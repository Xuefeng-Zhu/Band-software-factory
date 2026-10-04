"""Offline accounting-only room retirement; never touch live state or services."""
import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import yaml

from factorykit.budgets import persisted_budget_blockers, room_scope
from factorykit.common import FactoryError, load_config
from factorykit.runtime import (BudgetLedger, GateError, RoomPreprocessor, STAGE_STOP,
                                adapter_config, recovery_record, session_ledger)

FACTORY = Path(__file__).resolve().parents[1]
TOY = "00000000-0000-4000-8000-000000000001"
OLD = "00000000-0000-4000-8000-000000000002"
NEW = "00000000-0000-4000-8000-000000000003"
HUMAN = "00000000-0000-4000-8000-000000000099"


class ArchivedRoomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = yaml.safe_load((FACTORY / "config/factory.example.yaml").read_text())
        self.config["paths"]["factory"] = str(FACTORY)
        for name in ("runs", "rehearsal", "result"):
            path = self.root / name
            path.mkdir()
            self.config["paths"][name] = str(path)
        self.config["runtime"].pop("docker_host", None)
        self.config["runtime"].pop("permission_profile", None)
        self.config["band"].update(rehearsal_room_id=TOY, judged_room_id=NEW, archived_room_ids=[OLD])
        for i, seat in enumerate(self.config["seats"]):
            seat["agent_id"] = f"00000000-0000-4000-8000-{i+10:012d}"
            seat["mandate"] = str(FACTORY / "mandates" / f"factory-{seat['id']}.md")
        self.config["budgets"].update(billing_mode="subscription_only", approved=True,
            api_billing_allowed=False, paid_provisioning_allowed=False, spend_cap_usd=None,
            max_active_seats=1, max_total_tokens=100000000, max_turns_per_seat=100,
            turn_timeout_seconds=10, stage_timeout_seconds=30, overall_timeout_seconds=100)
        self.path = self.root / "runs/runtime/budget-subscription.json"
        self.path.parent.mkdir()
        self.data = {"room_id": None, "room_ids": sorted([TOY, OLD]),
            "started_epoch": 100, "turns": {"pm": 48, "architect": 7}, "tokens": 17365225,
            "token_threads": {OLD + ":pm:t": 528741, TOY + ":pm:t": 952004},
            "room_started_epochs": {TOY: 100, OLD: 140},
            "room_turns": {TOY: {"pm": 47, "architect": 7}, OLD: {"pm": 1}},
            "room_stopped_reasons": {TOY: STAGE_STOP, OLD: "retained previous outcome"},
            "stopped_reason": None, "updated_at": "preserved",
            "recovery_seen_events": {"old": ["event"]}, "recovery_membership_attempts": {"old": 1}}
        self.clock = patch("factorykit.runtime.time.time", return_value=150)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def save(self, *, reconciled=False):
        data = copy.deepcopy(self.data)
        if reconciled:
            data["room_ids"] = sorted([TOY, OLD, NEW])
        self.path.write_text(json.dumps(data, indent=2) + "\n")
        return self.path.read_bytes()

    def test_scope_is_exact_union_without_mutating_config(self):
        before = copy.deepcopy(self.config)
        self.assertEqual(room_scope(self.config), ([TOY, NEW], sorted([TOY, OLD, NEW])))
        self.assertEqual(self.config, before)
        self.config["band"].pop("archived_room_ids")
        self.assertEqual(room_scope(self.config), ([TOY, NEW], sorted([TOY, NEW])))

    def test_archived_ids_require_list_unique_canonical_uuids_and_no_active_overlap(self):
        for value in (None, OLD, [OLD, OLD], [TOY], [NEW], [""], ["alias"], [OLD.replace("-", "")], [1], [{}]):
            with self.subTest(value=value):
                self.config["band"]["archived_room_ids"] = value
                with self.assertRaises(ValueError):
                    room_scope(self.config)

    def test_config_loader_rejects_invalid_archive_field(self):
        path = self.root / "config.yaml"
        for value in ([OLD], [TOY], None):
            self.config["band"]["archived_room_ids"] = value
            path.write_text(yaml.safe_dump(self.config))
            if value == [OLD]:
                self.assertEqual(load_config(path)["band"]["archived_room_ids"], value)
            else:
                with self.assertRaisesRegex(FactoryError, "archived_room_ids"):
                    load_config(path)

    def test_no_automatic_scope_extension_and_failure_is_byte_unchanged(self):
        before = self.save()
        stamp = self.path.stat().st_mtime_ns
        with self.assertRaisesRegex(GateError, "scope changed"):
            session_ledger(self.config, "judged")
        self.assertTrue(persisted_budget_blockers(self.config, now=150))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.stat().st_mtime_ns, stamp)

    def test_explicit_append_preserves_all_history_and_charges_new_work_cumulatively(self):
        self.save(reconciled=True)
        before = json.loads(self.path.read_text())
        ledger = session_ledger(self.config, "judged")
        self.assertEqual({k:v for k,v in ledger.data.items() if k != "updated_at"},
                         {k:v for k,v in before.items() if k != "updated_at"})
        self.assertIsNone(ledger.reason())
        self.assertTrue(ledger.reserve("pm"))
        ledger.record("pm", {"codex_thread_id": "t", "codex_total_tokens": 50})
        self.assertEqual(ledger.data["tokens"], before["tokens"] + 50)
        self.assertEqual(ledger.data["turns"]["pm"], 49)
        self.assertEqual(ledger.data["room_started_epochs"], {TOY: 100, OLD: 140, NEW: 150})
        self.assertEqual(ledger.data["started_epoch"], 100)
        for key in ("room_stopped_reasons", "recovery_seen_events", "recovery_membership_attempts"):
            self.assertEqual(ledger.data[key], before[key])
        self.assertEqual(ledger.data["token_threads"][OLD + ":pm:t"], 528741)
        self.assertEqual(ledger.data["token_threads"][NEW + ":pm:t"], 50)
        self.assertEqual(ledger.semaphore._value, 1)

    def test_read_only_inspector_keeps_archived_scope_and_original_deadline(self):
        before = self.save(reconciled=True)
        stamp = self.path.stat().st_mtime_ns
        self.assertEqual(persisted_budget_blockers(self.config, now=199.999), [])
        self.assertIn("Cumulative overall time budget exhausted.", persisted_budget_blockers(self.config, now=200))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.stat().st_mtime_ns, stamp)
        with patch("factorykit.runtime.time.time", return_value=200):
            ledger = session_ledger(self.config, "judged")
            self.assertEqual(ledger.reason(), "overall time budget exhausted")
            self.assertFalse(ledger.reserve("qa"))

    def test_global_halts_and_tokens_and_seat_caps_still_defeat_new_room(self):
        for changes, expected in (({"stopped_reason": "existing stop"}, "existing stop"),
                ({"tokens": 100000000}, "observed token budget exhausted"),
                ({"turns": {"pm": 100}}, "turn budget exhausted for pm")):
            with self.subTest(changes=changes):
                original = copy.deepcopy(self.data)
                self.data.update(changes)
                self.save(reconciled=True)
                ledger = session_ledger(self.config, "judged")
                self.assertEqual(ledger.reason("pm"), expected)
                self.assertFalse(ledger.reserve("pm"))
                self.assertTrue(persisted_budget_blockers(self.config, now=150))
                self.data = original

    def test_dropping_archive_or_persisted_history_room_is_rejected(self):
        for change_config in (True, False):
            self.config["band"]["archived_room_ids"] = [OLD]
            self.save(reconciled=True)
            if change_config:
                self.config["band"]["archived_room_ids"] = []
            else:
                data = json.loads(self.path.read_text()); data["room_ids"].remove(OLD)
                self.path.write_text(json.dumps(data))
            before = self.path.read_bytes()
            with self.assertRaises(GateError):
                session_ledger(self.config, "judged")
            self.assertTrue(persisted_budget_blockers(self.config, now=150))
            self.assertEqual(self.path.read_bytes(), before)

    def test_missing_ledger_cannot_reset_archive_but_initial_rehearsal_works(self):
        for mode in ("rehearsal", "judged"):
            with self.assertRaisesRegex(GateError, "no reset"):
                session_ledger(self.config, mode)
        self.assertTrue(persisted_budget_blockers(self.config, now=150))
        self.assertFalse(self.path.exists())
        self.config["band"].pop("archived_room_ids")
        self.assertEqual(persisted_budget_blockers(self.config, now=150), [])
        self.assertIsNone(session_ledger(self.config, "rehearsal").data["started_epoch"])

    def test_archived_room_cannot_become_active_through_ledger_or_sdk_resolver(self):
        self.save(reconciled=True)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(GateError, "accounting-only"):
            BudgetLedger(self.config["budgets"], self.path, OLD, allowed_rooms=[TOY, OLD, NEW], active_rooms=[TOY, NEW])
        self.assertEqual(self.path.read_bytes(), before)
        conf = adapter_config(self.config, self.config["seats"][0], "judged")
        self.assertEqual(conf.workspace_for_room(NEW), str((self.root / "result").resolve()))
        for room in (TOY, OLD):
            with self.assertRaises(GateError):
                conf.workspace_for_room(room)
        from band.platform.event import MessageEvent
        guard = RoomPreprocessor(NEW)
        guard.default.process = AsyncMock()
        self.assertIsNone(asyncio.run(guard.process(None, MessageEvent(room_id=OLD), "pm")))
        guard.default.process.assert_not_awaited()
        with self.assertRaises(GateError):
            session_ledger(self.config, OLD)

    def test_rehearsal_recovery_accepts_cumulative_archive_without_reactivating_it(self):
        self.save(reconciled=True)
        record = recovery_record(self.config, json.loads(self.path.read_text()), 20, HUMAN, "Synthetic explicit approval", created=150)
        self.assertEqual(record["room_id"], TOY)
        self.assertEqual(record["original_started_epoch"], 100)
        ledger = session_ledger(self.config, "rehearsal", recovery=record)
        self.assertIsNone(ledger.reason("pm"))
        with self.assertRaises(GateError):
            session_ledger(self.config, "judged", recovery=record)


if __name__ == "__main__":
    unittest.main()
