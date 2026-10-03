"""Offline recovery authority/accounting tests. Never operate real state or seats."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import patch
import yaml

from factorykit.common import canonical, digest
from factorykit.runtime import (
    BudgetLedger, GateError, STAGE_STOP, cmd_authorize_recovery,
    load_recovery, recovery_digest, recovery_path, recovery_record,
    save_json, session_ledger, start_supervisor, state_dir,
)

FACTORY = Path(__file__).resolve().parents[1]
NOW = 20000.0
HUMAN = "00000000-0000-0000-0000-000000000099"


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = yaml.safe_load((FACTORY / "config/factory.example.yaml").read_text())
        self.config["paths"].update(runs=self.temp.name, factory=str(FACTORY))
        self.config["band"].update(rehearsal_room_id="rehearsal", judged_room_id="judged")
        self.config["budgets"].update(approved=True, billing_mode="subscription_only", spend_cap_usd=None,
            api_billing_allowed=False, paid_provisioning_allowed=False, max_active_seats=1,
            stage_timeout_seconds=14400, overall_timeout_seconds=28800, max_total_tokens=100000000,
            max_turns_per_seat=100)
        for index, seat in enumerate(self.config["seats"]):
            seat["agent_id"] = f"00000000-0000-0000-0000-{index:012d}"
        self.data = {"room_ids": ["judged", "rehearsal"], "room_id": None,
            "started_epoch": 1000.0, "room_started_epochs": {"rehearsal": 1000.0},
            "room_stopped_reasons": {"rehearsal": STAGE_STOP}, "stopped_reason": None,
            "turns": {"pm": 43, "architect": 4}, "tokens": 16391221,
            "room_turns": {"rehearsal": {"pm": 43, "architect": 4}},
            "token_threads": {"rehearsal:pm:old": 952004}, "updated_at": "before"}
        self.path = state_dir(self.config) / "budget-subscription.json"
        save_json(self.path, self.data)
        self.clock = patch("factorykit.runtime.time.time", return_value=NOW)
        self.clock_mock = self.clock.start()
        self.addCleanup(self.clock.stop)

    def make(self, duration=600):
        return recovery_record(self.config, self.data, duration, HUMAN, "Explicit approval message 123")

    def save_allowance(self):
        record = self.make()
        save_json(recovery_path(self.config, record["id"]), record)
        return record

    def test_manifest_is_exact_and_does_not_mutate_ledger(self):
        before = self.path.read_bytes()
        record = self.make()
        self.assertEqual(record["seats"], {s["id"]: s["agent_id"] for s in self.config["seats"] if s["id"] in ("pm", "architect")})
        self.assertEqual(record["configuration_sha256"], digest(canonical(self.config)))
        self.assertEqual(record["ledger_sha256"], recovery_digest(self.data))
        self.assertEqual(record["expires_epoch"], NOW + 600)
        self.assertEqual(record["original_room_stop_reason"], STAGE_STOP)
        self.assertEqual(self.path.read_bytes(), before)

    def test_authorization_constraints_fail_closed(self):
        for duration in (0, 601, True, 600.0):
            with self.subTest(duration=duration), self.assertRaises(GateError):
                self.make(duration)
        for operator, approval in (("bad", "yes"), (self.config["seats"][0]["agent_id"], "yes"), (HUMAN, " ")):
            with self.subTest(operator=operator), self.assertRaises(GateError):
                recovery_record(self.config, self.data, 60, operator, approval)
        for mutate in (
            lambda: self.data.update(stopped_reason="observed token budget exhausted"),
            lambda: self.data["room_stopped_reasons"].update(rehearsal="outer turn deadline exceeded"),
            lambda: self.data.update(tokens=100000000),
            lambda: self.data["turns"].update(pm=100),
            lambda: self.data["room_started_epochs"].update(rehearsal=NOW),
            lambda: self.config["budgets"].update(max_active_seats=2),
            lambda: self.config["budgets"].update(approved=False),
        ):
            original_config, original_data = copy.deepcopy(self.config), copy.deepcopy(self.data)
            mutate()
            with self.assertRaises(GateError):
                self.make()
            self.config, self.data = original_config, original_data
        self.clock_mock.return_value = 29800.0
        with self.assertRaises(GateError):
            self.make()

    def test_load_binds_config_ledger_and_expiry(self):
        record = self.save_allowance()
        self.assertEqual(load_recovery(self.config, record["id"]), record)
        self.data["updated_at"] = "cosmetic"
        save_json(self.path, self.data)
        self.assertEqual(load_recovery(self.config, record["id"]), record)
        self.data["tokens"] += 1
        save_json(self.path, self.data)
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"])
        self.data["tokens"] -= 1
        save_json(self.path, self.data)
        self.config["budgets"]["max_total_tokens"] += 1
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"])
        self.config["budgets"]["max_total_tokens"] -= 1
        self.clock_mock.return_value = record["expires_epoch"]
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"])

    def test_remaining_valid_window_does_not_restart_full_duration(self):
        self.clock_mock.return_value = 29199.0
        record = self.save_allowance()
        self.clock_mock.return_value = 29798.0
        self.assertEqual(load_recovery(self.config, record["id"]), record)
        self.clock_mock.return_value = 29799.0
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"])

    def test_claim_is_single_use_bound_to_token_and_file(self):
        record = self.save_allowance()
        path = recovery_path(self.config, record["id"])
        claim = recovery_path(self.config, record["id"], claim=True)
        save_json(claim, {"owner_token": "owned", "allowance_sha256": digest(path)})
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"])
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"], "wrong")
        self.assertEqual(load_recovery(self.config, record["id"], "owned"), record)
        record["approval_reference"] += " edited"
        save_json(path, record)
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"], "owned")

    def test_normal_start_remains_halted_and_recovery_does_not_clear_it(self):
        normal = session_ledger(self.config, "rehearsal")
        self.assertEqual(normal.reason(), STAGE_STOP)
        self.assertFalse(normal.reserve("pm"))
        original = copy.deepcopy(normal.data)
        record = self.make()
        recovery = session_ledger(self.config, "rehearsal", record)
        self.assertEqual(recovery.semaphore._value, 1)
        self.assertIsNone(recovery.reason("pm"))
        self.assertFalse(recovery.reserve("backend"))
        self.assertTrue(recovery.reserve("pm"))
        recovery.record("pm", {"codex_thread_id": "fresh", "codex_total_tokens": 20})
        self.assertEqual(recovery.data["tokens"], original["tokens"] + 20)
        self.assertEqual(recovery.data["turns"]["pm"], 44)
        for key in ("started_epoch", "room_started_epochs", "room_stopped_reasons", "stopped_reason"):
            self.assertEqual(recovery.data[key], original[key])
        recovery.halt("recovery allowance expired")
        self.assertEqual(recovery.reason(), "recovery allowance expired")
        self.assertIsNone(recovery.data["stopped_reason"])
        self.assertEqual(session_ledger(self.config, "rehearsal").reason(), STAGE_STOP)
        with self.assertRaises(GateError):
            session_ledger(self.config, "judged", record)

    def test_same_event_cannot_reserve_twice_or_replay_after_restart(self):
        record = self.make()
        ledger = session_ledger(self.config, "rehearsal", record)
        msg = SimpleNamespace(id="one-event", sender_id=HUMAN, sender_type="User", message_type="text",
            created_at=datetime.fromtimestamp(NOW, timezone.utc), content=record["marker"] + " connectivity only")
        self.assertTrue(ledger.reserve_event("pm", msg))
        self.assertFalse(ledger.reserve_event("pm", msg))
        self.assertEqual(ledger.data["turns"]["pm"], 44)
        restarted = session_ledger(self.config, "rehearsal", record)
        self.assertFalse(restarted.reserve_event("pm", msg))
        self.assertEqual(restarted.data["turns"]["pm"], 44)
        self.clock_mock.return_value = record["expires_epoch"]
        msg.id = "late-event"
        self.assertFalse(restarted.reserve_event("pm", msg))

    def test_global_failures_always_win_over_stage_exception(self):
        ledger = session_ledger(self.config, "rehearsal", self.make())
        ledger.data["tokens"] = 100000000
        self.assertEqual(ledger.reason(), "observed token budget exhausted")
        ledger.data["tokens"] = 0
        ledger.data["turns"]["pm"] = 100
        self.assertEqual(ledger.reason("pm"), "turn budget exhausted for pm")
        ledger.data["turns"]["pm"] = 43
        self.clock_mock.return_value = 29800.0
        self.assertEqual(ledger.reason(), "overall time budget exhausted")
        self.clock_mock.return_value = NOW
        ledger.data["stopped_reason"] = "some other failure"
        self.assertEqual(ledger.reason(), "some other failure")
        ledger.halt("observed token budget exhausted")
        self.assertEqual(ledger.data["stopped_reason"], "observed token budget exhausted")
        self.assertEqual(ledger.data["room_stopped_reasons"]["rehearsal"], STAGE_STOP)

    def test_authorize_requires_explicit_switch_and_stopped_owner(self):
        args = argparse.Namespace(loaded_config=self.config, config="unused", confirm_stage_limit_exception=False,
                                  duration_seconds=600, operator_id=HUMAN, approval_reference="approval")
        with self.assertRaises(GateError):
            cmd_authorize_recovery(args)
        self.assertFalse((state_dir(self.config) / "recovery").exists())
        args.confirm_stage_limit_exception = True
        with patch("factorykit.runtime.is_owned", return_value=True), self.assertRaises(GateError):
            cmd_authorize_recovery(args)
        self.assertFalse((state_dir(self.config) / "recovery").exists())

    def test_failed_spawn_consumes_claim_without_mutating_budget(self):
        record = self.save_allowance()
        args = argparse.Namespace(loaded_config=self.config, config="unused", mode="rehearsal")
        before = self.path.read_bytes()
        with patch("factorykit.runtime.require_ready"), patch("factorykit.runtime.subprocess.Popen", side_effect=OSError("inert failure")), self.assertRaises(OSError):
            start_supervisor(args, record["id"])
        claim = recovery_path(self.config, record["id"], claim=True)
        self.assertTrue(claim.is_file())
        self.assertEqual(claim.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(GateError):
            load_recovery(self.config, record["id"])


if __name__ == "__main__":
    unittest.main()
