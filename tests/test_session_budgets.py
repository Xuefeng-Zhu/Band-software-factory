"""Aggregate spend-cap accounting, with no provider calls or real run changes."""

import asyncio
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import yaml

from factorykit.budgets import (
    accounting_ledger_conflicts, budget_errors, budget_ledger_path,
    persisted_budget_blockers, session_accounting,
)
from factorykit.runtime import (
    AuditedTools, GateError, STAGE_STOP, accounted_adapter_turn, cmd_status,
    session_ledger,
)


class SessionBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        factory = Path(__file__).resolve().parents[1]
        self.config = yaml.safe_load((factory / "config/factory.example.yaml").read_text())
        self.config["paths"]["runs"] = str(self.root / "new-hermes-attempt")
        self.config["band"].update(rehearsal_room_id="rehearsal-new", judged_room_id="judged-new")
        self.config["band"].pop("archived_room_ids", None)
        self.config["budgets"].update(billing_mode="spend_cap", accounting_scope="session",
            spend_cap_usd=25, approved=True, max_active_seats=1, max_total_tokens=2000000,
            overall_timeout_seconds=21600, stage_timeout_seconds=1800,
            max_turns_per_seat=20, turn_timeout_seconds=180)
        self.path = budget_ledger_path(self.config)

    def record(self, ledger, seat, turn, tokens):
        ledger.record(seat, {"band_usage": {"input_tokens": tokens}},
                      harness="opencode", turn_id=turn)

    def test_explicit_scope_is_independent_of_provider_billing(self):
        self.assertEqual(budget_errors(self.config["budgets"]), [])
        self.assertTrue(session_accounting(self.config["budgets"]))
        self.assertEqual(self.path.name, "budget-session.json")
        legacy = copy.deepcopy(self.config)
        legacy["budgets"].pop("accounting_scope")
        self.assertFalse(session_accounting(legacy["budgets"]))
        self.assertEqual(budget_ledger_path(legacy, "rehearsal").name, "budget-rehearsal.json")
        subscription = copy.deepcopy(legacy)
        subscription["budgets"].update(billing_mode="subscription_only", spend_cap_usd=None,
                                      api_billing_allowed=False, paid_provisioning_allowed=False)
        self.assertTrue(session_accounting(subscription["budgets"]))
        self.assertEqual(budget_ledger_path(subscription).name, "budget-subscription.json")
        self.assertEqual(budget_errors(subscription["budgets"]), [])
        subscription["budgets"]["accounting_scope"] = "mode"
        self.assertTrue(budget_errors(subscription["budgets"]))
        for value in (True, None, "room", [], {}):
            with self.subTest(scope=value):
                self.assertTrue(budget_errors(dict(self.config["budgets"], accounting_scope=value)))

    def test_paid_verification_rehearsal_judged_share_origin_and_usage(self):
        with patch("time.time", return_value=100):
            verification = session_ledger(self.config, "rehearsal")
            self.assertIsNone(verification.data["started_epoch"])
            self.assertTrue(verification.reserve("pm"))
            self.record(verification, "pm", "verification-receipt", 50)
        with patch("time.time", return_value=120):
            rehearsal = session_ledger(self.config, "rehearsal")
            self.assertTrue(rehearsal.reserve("qa"))
            self.record(rehearsal, "qa", "rehearsal-receipt", 70)
            self.record(rehearsal, "pm", "verification-receipt", 50)
        with patch("time.time", return_value=150):
            judged = session_ledger(self.config, "judged")
            self.assertTrue(judged.reserve("pm"))
            self.record(judged, "pm", "judged-receipt", 80)
            restarted = session_ledger(self.config, "rehearsal")
            self.assertEqual(restarted.data["tokens"], 200)
            self.assertEqual(restarted.data["turns"], {"pm": 2, "qa": 1})
            self.assertEqual(restarted.data["started_epoch"], 100)
            self.assertEqual(restarted.data["room_started_epochs"], {"rehearsal-new": 100, "judged-new": 150})
            self.assertEqual(persisted_budget_blockers(self.config, now=150, require_existing=True), [])
        self.assertEqual(sorted(path.name for path in self.path.parent.glob("budget-*.json")), ["budget-session.json"])

    def test_verification_tokens_can_exhaust_the_whole_allowance(self):
        with patch("time.time", return_value=100):
            verification = session_ledger(self.config, "rehearsal")
            verification.reserve("pm")
            self.record(verification, "pm", "verification-receipt", 2000000)
            self.assertTrue(verification.stop.is_set())
            judged = session_ledger(self.config, "judged")
            self.assertFalse(judged.reserve("pm"))
            self.assertEqual(judged.data["tokens"], 2000000)
            self.assertEqual(judged.reason(), "observed token budget exhausted")
            self.assertTrue(persisted_budget_blockers(self.config, now=100, require_existing=True))

    def test_six_hour_deadline_cannot_restart_at_phase_transition(self):
        with patch("time.time", return_value=100):
            verification = session_ledger(self.config, "rehearsal")
            verification.reserve("pm")
            self.record(verification, "pm", "verification-receipt", 10)
        with patch("time.time", return_value=21699):
            judged = session_ledger(self.config, "judged")
            self.assertIsNone(judged.reason())
        with patch("time.time", return_value=21700):
            judged = session_ledger(self.config, "judged")
            self.assertEqual(judged.reason(), "overall time budget exhausted")
            self.assertFalse(judged.reserve("qa"))
            self.assertTrue(any("overall" in item for item in persisted_budget_blockers(self.config, now=21700)))
            self.assertEqual(judged.data["started_epoch"], 100)

    def test_stage_stop_stays_room_scoped_without_resetting_overall_clock(self):
        with patch("time.time", return_value=100):
            rehearsal = session_ledger(self.config, "rehearsal")
            rehearsal.reserve("pm")
        with patch("time.time", return_value=1900):
            rehearsal.halt(rehearsal.reason())
            self.assertEqual(rehearsal.data["room_stopped_reasons"], {"rehearsal-new": STAGE_STOP})
            judged = session_ledger(self.config, "judged")
            self.assertTrue(judged.reserve("qa"))
            self.assertEqual(judged.data["started_epoch"], 100)
            self.assertEqual(persisted_budget_blockers(self.config, now=1900), [])

    def test_missing_paid_verification_usage_stops_every_later_phase(self):
        async def scenario():
            ledger = session_ledger(self.config, "rehearsal")
            ledger.reserve("pm")
            wrapped = AuditedTools(SimpleNamespace(), ledger, "pm", self.root / "audit.jsonl",
                                   harness="opencode", turn_id="verification-receipt")
            await accounted_adapter_turn(AsyncMock(), None, wrapped)
            judged = session_ledger(self.config, "judged")
            self.assertFalse(judged.reserve("qa"))
            self.assertIn("usage was not reported", judged.reason())
            self.assertEqual(judged.data["tokens"], 0)
            self.assertEqual(judged.data["token_threads"], {})
            self.assertEqual(judged.data["turns"], {"pm": 1})
            self.assertTrue(persisted_budget_blockers(self.config, require_existing=True))
        asyncio.run(scenario())

    def test_conflicting_ledgers_block_without_creating_a_fresh_allowance(self):
        self.path.parent.mkdir(parents=True)
        for name in ("budget-rehearsal.json", "budget-judged.json", "budget-subscription.json"):
            with self.subTest(name=name):
                old = self.path.parent / name
                old.write_text('{"tokens": 123, "stopped_reason": "preserve"}')
                before = old.read_bytes()
                self.assertTrue(accounting_ledger_conflicts(self.config))
                self.assertTrue(persisted_budget_blockers(self.config))
                with self.assertRaises(GateError):
                    session_ledger(self.config, "judged")
                self.assertEqual(old.read_bytes(), before)
                self.assertFalse(self.path.exists())
                old.unlink()

    def test_removing_scope_cannot_hide_the_shared_spend_cap_ledger(self):
        ledger = session_ledger(self.config, "rehearsal")
        ledger.reserve("pm")
        self.record(ledger, "pm", "verification-receipt", 20)
        before = self.path.read_bytes()
        self.config["budgets"].pop("accounting_scope")
        with self.assertRaises(GateError):
            session_ledger(self.config, "judged")
        self.assertTrue(persisted_budget_blockers(self.config))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.path.parent / "budget-judged.json").exists())

    def test_legacy_spend_cap_keeps_its_existing_per_mode_behavior(self):
        self.config["budgets"].pop("accounting_scope")
        rehearsal = session_ledger(self.config, "rehearsal")
        rehearsal.reserve("pm")
        self.record(rehearsal, "pm", "legacy-receipt", 30)
        judged = session_ledger(self.config, "judged")
        self.assertEqual(judged.data["tokens"], 0)
        self.assertEqual(rehearsal.path.name, "budget-rehearsal.json")
        self.assertEqual(judged.path.name, "budget-judged.json")

    def test_new_attempt_never_reads_or_rewrites_separate_old_run_files(self):
        old = self.root / "old-local-run7/runtime/budget-subscription.json"
        old.parent.mkdir(parents=True)
        old.write_text('{"tokens": 90000000, "stopped_reason": "old run"}')
        before = old.read_bytes()
        ledger = session_ledger(self.config, "rehearsal")
        ledger.reserve("pm")
        self.record(ledger, "pm", "new-verification", 25)
        self.assertEqual(ledger.data["tokens"], 25)
        self.assertEqual(old.read_bytes(), before)

    def test_seat_status_reads_shared_ledger_for_judged_mode(self):
        ledger = session_ledger(self.config, "rehearsal")
        ledger.reserve("pm")
        self.record(ledger, "pm", "verification-receipt", 25)
        record = {"status": "stopped", "parent": {}, "token": "test", "mode": "judged"}
        output = io.StringIO()
        with patch("factorykit.runtime.read_registry", return_value=record), \
             patch("factorykit.runtime.is_owned", return_value=False), redirect_stdout(output):
            cmd_status(SimpleNamespace(loaded_config=self.config))
        self.assertEqual(json.loads(output.getvalue())["budget"]["tokens"], 25)


# Reuse the independent readiness fixture, which makes ledger construction and
# live network/process calls fail. Only its synthetic files can be modified.
from test_budget_readiness import BudgetReadinessFixture, ORIGIN
from factorykit.operations import freeze, launch_prepare
from factorykit.runtime import preflight_runtime


class SessionBudgetReadinessTests(BudgetReadinessFixture):
    def setUp(self):
        super().setUp()
        self.config["budgets"].update(billing_mode="spend_cap", accounting_scope="session",
            spend_cap_usd=25, overall_timeout_seconds=21600, max_total_tokens=2000000)
        self.path = budget_ledger_path(self.config)
        self.ready_files()
        self.before = self.save_ledger()

    def test_readonly_inspection_requires_existing_shared_ledger_for_judged(self):
        self.path.unlink()
        self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN, require_existing=True))
        self.assertFalse(self.path.exists())

    def test_judged_preflight_and_freeze_reject_spent_verification_allowance(self):
        self.data["tokens"] = 2000000
        before = self.save_ledger()
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 1):
            errors = preflight_runtime(self.config, "judged")
            frozen = freeze(self.config)
        self.assertTrue(any("token" in message for message in errors))
        self.assertEqual(frozen["status"], "BLOCKED_WITH_ACTIONS")
        self.assertEqual(self.path.read_bytes(), before)

    def test_ready_freeze_does_not_renew_six_hour_deadline_at_launch(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 21599):
            frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 21600):
            prepared = launch_prepare(self.config, "all", None)
        self.assertEqual(prepared["status"], "BLOCKED_WITH_ACTIONS")
        self.assertTrue(any("overall" in message for message in prepared["blockers"]))
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(self.path.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
