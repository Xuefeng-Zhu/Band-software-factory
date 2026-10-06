"""Offline request admission, streaming, persistence, and failure accounting."""

import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from factorykit.featherless import MODEL_IDS
from factorykit.featherless_guard import FeatherlessGuard, GuardError, _ceil_charge, _policy, _request


def models():
    return {model: {"id": model, "status": "active", "tool_use": True,
                    "available_on_current_plan": True, "is_gated": False,
                    "effective_context_length": 64, "effective_max_completion_tokens": 16,
                    "pricing": {"prompt": "0.001", "completion": "0.002", "image": "0", "request": "0.01"}}
            for model in MODEL_IDS}


def payload(**changes):
    return {"model": MODEL_IDS[0], "messages": [{"role": "user", "content": "private prompt"}], **changes}


def completion(prompt=10, output=5, **changes):
    return {"id": "private-provider-id", "choices": [{"finish_reason": "stop", "message": {"content": "private response"}}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": output, "total_tokens": prompt + output}, **changes}


def sse(value):
    return b"data: " + (value.encode() if isinstance(value, str) else json.dumps(value).encode()) + b"\n\n"


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


class FeatherlessGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "guard.json"
        self.calls = []

    def guard(self, handler=None, **kwargs):
        if handler is None:
            def handler(request):
                self.calls.append(request)
                return httpx.Response(200, json=completion())
        options = {"api_key": "real-provider-secret", "models": models(), "ledger_path": self.path,
                   "approved_credit_nano_usd": 25_000_000_000, "max_total_tokens": 2_000_000,
                   "overall_timeout_seconds": 21600, "request_timeout_seconds": 2,
                   "transport": httpx.MockTransport(handler)}
        options.update(kwargs)
        return FeatherlessGuard(**options)

    async def post(self, guard, body=None, **kwargs):
        async with httpx.AsyncClient(trust_env=False) as client:
            return await client.post(guard.url + "/chat/completions", json=body or payload(),
                                     headers={"Authorization": "Bearer " + guard.token}, **kwargs)

    async def test_before_forward_reservation_is_durable_and_response_settles_once(self):
        def handler(request):
            self.calls.append(request)
            saved = json.loads(self.path.read_text())
            record = next(iter(saved["requests"].values()))
            self.assertEqual(record["status"], "in_flight")
            self.assertEqual(record["reserved_tokens"], 80)
            self.assertEqual(record["reserved_nano_usd"], 106_000_000)
            self.assertIsNotNone(saved["started_epoch"])
            return httpx.Response(200, json=completion())
        async with self.guard(handler) as guard:
            self.assertIsNone(guard.verification()["started_epoch"])
            self.assertNotEqual(guard.token, "real-provider-secret")
            response = await self.post(guard)
            self.assertEqual(response.status_code, 200)
            proof = guard.verification()
            self.assertEqual(proof["observed_tokens"], 15)
            self.assertEqual(proof["charged_nano_usd"], 30_000_000)
            self.assertEqual(proof["held_tokens"], 0)
            self.assertEqual(proof["held_nano_usd"], 0)
        request = self.calls[0]
        self.assertEqual(str(request.url), "https://api.featherless.ai/v1/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer real-provider-secret")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        text = self.path.read_text()
        for secret in ("private prompt", "private response", "private-provider-id", "real-provider-secret", guard.token):
            self.assertNotIn(secret, text)
            self.assertNotIn(secret, json.dumps(proof))

    async def test_output_aliases_are_clamped_and_stream_usage_forced(self):
        def handler(request):
            self.calls.append(request)
            body = json.loads(request.content)
            self.assertEqual(body["max_tokens"], 8)
            self.assertNotIn("max_completion_tokens", body)
            self.assertTrue(body["stream_options"]["include_usage"])
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                                  stream=Stream([sse(completion()), sse("[DONE]")]))
        async with self.guard(handler) as guard:
            response = await self.post(guard, payload(stream=True, stream_options={"include_usage": False},
                                                     max_tokens=10000, max_completion_tokens=8))
            self.assertEqual(response.status_code, 200)
            self.assertIn("[DONE]", response.text)
            self.assertEqual(guard.verification()["observed_tokens"], 15)

    async def test_duplicate_and_larger_stream_usage_use_maximum_not_sum_and_ignore_cache_discount(self):
        events = [sse(completion()), sse(completion()), sse(completion(12, 6)), sse("[DONE]")]
        events[2] = sse(completion(12, 6, usage={"prompt_tokens": 12, "completion_tokens": 6,
                                              "total_tokens": 18, "prompt_tokens_details": {"cached_tokens": 12}}))
        def handler(request):
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                                  stream=Stream([b"".join(events)[:21], b"".join(events)[21:]]))
        async with self.guard(handler) as guard:
            response = await self.post(guard, payload(stream=True))
            self.assertEqual(response.content, b"".join(events))
            self.assertEqual(guard.verification()["observed_tokens"], 18)
            self.assertEqual(guard.verification()["charged_nano_usd"], 34_000_000)

    async def test_done_marker_is_withheld_until_final_usage_is_durable(self):
        reached_done, release = asyncio.Event(), asyncio.Event()
        class DelayedEOF(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield sse(completion())
                yield sse("[DONE]")
                reached_done.set()
                await release.wait()
        def handler(request):
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=DelayedEOF())
        async with self.guard(handler) as guard:
            received_done = asyncio.Event()
            async def consume():
                async with httpx.AsyncClient(trust_env=False) as client:
                    async with client.stream("POST", guard.url + "/chat/completions", json=payload(stream=True),
                                             headers={"Authorization": "Bearer " + guard.token}) as response:
                        async for chunk in response.aiter_bytes():
                            if b"[DONE]" in chunk:
                                self.assertEqual(guard.verification()["held_tokens"], 0)
                                received_done.set()
            task = asyncio.create_task(consume())
            await reached_done.wait()
            self.assertFalse(received_done.is_set())
            self.assertEqual(guard.verification()["held_tokens"], 80)
            release.set()
            await task
            self.assertTrue(received_done.is_set())

    async def test_concurrent_reservations_are_atomic_and_cannot_overrun_token_cap(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(request):
            self.calls.append(request)
            entered.set()
            await release.wait()
            return httpx.Response(200, json=completion())
        async with self.guard(handler, max_total_tokens=100) as guard:
            first = asyncio.create_task(self.post(guard))
            await entered.wait()
            second = await self.post(guard)
            self.assertEqual(second.status_code, 429)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(guard.verification()["held_tokens"], 80)
            release.set()
            self.assertEqual((await first).status_code, 200)
            self.assertIn("token reservation", guard.verification()["stopped_reason"])
            self.assertEqual((await self.post(guard)).status_code, 429)

    async def test_money_cap_rejects_before_forward_including_flat_request_charge(self):
        async with self.guard(approved_credit_nano_usd=105_999_999) as guard:
            self.assertEqual((await self.post(guard)).status_code, 429)
            self.assertEqual(self.calls, [])
            self.assertIsNone(guard.verification()["started_epoch"])
            self.assertEqual(guard.verification()["request_count"], 0)
            self.assertIn("money reservation", guard.verification()["stopped_reason"])

    async def test_restart_preserves_spend_tokens_and_first_request_clock(self):
        async with self.guard(max_total_tokens=100) as guard:
            await self.post(guard)
            started = guard.verification()["started_epoch"]
        async with self.guard(max_total_tokens=100) as guard:
            self.assertEqual(guard.verification()["started_epoch"], started)
            self.assertEqual(guard.verification()["observed_tokens"], 15)
            self.assertEqual((await self.post(guard)).status_code, 200)
            self.assertEqual((await self.post(guard)).status_code, 429)
            self.assertEqual(guard.verification()["observed_tokens"], 30)
        self.assertEqual(len(self.calls), 2)

    async def test_single_owner_lock_and_changed_policy_cannot_reset_ledger(self):
        async with self.guard() as guard:
            before = self.path.read_bytes()
            with self.assertRaises(GuardError):
                async with self.guard():
                    pass
            self.assertEqual(self.path.read_bytes(), before)
            await self.post(guard)
        before = self.path.read_bytes()
        with self.assertRaises(GuardError):
            async with self.guard(max_total_tokens=999999):
                pass
        self.assertEqual(self.path.read_bytes(), before)

    async def test_missing_usage_retains_full_reservation_and_blocks_after_restart(self):
        def handler(request):
            self.calls.append(request)
            return httpx.Response(200, json=completion(usage=None))
        async with self.guard(handler) as guard:
            with self.assertRaises(httpx.RemoteProtocolError):
                await self.post(guard)
            proof = guard.verification()
            self.assertEqual(proof["observed_tokens"], 0)
            self.assertEqual(proof["held_tokens"], 80)
            self.assertEqual(proof["held_nano_usd"], 106_000_000)
            self.assertIsNotNone(proof["stopped_reason"])
        async with self.guard() as guard:
            self.assertEqual((await self.post(guard)).status_code, 429)
            self.assertEqual(guard.verification()["held_tokens"], 80)
        self.assertEqual(len(self.calls), 1)

    async def test_pending_record_from_crash_is_retained_and_halts_on_restart(self):
        async with self.guard() as guard:
            guard._ledger.reserve(MODEL_IDS[0], 16)
        async with self.guard() as guard:
            self.assertEqual(guard.verification()["held_tokens"], 80)
            self.assertEqual(guard.verification()["stopped_reason"], "unfinished provider request found on restart")
            self.assertEqual((await self.post(guard)).status_code, 429)
        self.assertEqual(self.calls, [])

    async def test_client_cancellation_retains_unknown_request_and_no_free_retry(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def handler(request):
            entered.set()
            try:
                await asyncio.sleep(20)
            except asyncio.CancelledError:
                cancelled.set()
                raise
        async with self.guard(handler) as guard:
            request = asyncio.create_task(self.post(guard))
            await entered.wait()
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
            await asyncio.wait_for(cancelled.wait(), 1)
            # The disconnect task then durably stops admission.
            for _ in range(10):
                if guard.verification()["stopped_reason"]:
                    break
                await asyncio.sleep(.01)
            self.assertEqual(guard.verification()["held_tokens"], 80)
            self.assertEqual((await self.post(guard)).status_code, 429)

    async def test_partial_stream_without_done_retains_reservation(self):
        def handler(request):
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                                  stream=Stream([sse(completion())]))
        async with self.guard(handler) as guard:
            with self.assertRaises(httpx.RemoteProtocolError):
                await self.post(guard, payload(stream=True))
            self.assertEqual(guard.verification()["held_tokens"], 80)
            self.assertEqual(guard.verification()["observed_tokens"], 0)

    async def test_provider_errors_are_sanitized_and_never_retried(self):
        def handler(request):
            self.calls.append(request)
            return httpx.Response(429, text="real-provider-secret private prompt raw provider failure")
        async with self.guard(handler) as guard:
            response = await self.post(guard)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("private", response.text)
            self.assertNotIn("real-provider", response.text)
            self.assertEqual(guard.verification()["held_tokens"], 80)
            self.assertEqual((await self.post(guard)).status_code, 429)
        self.assertEqual(len(self.calls), 1)

    async def test_malformed_or_excess_usage_is_not_used_to_release_reservation(self):
        for usage in ({"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2},
                      {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 3},
                      {"prompt_tokens": 65, "completion_tokens": 1, "total_tokens": 66},
                      {"prompt_tokens": 1, "completion_tokens": 17, "total_tokens": 18}):
            with self.subTest(usage=usage):
                self.path = Path(self.directory.name) / (str(len(list(Path(self.directory.name).glob('*.json')))) + ".json")
                async with self.guard(lambda request: httpx.Response(200, json=completion(usage=usage))) as guard:
                    with self.assertRaises(httpx.RemoteProtocolError):
                        await self.post(guard)
                    self.assertEqual(guard.verification()["held_tokens"], 80)
                    self.assertEqual(guard.verification()["observed_tokens"], 0)

    async def test_unapproved_models_multimodal_and_extra_billing_parameters_never_forward(self):
        bodies = [payload(model="zai-org/GLM-5.3-extra"), payload(n=2), payload(n=True), payload(max_tokens=True),
                  payload(audio={}), payload(best_of=4), payload(extra_unknown_fee=True),
                  payload(messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:x"}}]}]),
                  payload(messages=[{"role": "user", "content": "text", "audio": {}}])]
        async with self.guard() as guard:
            for body in bodies:
                with self.subTest(body=body):
                    self.assertEqual((await self.post(guard, body)).status_code, 400)
            self.assertEqual(self.calls, [])
            self.assertIsNone(guard.verification()["started_epoch"])
            self.assertEqual(guard.verification()["request_count"], 0)
            self.assertIsNone(guard.verification()["stopped_reason"])
            self.assertEqual((await self.post(guard, payload(model=MODEL_IDS[1]))).status_code, 200)

    async def test_loopback_auth_and_only_approved_post_route(self):
        async with self.guard() as guard, httpx.AsyncClient(trust_env=False) as client:
            self.assertTrue(guard.url.startswith("http://127.0.0.1:"))
            self.assertEqual((await client.post(guard.url + "/chat/completions", json=payload())).status_code, 401)
            for route in ("/responses", "/models", "/chat/completions?bypass=true"):
                response = await client.post(guard.url + route, json=payload(),
                                             headers={"Authorization": "Bearer " + guard.token})
                self.assertEqual(response.status_code, 404)
            self.assertEqual((await client.get(guard.url + "/chat/completions")).status_code, 404)
            self.assertEqual(self.calls, [])

    async def test_overall_deadline_survives_restart(self):
        async with self.guard() as guard:
            await self.post(guard)
            start = guard.verification()["started_epoch"]
        async with self.guard() as guard:
            with patch("factorykit.featherless_guard.time.time", return_value=start + 21600):
                self.assertEqual((await self.post(guard)).status_code, 429)
            self.assertEqual(guard.verification()["stopped_reason"], "overall time budget exhausted")
        self.assertEqual(len(self.calls), 1)

    async def test_request_timeout_retains_full_reservation(self):
        async def handler(request):
            await asyncio.sleep(20)
        async with self.guard(handler, request_timeout_seconds=1) as guard:
            with self.assertRaises(httpx.RemoteProtocolError):
                await self.post(guard)
            self.assertEqual(guard.verification()["held_tokens"], 80)
            self.assertIsNotNone(guard.verification()["stopped_reason"])

    def test_exact_rounding_and_policy_limits(self):
        self.assertEqual(_ceil_charge("0.0000000000000000001", 1), 1)
        self.assertEqual(_ceil_charge("0.123456789123456789", 100), 12345678913)
        for kwargs in ({"approved_credit_nano_usd": 25000000001}, {"max_total_tokens": 2000001},
                       {"overall_timeout_seconds": 21601}, {"max_total_tokens": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(GuardError):
                self.guard(**kwargs)
        metadata = models()
        metadata[MODEL_IDS[0]]["pricing"]["future_fee"] = "1"
        with self.assertRaises(GuardError):
            self.guard(models=metadata)

    def test_glm_assistant_reasoning_history_accepts_only_text_without_new_billing_mode(self):
        policy = _policy(models(), 25000000000, 2000000, 21600)
        for value in (None, "prior assistant reasoning"):
            body = payload(messages=[{"role": "assistant", "content": "", "reasoning_content": value,
                                      "tool_calls": [{"id": "call", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]}])
            parsed, output = _request(body, policy["models"])
            self.assertEqual(parsed["messages"][0]["reasoning_content"], value)
            self.assertEqual(output, 16)
        for value in (True, 3, [], {"type": "image_url", "image_url": {"url": "data:x"}}):
            with self.subTest(value=value), self.assertRaises(GuardError):
                _request(payload(messages=[{"role": "assistant", "content": "", "reasoning_content": value}]), policy["models"])


if __name__ == "__main__":
    unittest.main()
