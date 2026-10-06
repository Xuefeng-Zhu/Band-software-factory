"""Offline exact aggregate billing and unchanged cumulative liability tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

from factorykit.featherless_guard import GuardError, MODEL_IDS, _Ledger, _canonical, _charge, _policy, apply_billing_checkpoint, reconcile_factory_money_halt


ACTUAL = 450_000_000
CONSERVATIVE = 900_000_000
REQUESTS = 3


class BillingCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.path, self.report = root / "guard.json", root / "provider.json"
        models = {model: {"id": model, "status": "active", "tool_use": True,
            "available_on_current_plan": True, "is_gated": False,
            "effective_context_length": 1024, "effective_max_completion_tokens": 16,
            "pricing": {"prompt": "0.01", "completion": "0.02", "image": "0", "request": "0.1"}}
            for model in MODEL_IDS}
        # Exercise the normalized ledger seam; full production authority/mode
        # validation remains covered by the existing balance-only tests.
        self.policy = _policy(models, 25_000_000_000, 2_000_000, 21600)
        self.policy["balance_only"] = True
        model = MODEL_IDS[0]; pinned = self.policy["models"][model]
        requests = {f"{index:032x}": {"model": model, "status": "settled", "output_ceiling": 16,
            "reserved_tokens": 1040, "reserved_nano_usd": _charge(pinned, 1024, 16),
            "prompt_tokens": 10, "completion_tokens": 5, "charged_nano_usd": _charge(pinned, 10, 5)}
            for index in range(1, REQUESTS + 1)}
        self.original = {"schema_version": 1, "policy": self.policy, "started_epoch": time.time() - 60,
                         "stopped_reason": None, "requests": requests}
        self.billing = {"status": "PASS", "api_origin": "https://api.featherless.ai", "blockers": [],
            "billing_attestation_verified_by_caller": True,
            "credits": {"currency": "usd", "balance_nano_usd": 25_000_000_000 - ACTUAL,
                        "available_nano_usd": 25_000_000_000 - ACTUAL, "reserved_nano_usd": 0},
            "usage": {"totals": {"request_count": REQUESTS, "input_tokens": 30, "output_tokens": 15,
                       "total_tokens": 45, "total_cost_nano_usd": ACTUAL}}}
        raw, billed = _canonical(self.original).encode(), _canonical(self.billing).encode()
        self.path.write_bytes(raw); self.path.chmod(0o600)
        self.report.write_bytes(billed); self.report.chmod(0o600)
        self.original = json.loads(raw)
        self.policy = copy.deepcopy(self.original["policy"])
        blocker = patch.object(socket.socket, "connect", side_effect=AssertionError("Offline checkpoint must not connect"))
        blocker.start(); self.addCleanup(blocker.stop)

    def reference(self):
        return {"path": str(self.report), "sha256": hashlib.sha256(self.report.read_bytes()).hexdigest()}

    def write_report(self, value):
        self.report.write_text(json.dumps(value)); self.report.chmod(0o600)

    def checked(self):
        ledger = _Ledger(self.path, self.policy)
        ledger.open()
        self.addCleanup(ledger.close)
        return ledger

    def install(self):
        before = self.path.read_bytes()
        return apply_billing_checkpoint(self.path, self.policy, self.reference(), apply=True,
                                        expected_ledger_sha256=hashlib.sha256(before).hexdigest())

    def test_synthetic_aggregate_preflight_and_apply_preserve_every_original_field(self):
        before = self.path.read_bytes(); report_before = self.report.read_bytes()
        review = apply_billing_checkpoint(self.path, self.policy, self.reference())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(review["status"], "REVIEW_ONLY")
        self.assertEqual(review["checkpoint"]["request_count"], REQUESTS)
        self.assertEqual(review["checkpoint"]["input_tokens"], 30)
        self.assertEqual(review["checkpoint"]["output_tokens"], 15)
        self.assertEqual(review["totals"]["charged_nano_usd"], ACTUAL)
        self.assertEqual(review["totals"]["total_conservative_charged_nano_usd"], CONSERVATIVE)
        self.assertEqual(review["totals"]["held_nano_usd"], 0)
        result = self.install()
        saved = json.loads(self.path.read_bytes())
        self.assertEqual({k: v for k, v in saved.items() if k != "billing_checkpoint"}, self.original)
        self.assertEqual(self.report.read_bytes(), report_before)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(result["original_started_epoch"], self.original["started_epoch"])
        self.assertEqual(result["original_requests_sha256"], hashlib.sha256(_canonical(self.original["requests"]).encode()).hexdigest())
        self.assertEqual(result["network_calls"], 0)

    def test_reopen_and_later_requests_charge_conservatively_and_hold_full_reservation(self):
        self.install(); ledger = self.checked()
        model = next(iter(self.policy["models"]))
        key = ledger.reserve(model, 8)
        record = ledger.data["requests"][key]
        totals = ledger.totals()
        self.assertEqual(totals["charged_nano_usd"], ACTUAL)
        self.assertEqual(totals["held_nano_usd"], record["reserved_nano_usd"])
        self.assertEqual(totals["held_tokens"], record["reserved_tokens"])
        ledger.settle(key, 100, 5)
        charge = _charge(self.policy["models"][model], 100, 5)
        self.assertEqual(ledger.totals()["charged_nano_usd"], ACTUAL + charge)
        self.assertEqual(ledger.totals()["total_conservative_charged_nano_usd"], CONSERVATIVE + charge)
        self.assertEqual(ledger.data["started_epoch"], self.original["started_epoch"])
        self.assertEqual(len(ledger.data["requests"]), REQUESTS + 1)
        self.assertEqual({k: ledger.data["requests"][k] for k in self.original["requests"]}, self.original["requests"])

    def test_missing_usage_or_in_flight_request_cannot_install_or_clear_stop(self):
        for status in ("unknown", "in_flight"):
            with self.subTest(status=status):
                data = copy.deepcopy(self.original)
                record = next(iter(data["requests"].values()))
                record["status"] = status
                self.path.write_text(_canonical(data)); self.path.chmod(0o600)
                before = self.path.read_bytes()
                with self.assertRaises(GuardError):
                    apply_billing_checkpoint(self.path, self.policy, self.reference())
                self.assertEqual(self.path.read_bytes(), before)
        data = copy.deepcopy(self.original); data["stopped_reason"] = "provider request usage is unknown"
        self.path.write_text(_canonical(data)); self.path.chmod(0o600)
        before = self.path.read_bytes()
        with self.assertRaises(GuardError):
            self.install()
        self.assertEqual(self.path.read_bytes(), before)

    def test_report_counter_or_price_mismatch_is_not_a_reset(self):
        changes = [("request_count", REQUESTS - 1), ("input_tokens", 29), ("output_tokens", 14),
                   ("total_tokens", 44), ("total_cost_nano_usd", None),
                   ("total_cost_nano_usd", -1), ("total_cost_nano_usd", True),
                   ("total_cost_nano_usd", CONSERVATIVE + 1)]
        before = self.path.read_bytes()
        for key, value in changes:
            with self.subTest(key=key, value=value):
                billed = copy.deepcopy(self.billing); billed["usage"]["totals"][key] = value
                self.write_report(billed)
                with self.assertRaises(GuardError):
                    self.install()
                self.assertEqual(self.path.read_bytes(), before)

    def test_credit_increase_reservation_currency_and_conservation_are_rejected(self):
        changes = [("balance_nano_usd", 25_000_000_001), ("available_nano_usd", 25_000_000_001 - ACTUAL),
                   ("reserved_nano_usd", 1), ("currency", "eur"), ("balance_nano_usd", 25_000_000_001 - ACTUAL)]
        before = self.path.read_bytes()
        for key, value in changes:
            with self.subTest(key=key):
                billed = copy.deepcopy(self.billing); billed["credits"][key] = value; self.write_report(billed)
                with self.assertRaises(GuardError):
                    self.install()
                self.assertEqual(self.path.read_bytes(), before)

    def test_pass_origin_attestation_and_blockers_are_required(self):
        for key, value in (("status", "BLOCKED"), ("api_origin", "https://other.invalid"),
                           ("billing_attestation_verified_by_caller", False), ("blockers", ["unknown usage"])):
            with self.subTest(key=key):
                billed = copy.deepcopy(self.billing); billed[key] = value; self.write_report(billed)
                with self.assertRaises(GuardError):
                    self.install()

    def test_covered_record_extra_field_tampering_breaks_exact_binding(self):
        self.install()
        data = json.loads(self.path.read_bytes())
        identity = next(iter(data["requests"]))
        data["requests"][identity]["extra"] = "changed"
        self.path.write_text(_canonical(data)); self.path.chmod(0o600)
        with self.assertRaises(GuardError):
            self.checked()

    def test_checkpoint_field_or_covered_set_tampering_is_rejected(self):
        self.install(); original = self.path.read_bytes()
        for key, value in (("actual_charged_nano_usd", 0), ("covered_requests_sha256", "0" * 64),
                           ("covered_request_ids", list(self.original["requests"])[:-1]), ("extra", True)):
            with self.subTest(key=key):
                data = json.loads(original); data["billing_checkpoint"][key] = value
                self.path.write_text(_canonical(data)); self.path.chmod(0o600)
                with self.assertRaises(GuardError):
                    self.checked()

    def test_changed_or_missing_report_blocks_before_new_request(self):
        self.install(); ledger = self.checked(); before = self.path.read_bytes()
        self.report.write_bytes(self.report.read_bytes() + b"\n")
        model = next(iter(self.policy["models"]))
        with self.assertRaises(GuardError):
            ledger.reserve(model, 8)
        self.assertEqual(self.path.read_bytes(), before)
        self.report.unlink()
        with self.assertRaises(GuardError):
            ledger.reserve(model, 8)
        self.assertEqual(self.path.read_bytes(), before)

    def test_report_must_be_owner_private_and_have_no_symlink_or_hardlink(self):
        before = self.path.read_bytes()
        self.report.chmod(0o644)
        with self.assertRaises(GuardError): self.install()
        self.report.chmod(0o600)
        linked = self.report.with_name("hardlinked.json"); os.link(self.report, linked)
        with self.assertRaises(GuardError): self.install()
        linked.unlink()
        linked.symlink_to(self.report)
        with self.assertRaises(GuardError):
            apply_billing_checkpoint(self.path, self.policy, {"path": str(linked), "sha256": self.reference()["sha256"]})
        self.assertEqual(self.path.read_bytes(), before)

    def test_same_checkpoint_apply_is_idempotent_and_replacement_is_rejected(self):
        self.install(); before = self.path.read_bytes()
        self.assertFalse(self.install()["ledger_write"])
        self.assertEqual(self.path.read_bytes(), before)
        billed = copy.deepcopy(self.billing)
        billed["usage"]["totals"]["total_cost_nano_usd"] -= 1
        billed["credits"]["balance_nano_usd"] += 1; billed["credits"]["available_nano_usd"] += 1
        self.write_report(billed)
        with self.assertRaises(GuardError): self.install()
        self.assertEqual(self.path.read_bytes(), before)

    def test_stale_apply_digest_and_existing_owner_reject_without_write(self):
        before = self.path.read_bytes()
        with self.assertRaises(GuardError):
            apply_billing_checkpoint(self.path, self.policy, self.reference(), apply=True, expected_ledger_sha256="0" * 64)
        ledger = self.checked()
        with self.assertRaises(GuardError): self.install()
        self.assertEqual(self.path.read_bytes(), before)
        ledger.close()

    def test_legacy_accounting_without_checkpoint_is_unchanged(self):
        ledger = self.checked()
        self.assertEqual(ledger.totals()["charged_nano_usd"], CONSERVATIVE)
        self.assertEqual(ledger.totals()["total_conservative_charged_nano_usd"], CONSERVATIVE)
        self.assertEqual(ledger.data, self.original)
        policy = copy.deepcopy(self.policy); policy.pop("balance_only")
        bare = _Ledger(self.path, policy); bare.data = copy.deepcopy(self.original)
        with self.assertRaises(GuardError):
            bare.billing_checkpoint(self.reference(), sorted(self.original["requests"]))

    def test_later_unknown_request_keeps_its_entire_liability_and_stop(self):
        self.install(); ledger = self.checked()
        model = next(iter(self.policy["models"]))
        key = ledger.reserve(model, 8); held = ledger.data["requests"][key]["reserved_nano_usd"]
        ledger.unknown(key)
        self.assertEqual(ledger.totals()["charged_nano_usd"], ACTUAL)
        self.assertEqual(ledger.totals()["held_nano_usd"], held)
        self.assertEqual(ledger.data["stopped_reason"], "provider request usage is unknown")
        before = self.path.read_bytes()
        with self.assertRaises(GuardError): ledger.reserve(model, 8)
        self.assertEqual(self.path.read_bytes(), before)

    def test_effective_25_dollar_cap_still_blocks_full_reservations_without_forwarding(self):
        self.install(); ledger = self.checked()
        model = next(iter(self.policy["models"]))
        output = self.policy["models"][model]["output_ceiling"]
        price = _charge(self.policy["models"][model], self.policy["models"][model]["input_ceiling"], output)
        allowed = (25_000_000_000 - ACTUAL) // price
        for _ in range(allowed): ledger.reserve(model, output)
        self.assertEqual(ledger.totals()["held_nano_usd"], allowed * price)
        self.assertLessEqual(ledger.totals()["charged_nano_usd"] + ledger.totals()["held_nano_usd"], 25_000_000_000)
        with self.assertRaises(GuardError): ledger.reserve(model, output)
        self.assertEqual(len(ledger.data["requests"]), REQUESTS + allowed)
        self.assertEqual(ledger.data["stopped_reason"], "money reservation would exceed the approved cap")

    def append_settled(self, prompt, completion=5):
        ledger = self.checked()
        model = next(iter(self.policy["models"]))
        identity = ledger.reserve(model, 16)
        ledger.settle(identity, prompt, completion)
        # Extra original request provenance is included in the immutable binding.
        ledger.data["requests"][identity]["caller_id"] = "caller-" + identity
        ledger._save()
        ledger.close()
        return identity

    def subsequent_report(self, cost, suffix):
        requests = json.loads(self.path.read_bytes())["requests"]
        report = copy.deepcopy(self.billing)
        prompt = sum(item["prompt_tokens"] for item in requests.values())
        output = sum(item["completion_tokens"] for item in requests.values())
        report["usage"]["totals"].update(request_count=len(requests), input_tokens=prompt,
            output_tokens=output, total_tokens=prompt + output, total_cost_nano_usd=cost)
        report["credits"].update(balance_nano_usd=25_000_000_000 - cost,
            available_nano_usd=25_000_000_000 - cost)
        path = self.report.with_name("provider-" + suffix + ".json")
        path.write_text(_canonical(report)); path.chmod(0o600)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def append_checkpoint(self, reference, apply=True):
        return apply_billing_checkpoint(self.path, self.policy, reference, apply=apply,
            expected_ledger_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest() if apply else None)

    def two_checkpoints(self):
        self.install()
        original_checkpoint = copy.deepcopy(json.loads(self.path.read_bytes())["billing_checkpoint"])
        original_report = self.report.read_bytes()
        self.append_settled(100)
        reference = self.subsequent_report(ACTUAL + 600_000_000, "second")
        self.append_checkpoint(reference)
        return original_checkpoint, original_report, reference

    def test_second_cumulative_checkpoint_preserves_original_and_does_not_double_count(self):
        original_checkpoint, original_report, second_reference = self.two_checkpoints()
        before = json.loads(self.path.read_bytes())
        second = copy.deepcopy(before["billing_checkpoint_history"][0])
        self.assertEqual(second["parent_checkpoint_sha256"], hashlib.sha256(_canonical(original_checkpoint).encode()).hexdigest())
        ledger = self.checked()
        self.assertEqual(ledger.totals()["charged_nano_usd"], ACTUAL + 600_000_000)
        self.assertEqual(before["billing_checkpoint"], original_checkpoint)
        self.assertEqual(self.report.read_bytes(), original_report)

    def test_three_prefixes_dry_run_idempotence_and_unchanged_request_provenance(self):
        original_checkpoint, original_report, second_reference = self.two_checkpoints()
        second_bytes = Path(second_reference["path"]).read_bytes()
        before_second = json.loads(self.path.read_bytes())
        self.append_settled(200)
        before = self.path.read_bytes(); original = json.loads(before)
        reference = self.subsequent_report(ACTUAL + 1_400_000_000, "third")
        review = self.append_checkpoint(reference, apply=False)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(review["checkpoint_count"], 3)
        self.assertEqual(review["totals"]["charged_nano_usd"], ACTUAL + 1_400_000_000)
        result = self.append_checkpoint(reference)
        saved = json.loads(self.path.read_bytes())
        self.assertEqual(saved["billing_checkpoint"], original_checkpoint)
        self.assertEqual(saved["billing_checkpoint_history"][:1], before_second["billing_checkpoint_history"])
        self.assertEqual(saved["billing_checkpoint_history"][1]["parent_checkpoint_sha256"],
            hashlib.sha256(_canonical(before_second["billing_checkpoint_history"][0]).encode()).hexdigest())
        self.assertEqual({k: v for k, v in saved.items() if k != "billing_checkpoint_history"},
            {k: v for k, v in original.items() if k != "billing_checkpoint_history"})
        self.assertEqual(self.report.read_bytes(), original_report)
        self.assertEqual(Path(second_reference["path"]).read_bytes(), second_bytes)
        self.assertEqual(result["totals"]["total_conservative_charged_nano_usd"], CONSERVATIVE + 3_400_000_000)
        after = self.path.read_bytes()
        self.assertFalse(self.append_checkpoint(reference)["ledger_write"])
        self.assertEqual(self.path.read_bytes(), after)

    def test_latest_checkpoint_keeps_uncovered_settled_and_new_inflight_liabilities(self):
        _, _, second_reference = self.two_checkpoints()
        ledger = self.checked(); model = next(iter(self.policy["models"]))
        key = ledger.reserve(model, 16)
        held = ledger.data["requests"][key]["reserved_nano_usd"]
        self.assertEqual(ledger.totals()["charged_nano_usd"], ACTUAL + 600_000_000)
        self.assertEqual(ledger.totals()["held_nano_usd"], held)
        ledger.settle(key, 200, 5)
        self.assertEqual(ledger.totals()["charged_nano_usd"], ACTUAL + 600_000_000 + 2_200_000_000)
        key = ledger.reserve(model, 16); ledger.unknown(key)
        self.assertEqual(ledger.totals()["held_nano_usd"], held)
        before = self.path.read_bytes(); ledger.close()
        with self.assertRaises(GuardError): self.append_checkpoint(second_reference)
        self.assertEqual(self.path.read_bytes(), before)

    def test_chain_parent_coverage_record_report_or_history_tampering_blocks_admission(self):
        self.two_checkpoints(); original = self.path.read_bytes()
        variants = []
        for key, value in (("parent_checkpoint_sha256", "0" * 64), ("covered_requests_sha256", "0" * 64),
                           ("covered_request_ids", sorted(self.original["requests"])), ("actual_charged_nano_usd", 0)):
            data = json.loads(original); data["billing_checkpoint_history"][0][key] = value; variants.append(data)
        data = json.loads(original); data["billing_checkpoint_history"] *= 2; variants.append(data)
        data = json.loads(original); data["billing_checkpoint_history"] = []; variants.append(data)
        data = json.loads(original); data.pop("billing_checkpoint"); variants.append(data)
        data = json.loads(original); identity = data["billing_checkpoint_history"][0]["covered_request_ids"][-1]
        data["requests"][identity]["caller_id"] = "tampered"; variants.append(data)
        for data in variants:
            with self.subTest(data=data.get("billing_checkpoint_history")):
                self.path.write_text(_canonical(data)); self.path.chmod(0o600)
                with self.assertRaises(GuardError): self.checked()
        self.path.write_bytes(original)
        checkpoint = json.loads(original)["billing_checkpoint_history"][0]
        Path(checkpoint["provider_report"]["path"]).unlink()
        with self.assertRaises(GuardError): self.checked()

    def test_subsequent_decreasing_or_excess_increment_cost_is_not_a_reset(self):
        self.install(); self.append_settled(100); before = self.path.read_bytes()
        for number, cost in enumerate((ACTUAL - 1, ACTUAL + 1_200_000_001)):
            reference = self.subsequent_report(cost, "invalid-" + str(number))
            with self.assertRaises(GuardError): self.append_checkpoint(reference)
            self.assertEqual(self.path.read_bytes(), before)

    def test_all_retained_reports_are_still_required_after_later_checkpoint(self):
        self.two_checkpoints()
        ledger = self.checked(); before = self.path.read_bytes()
        self.report.unlink()
        with self.assertRaises(GuardError): ledger.reserve(next(iter(self.policy["models"])), 8)
        self.assertEqual(self.path.read_bytes(), before)

    def test_later_exact_report_still_requires_usage_attestation_and_credit_conservation(self):
        self.install(); self.append_settled(100); before = self.path.read_bytes()
        reference = self.subsequent_report(ACTUAL + 600_000_000, "invalid-credits")
        good = json.loads(Path(reference["path"]).read_text())
        changes = [("usage", "input_tokens", 129), ("usage", "output_tokens", None),
                   ("credits", "balance_nano_usd", good["credits"]["balance_nano_usd"] + 1),
                   ("credits", "reserved_nano_usd", 1), ("root", "billing_attestation_verified_by_caller", False)]
        for section, key, value in changes:
            data = copy.deepcopy(good)
            target = data["usage"]["totals"] if section == "usage" else data if section == "root" else data[section]
            target[key] = value; path = Path(reference["path"]); path.write_text(_canonical(data))
            changed = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            with self.assertRaises(GuardError): self.append_checkpoint(changed)
            self.assertEqual(self.path.read_bytes(), before)

    def test_latest_actual_cost_still_exhausts_only_the_original_25_dollar_cap(self):
        self.two_checkpoints(); ledger = self.checked()
        model = next(iter(self.policy["models"])); price = _charge(self.policy["models"][model], 1024, 16)
        cost = ACTUAL + 600_000_000
        allowed = (25_000_000_000 - cost) // price
        for _ in range(allowed): ledger.reserve(model, 16)
        self.assertEqual(ledger.totals()["charged_nano_usd"], cost)
        self.assertEqual(ledger.totals()["held_nano_usd"], allowed * price)
        with self.assertRaises(GuardError): ledger.reserve(model, 16)
        self.assertEqual(ledger.data["stopped_reason"], "money reservation would exceed the approved cap")

    def halt_image(self, raw, name="guard-halt-before.json"):
        path = self.path.with_name(name); path.write_bytes(raw); path.chmod(0o600)
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}

    def money_halt(self):
        self.install(); self.append_settled(100)
        data = json.loads(self.path.read_bytes())
        data["stopped_reason"] = "money reservation would exceed the approved cap"
        self.path.write_text(_canonical(data)); self.path.chmod(0o600)
        raw = self.path.read_bytes()
        return raw, self.halt_image(raw), self.subsequent_report(ACTUAL + 600_000_000, "halt")

    def release_money_halt(self, report, image, apply=True):
        return apply_billing_checkpoint(self.path, self.policy, report, apply=apply,
            expected_ledger_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest() if apply else None,
            reconcile_stale_money_halt=True, halt_before_image=image)

    def test_stale_money_halt_release_is_explicit_report_bound_and_preserves_raw_history(self):
        raw, image, report = self.money_halt(); original = json.loads(raw)
        with self.assertRaises(GuardError): self.append_checkpoint(report)
        review = self.release_money_halt(report, image, apply=False)
        self.assertTrue(review["stale_money_halt_reconciled"])
        self.assertEqual(self.path.read_bytes(), raw)
        result = self.release_money_halt(report, image)
        saved = json.loads(self.path.read_bytes())
        self.assertIsNone(saved["stopped_reason"])
        self.assertEqual(saved["billing_checkpoint"], original["billing_checkpoint"])
        self.assertEqual(saved["requests"], original["requests"])
        self.assertEqual(saved["policy"], original["policy"])
        self.assertEqual(saved["started_epoch"], original["started_epoch"])
        amendment = saved["billing_money_halt_reconciliations"][0]
        self.assertEqual(amendment["before_guard_ledger"], image)
        self.assertEqual(amendment["original_stopped_reason"], original["stopped_reason"])
        self.assertEqual(amendment["provider_report"], report)
        self.assertEqual(Path(image["path"]).read_bytes(), raw)
        ledger = self.checked()
        self.assertEqual(ledger.totals()["charged_nano_usd"], ACTUAL + 600_000_000)
        ledger.reserve(next(iter(self.policy["models"])), 8)

    def test_money_halt_opt_in_never_releases_other_halts_unknown_usage_or_wrong_before_image(self):
        raw, image, report = self.money_halt()
        for reason in ("provider request usage is unknown", "provider request failed or was interrupted",
                       "ledger persistence failed", "overall time budget exhausted"):
            data = json.loads(raw); data["stopped_reason"] = reason
            self.path.write_text(_canonical(data)); self.path.chmod(0o600); before = self.path.read_bytes()
            with self.assertRaises(GuardError): self.release_money_halt(report, self.halt_image(before))
            self.assertEqual(self.path.read_bytes(), before)
        for status in ("in_flight", "unknown"):
            data = json.loads(raw); next(iter(data["requests"].values()))["status"] = status
            self.path.write_text(_canonical(data)); self.path.chmod(0o600); before = self.path.read_bytes()
            with self.assertRaises(GuardError): self.release_money_halt(report, self.halt_image(before))
            self.assertEqual(self.path.read_bytes(), before)
        self.path.write_bytes(raw)
        with self.assertRaises(GuardError): self.release_money_halt(report, {"path": image["path"], "sha256": "0" * 64})
        self.assertEqual(self.path.read_bytes(), raw)

    def test_money_halt_amendment_chain_and_before_image_tampering_block_new_admission(self):
        raw, image, report = self.money_halt(); self.release_money_halt(report, image)
        saved = self.path.read_bytes()
        for field, value in (("original_stopped_reason", "provider request usage is unknown"),
                             ("checkpoint_sha256", "0" * 64), ("parent_reconciliation_sha256", "0" * 64)):
            data = json.loads(saved); data["billing_money_halt_reconciliations"][0][field] = value
            self.path.write_text(_canonical(data)); self.path.chmod(0o600)
            with self.assertRaises(GuardError): self.checked()
        self.path.write_bytes(saved); Path(image["path"]).write_bytes(raw + b"\n")
        with self.assertRaises(GuardError): self.checked()

    def test_actual_25_dollars_cannot_release_the_stale_money_halt(self):
        self.install()
        data = json.loads(self.path.read_bytes());model = next(iter(self.policy["models"]))
        template = copy.deepcopy(next(iter(data["requests"].values())))
        for number, prompt in enumerate((1024, 1024, 347), 20):
            item = copy.deepcopy(template); item.update(prompt_tokens=prompt, completion_tokens=5,
                charged_nano_usd=_charge(self.policy["models"][model], prompt, 5))
            data["requests"][f"{number:032x}"] = item
        data["stopped_reason"] = "money reservation would exceed the approved cap"
        self.path.write_text(_canonical(data)); self.path.chmod(0o600); raw=self.path.read_bytes()
        with self.assertRaises(GuardError):
            self.release_money_halt(self.subsequent_report(25_000_000_000,"exhausted"), self.halt_image(raw))
        self.assertEqual(self.path.read_bytes(), raw)

    def test_only_exact_factory_guard_money_reason_is_released_with_unchanged_usage_and_before_image(self):
        raw, image, report = self.money_halt(); self.release_money_halt(report, image)
        guard = json.loads(self.path.read_bytes())
        factory = dict(tokens=12345, turns={"pm": 3}, token_threads={"thread": 100},
            started_epoch=guard["started_epoch"], room_ids=["same-room"],
            stopped_reason="Request budget guard blocked: Featherless request guard is persistently stopped; reconciliation is required.")
        before = self.halt_image(_canonical(factory).encode(), "factory-before.json")
        after = reconcile_factory_money_halt(factory, guard, before_image=before)
        self.assertIsNone(after["stopped_reason"])
        self.assertEqual({k:v for k,v in after.items() if k not in ("stopped_reason","billing_money_halt_reconciliations")},
            {k:v for k,v in factory.items() if k!="stopped_reason"})
        self.assertEqual(after["billing_money_halt_reconciliations"][0]["before_factory_ledger"], before)
        self.assertEqual(factory["stopped_reason"], "Request budget guard blocked: Featherless request guard is persistently stopped; reconciliation is required.")
        for reason in ("unknown paid usage", "unsafe permission", factory["stopped_reason"] + "; unknown usage"):
            other = copy.deepcopy(factory); other["stopped_reason"] = reason
            with self.assertRaises(GuardError): reconcile_factory_money_halt(other, guard, before_image=before)
        self.append_settled(20)
        newer_guard = json.loads(self.path.read_bytes())
        with self.assertRaises(GuardError): reconcile_factory_money_halt(factory, newer_guard, before_image=before)


if __name__ == "__main__":
    unittest.main()
