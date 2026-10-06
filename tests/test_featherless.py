"""Provider document shapes and offline transport tests, never live API proof."""

import asyncio
import copy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import json
import unittest
from unittest.mock import patch

import httpx

from factorykit.featherless import (
    API_ORIGIN, MODEL_IDS, EvidenceError, evaluate_evidence, nano_usd, preflight,
)


# Field shapes and values from the four linked API references in featherless.py.
# The model docs use a Llama ID: below only the requested identity is substituted
# for offline tests. These fixture limits/prices are not claims about GLM.
PLAN = {"id": "feather_pro_plus", "name": "Feather Premium",
        "max_context_length": 32768, "max_model_size": None, "concurrency": 4}
MODEL = {"id": "meta-llama/Meta-Llama-3-8B-Instruct", "object": "model",
         "context_length": 8192, "max_completion_tokens": 4096, "concurrency_cost": 1,
         "is_gated": False, "available_on_current_plan": True,
         "pricing": {"prompt": "0.0000001", "completion": "0.0000001", "image": "0", "request": "0"},
         "features": {"tool_use": True}, "status": "active"}
DOC_CREDITS = {"balance_nano_usd": "42500000000", "balance_usd": "42.500000000",
               "reserved_nano_usd": "12000000", "reserved_usd": "0.012000000",
               "available_nano_usd": "42488000000", "available_usd": "42.488000000", "currency": "usd"}
USAGE = {"start_date": "2026-09-01T00:00:00.000Z", "end_date": "2026-10-01T00:00:00.000Z",
         "totals": {"request_count": 2, "input_tokens": 500, "output_tokens": 125,
                    "total_tokens": 625, "total_cost_nano_usd": "24500000"}}
# The reference's example query years differ from its example dates. Compute the
# matching request interval rather than reproducing that documentation typo.
START = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
ATTESTATION = {"request_pricing": True, "auto_topup_enabled": False, "existing_credit_only": True}


def responses():
    payloads = {"plan": copy.deepcopy(PLAN), "usage": copy.deepcopy(USAGE),
                "credits": copy.deepcopy(DOC_CREDITS)}
    # Synthetic policy amount matching the user's authorized existing balance.
    payloads["credits"].update(balance_nano_usd="25000000000", available_nano_usd="24988000000")
    for model_id in MODEL_IDS:
        payloads[model_id] = copy.deepcopy(MODEL)
        payloads[model_id]["id"] = model_id
    return payloads


def evaluate(payloads, **kwargs):
    options = {"usage_start": START, "usage_end": END, "expected_plan_id": PLAN["id"],
               "billing_attestation": ATTESTATION}
    options.update(kwargs)
    return evaluate_evidence(payloads, **options)


class FeatherlessEvidenceTests(unittest.TestCase):
    def test_documented_shapes_return_only_needed_fields_and_exact_values(self):
        payloads = responses()
        for payload in payloads.values():
            payload["secret"] = "must-not-persist"
        payloads["usage"]["models"] = [{"api_key_id": "private-key-id", "user_id": "private-user-id"}]
        result = evaluate(payloads)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["credits"]["balance_nano_usd"], 25000000000)
        self.assertEqual(result["usage"]["totals"]["total_cost_nano_usd"], 24500000)
        self.assertEqual(set(result["models"]), set(MODEL_IDS))
        self.assertEqual(result["models"][MODEL_IDS[0]]["effective_context_length"], 8192)
        self.assertEqual(result["models"][MODEL_IDS[0]]["pricing"], MODEL["pricing"])
        serialized = json.dumps(result)
        for private in ("must-not-persist", "private-key-id", "private-user-id", "Feather Premium"):
            self.assertNotIn(private, serialized)
        self.assertIn("neither enforces a dollar cap", serialized)

    def test_plan_discovery_is_useful_but_not_launch_approval(self):
        result = evaluate(responses(), expected_plan_id=None, billing_attestation=None)
        self.assertEqual(result["plan"]["id"], PLAN["id"])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["billing_attestation_verified_by_caller"])
        self.assertEqual(len(result["blockers"]), 2)
        result = evaluate(responses(), expected_plan_id="another_plan")
        self.assertEqual(result["status"], "BLOCKED")

    def test_plan_id_never_implies_request_pricing_or_disabled_topup(self):
        for attestation in (None, {}, {**ATTESTATION, "auto_topup_enabled": True},
                            {**ATTESTATION, "request_pricing": 1},
                            {**ATTESTATION, "existing_credit_only": False}):
            with self.subTest(attestation=attestation):
                result = evaluate(responses(), billing_attestation=attestation)
                self.assertEqual(result["status"], "BLOCKED")

    def test_concurrency_units_and_plan_context_cap_are_applied(self):
        payloads = responses()
        payloads["plan"]["max_context_length"] = 2048
        for model in MODEL_IDS:
            payloads[model]["concurrency_cost"] = 4
        result = evaluate(payloads)
        self.assertEqual(result["status"], "PASS")
        model = result["models"][MODEL_IDS[0]]
        self.assertEqual(model["effective_context_length"], 2048)
        self.assertEqual(model["effective_max_completion_tokens"], 2047)
        payloads["plan"]["concurrency"] = 3
        self.assertEqual(evaluate(payloads)["status"], "BLOCKED")
        payloads["plan"].update(concurrency=4, max_context_length=None)
        self.assertEqual(evaluate(payloads)["models"][MODEL_IDS[0]]["effective_context_length"], 8192)

    def test_wrong_model_unsupported_tools_inactive_or_unavailable_fail_closed(self):
        mutations = (("id", "different/model"), ("status", "not_deployed"),
                     ("available_on_current_plan", False), ("available_on_current_plan", 1),
                     ("is_gated", True), ("is_gated", None),
                     ("features", {"tool_use": False}), ("features", {"tool_use": 1}))
        for key, value in mutations:
            with self.subTest(field=key, value=value):
                payloads = responses()
                payloads[MODEL_IDS[0]][key] = value
                result = evaluate(payloads)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertNotIn(MODEL_IDS[0], result["models"])
                self.assertIn(MODEL_IDS[1], result["models"])

    def test_malformed_or_missing_positive_limits_are_rejected(self):
        for endpoint, key in (("plan", "concurrency"), ("plan", "max_context_length"),
                              (MODEL_IDS[0], "context_length"), (MODEL_IDS[0], "max_completion_tokens"),
                              (MODEL_IDS[0], "concurrency_cost")):
            for value in (0, -1, True, 1.5, "4", {}):
                with self.subTest(endpoint=endpoint, key=key, value=value):
                    payloads = responses()
                    payloads[endpoint][key] = value
                    self.assertEqual(evaluate(payloads)["status"], "BLOCKED")
            payloads = responses()
            del payloads[endpoint][key]
            self.assertEqual(evaluate(payloads)["status"], "BLOCKED")

    def test_documented_balance_is_exact_but_outside_the_approved_existing_credit(self):
        payloads = responses()
        payloads["credits"] = DOC_CREDITS
        result = evaluate(payloads)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["credits"]["available_nano_usd"], 42488000000)
        self.assertTrue(any("existing $25" in b for b in result["blockers"]))

    def test_exact_nano_usd_parser_rejects_coercion_and_invalid_amounts(self):
        self.assertEqual(nano_usd("9007199254740993"), 9007199254740993)
        for bad in (None, True, 123, 1.0, "1.0", "1e9", "-1", " 1", "01", "NaN", []):
            with self.subTest(value=bad), self.assertRaises(EvidenceError):
                nano_usd(bad)

    def test_prices_preserve_fractional_nano_precision_and_reject_missing_or_float(self):
        payloads = responses()
        price = "0.00000000012345678901234567890123456789"
        payloads[MODEL_IDS[0]]["pricing"]["prompt"] = price
        result = evaluate(payloads)
        self.assertEqual(Decimal(result["models"][MODEL_IDS[0]]["pricing"]["prompt"]), Decimal(price))
        for bad in (None, True, .0000001, "-1", "NaN", "Infinity", "1e-9"):
            with self.subTest(value=bad):
                payloads[MODEL_IDS[0]]["pricing"]["prompt"] = bad
                self.assertEqual(evaluate(payloads)["status"], "BLOCKED")

    def test_unknown_nonzero_billing_dimension_cannot_be_hidden_by_sanitization(self):
        payloads = responses()
        payloads[MODEL_IDS[0]]["pricing"]["future_charge"] = "0.1"
        self.assertEqual(evaluate(payloads)["status"], "BLOCKED")
        payloads[MODEL_IDS[0]]["pricing"]["future_charge"] = "0"
        self.assertEqual(evaluate(payloads)["status"], "PASS")

    def test_observed_numeric_aliases_must_match_documented_per_token_strings(self):
        payloads = responses()
        # Sanitized authenticated response shape reported by the operator;
        # numeric JSON values are represented exactly as the transport decodes.
        observed = (("0.0000014", "0.0000044", "1.4", "4.4"),
                    ("0.00000015", "0.0000005", "0.15", "0.5"))
        for model_id, (prompt, completion, input_rate, output_rate) in zip(MODEL_IDS, observed):
            payloads[model_id]["pricing"].update(
                prompt=prompt, completion=completion,
                input=Decimal(input_rate), output=Decimal(output_rate))
        result = evaluate(payloads)
        self.assertEqual(result["status"], "PASS")
        for model_id, (prompt, completion, _, _) in zip(MODEL_IDS, observed):
            self.assertEqual(result["models"][model_id]["pricing"],
                             {"prompt": prompt, "completion": completion, "image": "0", "request": "0"})
        # Evidence remains JSON serializable; aliases do not replace prices.
        json.dumps(result)

    def test_alias_conflicts_malformed_values_and_binary_floats_fail_closed(self):
        for alias in ("input", "output"):
            for amount in (Decimal("0.10000000000000000000000000001"),
                           Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1"),
                           True, None, {}, "0.1", 0.1):
                with self.subTest(alias=alias, amount=amount):
                    payloads = responses()
                    payloads[MODEL_IDS[0]]["pricing"][alias] = amount
                    result = evaluate(payloads)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertTrue(any(f"model.pricing.{alias}:" in b for b in result["blockers"]))
        payloads = responses()
        payloads[MODEL_IDS[0]]["pricing"].update(input=Decimal("0.1"), future_charge="0.1")
        self.assertEqual(evaluate(payloads)["status"], "BLOCKED")
        del payloads[MODEL_IDS[0]]["pricing"]["prompt"]
        self.assertEqual(evaluate(payloads)["status"], "BLOCKED")

    def test_alias_comparison_is_exact_independent_of_decimal_context(self):
        payloads = responses()
        payloads[MODEL_IDS[0]]["pricing"].update(
            prompt="0.00000012345678901234567890123456789",
            input=Decimal("0.12345678901234567890123456789"),
            completion="0.000001", output=1)
        with localcontext() as context:
            context.prec = 6
            self.assertEqual(evaluate(payloads)["status"], "PASS")
        payloads[MODEL_IDS[0]]["pricing"]["input"] = Decimal("0.12345678901234567890123456788")
        self.assertEqual(evaluate(payloads)["status"], "BLOCKED")

    def test_credit_exhaustion_reservations_inconsistency_and_upward_changes_block(self):
        for balance, reserved, available in (("0", "0", "0"), ("25", "25", "0"),
                                               ("25", "1", "25")):
            with self.subTest(balance=balance, reserved=reserved):
                payloads = responses()
                payloads["credits"].update(balance_nano_usd=balance, reserved_nano_usd=reserved,
                                           available_nano_usd=available)
                self.assertEqual(evaluate(payloads)["status"], "BLOCKED")
        result = evaluate(responses(), baseline_balance_nano_usd=24000000000)
        self.assertTrue(any("increased above" in b for b in result["blockers"]))
        self.assertEqual(evaluate(responses(), baseline_balance_nano_usd=25000000000)["status"], "PASS")

    def test_missing_cost_stays_unknown_and_nonempty_unpriced_usage_blocks(self):
        payloads = responses()
        payloads["usage"]["totals"]["total_cost_nano_usd"] = None
        result = evaluate(payloads)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["usage"]["totals"]["total_cost_nano_usd"])
        payloads["usage"]["totals"].update(request_count=0, input_tokens=0, output_tokens=0, total_tokens=0)
        result = evaluate(payloads)
        self.assertEqual(result["status"], "PASS")
        self.assertIsNone(result["usage"]["totals"]["total_cost_nano_usd"])
        del payloads["usage"]["totals"]["total_cost_nano_usd"]
        self.assertEqual(evaluate(payloads)["status"], "BLOCKED")

    def test_usage_must_match_window_and_have_consistent_real_counts(self):
        for field, value in (("request_count", True), ("input_tokens", "500"),
                             ("output_tokens", -1), ("total_tokens", 624),
                             ("total_cost_nano_usd", 24500000)):
            with self.subTest(field=field):
                payloads = responses()
                payloads["usage"]["totals"][field] = value
                self.assertEqual(evaluate(payloads)["status"], "BLOCKED")
        for date in (None, "bad date", "2025-09-01T00:00:00Z", "2026-09-01T00:00:00"):
            with self.subTest(date=date):
                payloads = responses()
                payloads["usage"]["start_date"] = date
                self.assertEqual(evaluate(payloads)["status"], "BLOCKED")


class FeatherlessTransportTests(unittest.IsolatedAsyncioTestCase):
    async def run_preflight(self, handler, **kwargs):
        options = dict(usage_start=START, usage_end=END, expected_plan_id=PLAN["id"],
                       billing_attestation=ATTESTATION, transport=httpx.MockTransport(handler))
        options.update(kwargs)
        return await preflight("test-secret-do-not-report", **options)

    def response_handler(self, calls, payloads=None):
        payloads = payloads or responses()
        def handle(request):
            calls.append(request)
            labels = {"/v1/plan": "plan", "/credits/balance": "credits", "/usage/activity/summary": "usage"}
            labels.update({"/v1/models/" + model: model for model in MODEL_IDS})
            return httpx.Response(200, json=payloads[labels[request.url.path]])
        return handle

    async def test_only_five_authenticated_gets_with_fixed_origin_and_no_environment_proxy(self):
        calls = []
        real_client = httpx.AsyncClient
        with patch("factorykit.featherless.httpx.AsyncClient", wraps=real_client) as client:
            result = await self.run_preflight(self.response_handler(calls))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(calls), 5)
        self.assertFalse(client.call_args.kwargs["trust_env"])
        self.assertFalse(client.call_args.kwargs["follow_redirects"])
        for request in calls:
            self.assertEqual(request.method, "GET")
            self.assertEqual(str(request.url).split(".ai", 1)[0] + ".ai", API_ORIGIN)
            self.assertEqual(request.headers["authorization"], "Bearer test-secret-do-not-report")
            self.assertNotIn("secret", str(request.url))
        self.assertEqual(dict(calls[-1].url.params), {"start": str(START), "end": str(END)})
        self.assertNotIn("test-secret", json.dumps(result))

    async def test_http_errors_and_redirects_never_follow_retry_or_return_bodies(self):
        for status in (302, 401, 403, 429, 503):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers={"Location": "https://evil.invalid"},
                                      text="test-secret-do-not-report raw error body")
            with self.subTest(status=status):
                result = await self.run_preflight(handler)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(len(calls), 5)
                self.assertTrue(any(f"HTTP {status}" in b for b in result["blockers"]))
                self.assertNotIn("raw error body", json.dumps(result))
                self.assertNotIn("test-secret", json.dumps(result))

    async def test_numeric_aliases_decode_directly_to_decimal_without_rounding(self):
        payloads = responses()
        prices = payloads[MODEL_IDS[0]]["pricing"]
        prices.update(prompt="0.00000012345678901234567890123456789",
                      input="exact-numeric-alias", output="exact-output-alias")
        delegate = self.response_handler([], payloads)
        for alias, expected in (("0.12345678901234567890123456789", "PASS"),
                                ("0.12345678901234567890123456788", "BLOCKED")):
            def handler(request):
                response = delegate(request)
                # Raw JSON decimal and scientific numeric literals exercise
                # decoding; neither passes through a Python float fixture.
                content = response.text.replace('"exact-numeric-alias"', alias)
                content = content.replace('"exact-output-alias"', '1e-1')
                return httpx.Response(200, text=content)
            with self.subTest(alias=alias):
                result = await self.run_preflight(handler)
                self.assertEqual(result["status"], expected)
                if expected == "PASS":
                    self.assertEqual(result["models"][MODEL_IDS[0]]["pricing"]["prompt"], prices["prompt"])
                    json.dumps(result)

    async def test_transport_error_and_malformed_json_are_sanitized(self):
        for handler in (lambda request: httpx.Response(200, text="test-secret-do-not-report"),
                        lambda request: self.raise_transport_error(request)):
            result = await self.run_preflight(handler)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertNotIn("test-secret", json.dumps(result))

    def raise_transport_error(self, request):
        raise httpx.ConnectError("test-secret-do-not-report", request=request)

    async def test_cancellation_is_not_converted_to_a_successful_snapshot(self):
        async def handler(request):
            raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.run_preflight(handler)

    async def test_overall_deadline_bounds_all_gets_and_keeps_partial_evidence(self):
        calls = []
        handler = self.response_handler(calls)
        async def slow_handler(request):
            if request.url.path != "/v1/plan":
                await asyncio.sleep(10)
            return handler(request)
        timeout = asyncio.timeout
        with patch("factorykit.featherless.asyncio.timeout", side_effect=lambda seconds: timeout(.01)):
            result = await self.run_preflight(slow_handler)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["plan"]["id"], PLAN["id"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("total timeout" in b for b in result["blockers"]))

    async def test_invalid_caller_arguments_never_open_connection(self):
        for kwargs in ({"usage_start": True}, {"usage_end": START},
                       {"baseline_balance_nano_usd": 25000000001}, {"expected_plan_id": []}):
            calls = []
            with self.subTest(kwargs=kwargs), self.assertRaises(EvidenceError):
                await self.run_preflight(self.response_handler(calls), **kwargs)
            self.assertEqual(calls, [])

    async def test_provider_echo_of_credential_in_plan_identity_is_redacted(self):
        payloads = responses()
        payloads["plan"]["id"] = "test-secret-do-not-report"
        result = await self.run_preflight(self.response_handler([], payloads))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("test-secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
