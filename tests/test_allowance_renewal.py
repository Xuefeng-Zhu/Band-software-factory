"""Offline renewal retains liabilities, rooms, origins and request reservations."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from factorykit.allowance_renewal import (load_time_renewal, reconcile_accounting,
                                          renewal_durations, validate_renewal_config)
from factorykit.budgets import persisted_budget_blockers
from factorykit.common import FactoryError
from factorykit.featherless import MODEL_IDS
from factorykit.featherless_guard import _charge, _Ledger, _policy, GuardError
from factorykit import harnesses


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.now = int(time.time())
        self.origin = self.now - 40000.238457
        self.old_rooms = [str(uuid4()), str(uuid4())]
        self.new_rooms = [str(uuid4()), str(uuid4())]
        self.models = {model: {"id": model, "status": "active", "tool_use": True,
                "available_on_current_plan": True, "is_gated": False,
                "effective_context_length": 262144, "effective_max_completion_tokens": 32768,
                "pricing": {"prompt": "0.0000014" if index == 0 else "0.00000015",
                            "completion": "0.0000044" if index == 0 else "0.0000005",
                            "image": "0", "request": "0"}}
            for index, model in enumerate(MODEL_IDS)}
        metadata = {"status": "PASS", "blockers": [], "api_origin": "https://api.featherless.ai",
                    "billing_attestation_verified_by_caller": True, "plan": {"id": "plan"},
                    "credits": {"currency": "usd", "balance_nano_usd": 25000000000,
                                "reserved_nano_usd": 0, "available_nano_usd": 25000000000},
                    "models": self.models}
        meta = self.save(self.root / "readiness/models.json", metadata)
        guard = {"ledger": str(self.root / "runtime/featherless-requests.json"),
                 "model_metadata": meta["path"], "model_metadata_sha256": meta["sha256"],
                 "approved_credit_nano_usd": 25000000000, "max_total_tokens": 2000000,
                 "overall_timeout_seconds": 21600, "request_timeout_seconds": 900}
        self.base = {"paths": {"runs": str(self.root)},
                     "band": {"rehearsal_room_id": self.old_rooms[0], "judged_room_id": self.old_rooms[1]},
                     "budgets": {"approved": True, "billing_mode": "spend_cap", "accounting_scope": "session",
                                 "spend_cap_usd": 25, "max_active_seats": 1, "max_repairs": 2,
                                 "turn_timeout_seconds": 900, "stage_timeout_seconds": 21600,
                                 "overall_timeout_seconds": 21600, "max_turns_per_seat": 300,
                                 "max_total_tokens": 2000000, "ack_timeout_seconds": 60,
                                 "api_billing_allowed": True, "paid_provisioning_allowed": False},
                     "runtime": {"harness": "opencode", "model": "featherless/" + MODEL_IDS[0],
                                 "opencode_state_root": str(self.root / "fresh/opencode"),
                                 "featherless_budget_guard": guard,
                                 "opencode_provider": {"id": "featherless", "npm": "@ai-sdk/openai-compatible",
                                       "base_url": "https://api.featherless.ai/v1", "api_key_env": "UNREAD_KEY",
                                       "models": {k: {"id": k, "limit": {"context": 262144, "output": 32768}} for k in MODEL_IDS}}},
                     "seats": [{"id": role, "agent_id": str(uuid4()),
                                "model": "featherless/" + MODEL_IDS[1 if role in ("designer", "frontend", "qa") else 0]}
                               for role in ("pm", "architect", "designer", "backend", "frontend", "qa", "reviewer")]}
        self.factory = {"room_id": None, "room_ids": sorted(self.old_rooms), "started_epoch": self.origin,
                        "tokens": 24765, "turns": {"pm": 1, "designer": 1},
                        "token_threads": {self.old_rooms[0] + ":pm:old": 24765}, "stopped_reason": None,
                        "room_started_epochs": {self.old_rooms[0]: self.origin},
                        "room_turns": {self.old_rooms[0]: {"pm": 1, "designer": 1}}, "room_stopped_reasons": {}}
        policy = _policy(self.models, 25000000000, 2000000, 21600)
        self.guard = {"schema_version": 1, "policy": policy, "started_epoch": self.origin,
                      "stopped_reason": None, "requests": {}}
        for index, (model, prompt, completion) in enumerate(((MODEL_IDS[0], 5892, 124),
                (MODEL_IDS[0], 6293, 49), (MODEL_IDS[1], 5896, 118), (MODEL_IDS[1], 6290, 103))):
            m = policy["models"][model]
            self.guard["requests"][str(index + 1).zfill(32)] = {"model": model, "status": "settled",
                "output_ceiling": m["output_ceiling"], "reserved_tokens": m["input_ceiling"] + m["output_ceiling"],
                "reserved_nano_usd": _charge(m, m["input_ceiling"], m["output_ceiling"]),
                "prompt_tokens": prompt, "completion_tokens": completion,
                "charged_nano_usd": _charge(m, prompt, completion)}
        self.authority = {"schema_version": 1, "status": "APPROVED", "authorization_source": "direct_user_chat",
                          "user_answer": "approve and continue", "renewal_started_epoch": self.now,
                          "renewal_deadline_epoch": self.now + 21600, "renewed_seconds": 21600,
                          "original_factory_started_epoch": self.origin, "original_guard_started_epoch": self.origin,
                          "original_configuration": self.save(self.root / "before/config.json", self.base),
                          "original_factory_budget": self.save(self.root / "before/budget.json", self.factory),
                          "original_request_ledger": self.save(self.root / "before/requests.json", self.guard),
                          "active_room_ids": self.new_rooms,
                          "cumulative_room_ids": sorted(self.old_rooms + self.new_rooms),
                          "role_models": {s["id"]: s["model"] for s in self.base["seats"]}}
        self.ref = self.save(self.root / "renewal.json", self.authority)
        self.config = copy.deepcopy(self.base)
        self.config["band"].update(rehearsal_room_id=self.new_rooms[0], judged_room_id=self.new_rooms[1],
                                     archived_room_ids=self.old_rooms)
        duration = renewal_durations(self.authority)
        self.config["budgets"]["overall_timeout_seconds"] = duration["factory"]
        self.config["runtime"]["featherless_budget_guard"].update(
            overall_timeout_seconds=duration["guard"], time_renewal=self.ref)

    def save(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(data, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        path.chmod(0o600)
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}

    def test_reconciliation_preserves_all_cumulative_usage_and_starts(self):
        before = copy.deepcopy((self.factory, self.guard))
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        self.assertEqual((self.factory, self.guard), before)
        self.assertEqual(factory["started_epoch"], self.origin)
        self.assertEqual(guard["started_epoch"], self.origin)
        self.assertEqual(guard["requests"], self.guard["requests"])
        self.assertEqual(factory["tokens"], 24765)
        self.assertEqual(factory["turns"], {"pm": 1, "designer": 1})
        self.assertEqual(factory["room_started_epochs"], self.factory["room_started_epochs"])
        self.assertEqual(factory["room_ids"], sorted(self.old_rooms + self.new_rooms))
        ledger = _Ledger(self.root / "runtime/featherless-requests.json", guard["policy"])
        ledger.data = guard
        ledger._validate()
        self.assertEqual(ledger.totals()["observed_tokens"], 24765)
        self.assertEqual(ledger.totals()["charged_nano_usd"], 19758600)
        self.assertLessEqual(self.origin + guard["policy"]["overall_timeout_seconds"], self.now + 21600)
        self.assertGreater(self.origin + guard["policy"]["overall_timeout_seconds"], self.now + 21599)

    def test_production_inspectors_and_restart_retain_counts(self):
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        self.save(self.root / "runtime/budget-session.json", factory)
        self.save(self.root / "runtime/featherless-requests.json", guard)
        self.assertEqual(harnesses.featherless_guard_errors(self.config), [])
        self.assertEqual(persisted_budget_blockers(self.config, now=self.now + 1, require_existing=True), [])
        for _ in range(2):
            ledger = _Ledger(self.root / "runtime/featherless-requests.json", guard["policy"])
            ledger.open()
            self.assertEqual(ledger.totals()["observed_tokens"], 24765)
            self.assertEqual(len(ledger.data["requests"]), 4)
            ledger.close()
        self.assertTrue(any("time budget exhausted" in x for x in
                            persisted_budget_blockers(self.config, now=self.now + 21600)))

    def test_unreferenced_wider_policy_remains_forbidden(self):
        with self.assertRaises(GuardError):
            _policy(self.models, 25000000000, 2000000, 21601)

    def test_modified_authority_or_before_image_is_rejected(self):
        for reference in (self.ref, self.authority["original_factory_budget"],
                          self.authority["original_request_ledger"], self.authority["original_configuration"]):
            path = Path(reference["path"])
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaises(FactoryError):
                validate_renewal_config(self.config, now=self.now)
            path.write_bytes(original)

    def test_changed_live_accounting_is_not_silently_reconciled(self):
        factory = copy.deepcopy(self.factory)
        factory["tokens"] += 1
        with self.assertRaises(FactoryError):
            reconcile_accounting(self.config, factory, self.guard, self.models, now=self.now)

    def test_each_cap_and_model_assignment_is_immutable(self):
        changed = []
        for name in ("max_total_tokens", "max_active_seats", "turn_timeout_seconds", "max_repairs", "spend_cap_usd"):
            config = copy.deepcopy(self.config)
            config["budgets"][name] += 1
            changed.append(config)
        config = copy.deepcopy(self.config)
        config["seats"][0]["model"] = config["seats"][2]["model"]
        changed.append(config)
        for config in changed:
            with self.subTest(config=config["budgets"]):
                with self.assertRaises(FactoryError):
                    validate_renewal_config(config, now=self.now)

    def test_renewal_is_bound_to_fresh_rooms_and_existing_ledger(self):
        changes = []
        for name in ("rehearsal_room_id", "judged_room_id"):
            config = copy.deepcopy(self.config)
            config["band"][name] = str(uuid4())
            changes.append(config)
        config = copy.deepcopy(self.config)
        config["paths"]["runs"] = str(self.root / "new")
        changes.append(config)
        config = copy.deepcopy(self.config)
        config["runtime"]["featherless_budget_guard"]["ledger"] += ".new"
        changes.append(config)
        for config in changes:
            with self.assertRaises(FactoryError):
                validate_renewal_config(config, now=self.now)

    def test_original_epoch_cannot_be_reset_in_request_or_factory_ledger(self):
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        guard["started_epoch"] = self.now
        ledger = _Ledger(self.root / "guard.json", guard["policy"])
        ledger.data = guard
        with self.assertRaises(GuardError):
            ledger._validate()
        factory["started_epoch"] = self.now
        self.save(self.root / "runtime/budget-session.json", factory)
        self.assertTrue(persisted_budget_blockers(self.config, now=self.now + 1))

    def test_unknown_requests_and_non_time_stops_are_not_clearable(self):
        for target, field, value in (("original_request_ledger", "stopped_reason", "provider request usage is unknown"),
                                     ("original_factory_budget", "stopped_reason", "observed token budget exhausted")):
            authority = copy.deepcopy(self.authority)
            before = copy.deepcopy(self.guard if target == "original_request_ledger" else self.factory)
            before[field] = value
            authority[target] = self.save(self.root / (target + ".json"), before)
            ref = self.save(self.root / (target + "-renewal.json"), authority)
            with self.assertRaises(FactoryError):
                load_time_renewal(ref, now=self.now)
        authority = copy.deepcopy(self.authority)
        before = copy.deepcopy(self.guard)
        next(iter(before["requests"].values()))["status"] = "unknown"
        authority["original_request_ledger"] = self.save(self.root / "unknown.json", before)
        ref = self.save(self.root / "unknown-renewal.json", authority)
        with self.assertRaises(FactoryError):
            load_time_renewal(ref, now=self.now)

    def test_only_expired_time_stops_are_cleared_and_original_stop_is_preserved(self):
        self.factory["stopped_reason"] = self.guard["stopped_reason"] = "overall time budget exhausted"
        self.authority["original_factory_budget"] = self.save(self.root / "before/budget.json", self.factory)
        self.authority["original_request_ledger"] = self.save(self.root / "before/requests.json", self.guard)
        self.ref = self.save(self.root / "renewal.json", self.authority)
        self.config["runtime"]["featherless_budget_guard"]["time_renewal"] = self.ref
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        self.assertIsNone(factory["stopped_reason"])
        self.assertIsNone(guard["stopped_reason"])
        self.assertEqual(self.factory["stopped_reason"], "overall time budget exhausted")
        self.assertEqual(self.guard["stopped_reason"], "overall time budget exhausted")

    def test_approved_deadline_cannot_move_or_start_in_future(self):
        for key, value in (("renewal_deadline_epoch", self.now + 21601),
                           ("renewal_started_epoch", self.now + 1),
                           ("user_answer", "looks good"), ("renewed_seconds", 21601)):
            authority = copy.deepcopy(self.authority)
            authority[key] = value
            ref = self.save(self.root / (key + ".json"), authority)
            with self.assertRaises(FactoryError):
                load_time_renewal(ref, now=self.now)

    def test_renewal_file_permission_and_symlink_are_rejected(self):
        path = Path(self.ref["path"])
        path.chmod(0o644)
        with self.assertRaises(FactoryError):
            load_time_renewal(self.ref, now=self.now)
        path.chmod(0o600)
        link = self.root / "link.json"
        link.symlink_to(path)
        with self.assertRaises(FactoryError):
            load_time_renewal({"path": str(link), "sha256": self.ref["sha256"]}, now=self.now)

    def test_renewed_guard_reserves_once_and_persists_expiry_without_reset(self):
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        path = self.root / "runtime/featherless-requests.json"
        self.save(path, guard)
        ledger = _Ledger(path, guard["policy"])
        ledger.open()
        try:
            with patch("time.time", return_value=self.now + 1):
                key = ledger.reserve(MODEL_IDS[1], 16)
                ledger.settle(key, 100, 10)
            self.assertEqual(len(ledger.data["requests"]), 5)
            self.assertEqual(ledger.totals()["observed_tokens"], 24875)
            self.assertEqual(ledger.data["started_epoch"], self.origin)
            self.assertTrue(all(ledger.data["requests"][key] == value
                                for key, value in self.guard["requests"].items()))
            with patch("time.time", return_value=self.now + 21600):
                with self.assertRaises(GuardError):
                    ledger.reserve(MODEL_IDS[0], 16)
            self.assertEqual(len(ledger.data["requests"]), 5)
            self.assertEqual(ledger.data["stopped_reason"], "overall time budget exhausted")
        finally:
            ledger.close()
        reopened = _Ledger(path, guard["policy"])
        reopened.open()
        try:
            with self.assertRaises(GuardError):
                reopened.reserve(MODEL_IDS[0], 16)
            self.assertEqual(reopened.totals()["observed_tokens"], 24875)
        finally:
            reopened.close()

    def test_new_room_stage_starts_naturally_while_old_room_history_stays(self):
        from factorykit.runtime import BudgetLedger
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        path = self.root / "runtime/budget-session.json"
        self.save(path, factory)
        ledger = BudgetLedger(self.config["budgets"], path, self.new_rooms[0],
                              allowed_rooms=sorted(self.old_rooms + self.new_rooms), active_rooms=self.new_rooms)
        with patch("time.time", return_value=self.now + 1):
            self.assertTrue(ledger.reserve("pm"))
        self.assertEqual(ledger.data["started_epoch"], self.origin)
        self.assertEqual(ledger.data["room_started_epochs"][self.old_rooms[0]], self.origin)
        self.assertEqual(ledger.data["room_started_epochs"][self.new_rooms[0]], self.now + 1)
        self.assertEqual(ledger.data["turns"], {"pm": 2, "designer": 1})
        self.assertEqual(ledger.data["room_turns"][self.old_rooms[0]], {"pm": 1, "designer": 1})
        with patch("time.time", return_value=self.now + 21600):
            self.assertEqual(ledger.reason(), "overall time budget exhausted")
            self.assertFalse(ledger.reserve("pm"))
        self.assertEqual(ledger.data["turns"], {"pm": 2, "designer": 1})

    def test_distinct_original_factory_and_guard_epochs_use_independent_caps(self):
        guard_start = self.origin + 1.801934
        self.guard["started_epoch"] = guard_start
        self.authority["original_guard_started_epoch"] = guard_start
        self.authority["original_request_ledger"] = self.save(self.root / "before/requests.json", self.guard)
        self.ref = self.save(self.root / "renewal.json", self.authority)
        duration = renewal_durations(self.authority)
        self.config["runtime"]["featherless_budget_guard"].update(
            time_renewal=self.ref, overall_timeout_seconds=duration["guard"])
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        self.assertEqual(factory["started_epoch"], self.origin)
        self.assertEqual(guard["started_epoch"], guard_start)
        self.assertLess(duration["guard"], duration["factory"])
        self.assertEqual(harnesses.featherless_guard_errors(self.config), [])
        self.assertLessEqual(self.origin + duration["factory"], self.now + 21600)
        self.assertLessEqual(guard_start + duration["guard"], self.now + 21600)

    def test_restart_cannot_delete_paid_request_liabilities_even_with_valid_original_epoch(self):
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        self.save(self.root / "runtime/budget-session.json", factory)
        requests_path = self.root / "runtime/featherless-requests.json"
        for requests in ({}, {key: value for key, value in list(guard["requests"].items())[1:]}):
            changed = copy.deepcopy(guard)
            changed["requests"] = requests
            self.save(requests_path, changed)
            self.assertTrue(persisted_budget_blockers(self.config, now=self.now + 1, require_existing=True))
            ledger = _Ledger(requests_path, guard["policy"])
            with self.assertRaises(GuardError):
                ledger.open()
        changed = copy.deepcopy(guard)
        request = next(iter(changed["requests"].values()))
        request["prompt_tokens"] -= 1
        request["charged_nano_usd"] = _charge(guard["policy"]["models"][request["model"]],
                                             request["prompt_tokens"], request["completion_tokens"])
        self.save(requests_path, changed)
        self.assertTrue(persisted_budget_blockers(self.config, now=self.now + 1, require_existing=True))

    def test_restart_cannot_reduce_retained_factory_usage_turns_threads_or_room_history(self):
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        self.save(self.root / "runtime/featherless-requests.json", guard)
        path = self.root / "runtime/budget-session.json"
        changes = []
        for name, value in (("tokens", 0), ("turns", {}), ("token_threads", {}),
                             ("room_turns", {}), ("room_started_epochs", {})):
            data = copy.deepcopy(factory)
            data[name] = value
            changes.append(data)
        data = copy.deepcopy(factory)
        data["room_started_epochs"][self.old_rooms[0]] += 1
        changes.append(data)
        for data in changes:
            self.save(path, data)
            self.assertTrue(persisted_budget_blockers(self.config, now=self.now + 1, require_existing=True))

    def test_missing_original_ledgers_block_even_optional_rehearsal_checks_and_never_recreate_usage(self):
        from factorykit.runtime import session_ledger, GateError
        factory, guard = reconcile_accounting(self.config, self.factory, self.guard, self.models, now=self.now)
        factory_path = self.root / "runtime/budget-session.json"
        request_path = self.root / "runtime/featherless-requests.json"
        self.save(factory_path, factory)
        self.save(request_path, guard)
        request_path.unlink()
        self.assertTrue(persisted_budget_blockers(self.config, now=self.now + 1, require_existing=False))
        ledger = _Ledger(request_path, guard["policy"])
        with self.assertRaises(GuardError):
            ledger.open()
        self.assertFalse(request_path.exists())
        self.save(request_path, guard)
        factory_path.unlink()
        self.assertTrue(persisted_budget_blockers(self.config, now=self.now + 1, require_existing=False))
        with self.assertRaises(GateError):
            session_ledger(self.config, "rehearsal")
        self.assertFalse(factory_path.exists())
