import json
from pathlib import Path
import tempfile
import unittest

from factorykit.common import canonical, digest, write_json
from factorykit.status import current_status
from factorykit.source_snapshot import SOURCE_FILES, source_inventory


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"paths": {k:str(self.root/k) for k in ("runs", "factory", "result", "rehearsal")},
                       "band":{"judged_room_id":"room", "rehearsal_room_id":"practice"},
                       "budgets":{"billing_mode":"subscription_only"}}
        self.runs = self.root/"runs"; self.factory = self.root/"factory"; self.factory.mkdir()
        self.runtime = self.runs/"runtime"
        for name in SOURCE_FILES:
            path = self.factory/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("input")
        self.runner = lambda *args, **kwargs: {"exit_code":0, "stdout":"a"*40+"\n"}

    def report(self): return current_status(self.config, runner=self.runner)

    def test_persisted_stop_wins_over_readme_and_does_not_leak_owner_token(self):
        write_json(self.runtime/"owner.json", {"status":"stopped", "stop_reason":"workflow_blocked", "token":"private-marker", "workflow":{"state":"blocked", "active_turn_ids":[], "unresolved_incident_ids":["a"]}})
        (self.runs/"README.md").write_text("RUNNING everything passed")
        report = self.report()
        self.assertEqual(report["runtime"]["persisted_status"], "stopped")
        self.assertEqual(report["runtime"]["workflow_state"], "blocked")
        self.assertEqual(report["runtime"]["stop_reason"], "workflow_blocked")
        self.assertNotIn("private-marker", json.dumps(report))
        self.assertEqual(report["runtime"]["process_liveness"], "not_checked")

    def test_missing_evidence_remains_unknown_and_read_does_not_write(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        report = self.report()
        self.assertEqual(report["runtime"]["persisted_status"], "unknown")
        self.assertEqual(report["source"]["state"], "freeze_missing_or_invalid")
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))

    def test_source_drift_and_config_drift_are_reported_separately(self):
        path = self.factory/"factorykit/runtime.py"; path.parent.mkdir(); path.write_text("frozen")
        files, errors = source_inventory(self.config); self.assertFalse(errors)
        write_json(self.runs/"freeze/latest.json", {"files":files, "configuration_sha256":digest(canonical(self.config))})
        self.assertEqual(self.report()["source"]["state"], "disk_matches_freeze")
        path.write_text("changed")
        report = self.report()
        self.assertEqual(report["source"]["changed_files"], ["factorykit/runtime.py"])
        self.assertTrue(report["source"]["configuration_matches_freeze"])
        self.assertEqual(report["source"]["loaded_process_bytes"], "not_established")

    def test_accepted_queue_is_not_promoted_into_verified_product_gate(self):
        write_json(self.root/"result/planning/queue.json", [{"id":"gate", "state":"ACCEPTED", "requirements":"private payload"}])
        product = self.report()["product"]
        self.assertEqual(product["items"][0]["state"], "ACCEPTED")
        self.assertEqual(product["acceptance"], "not_independently_verified_by_status")
        self.assertNotIn("private payload", json.dumps(product))

    def test_historical_observations_cannot_become_current_rehearsal(self):
        write_json(self.runs/"readiness/observations.json", {"configuration_sha256":digest(canonical(self.config)), "observations":[{"id":"rehearsal", "historical_provenance":{}, "observed_at":"2020-01-01", "status":"PASS"}]})
        report = self.report()["rehearsal"]
        self.assertEqual(report["historical_observation_count"], 1)
        self.assertEqual(report["live_current_rehearsal"], "not_established_by_observation_metadata")

    def test_alternative_session_ledger_and_rehearsal_repository(self):
        self.config["budgets"] = {"billing_mode":"spend_cap", "accounting_scope":"session"}
        write_json(self.runtime/"budget-session.json", {"tokens":17, "room_stopped_reasons":{"practice":"practice stopped"}})
        called = []
        def runner(argv, cwd, **kwargs):
            called.append(cwd); return {"exit_code":1, "stdout":""}
        report = current_status(self.config, mode="rehearsal", runner=runner)
        self.assertEqual(report["accounting"]["reported_tokens"], 17)
        self.assertEqual(report["runtime"]["room_stop_reason"], "practice stopped")
        self.assertEqual(called, [self.root/"rehearsal"])

    def test_new_source_file_is_detected_and_invalid_snapshot_is_reported(self):
        files, errors = source_inventory(self.config); self.assertFalse(errors)
        write_json(self.runs/"freeze/latest.json", {"files":files})
        path = self.factory/"factorykit/new.py"; path.parent.mkdir(); path.write_text("added")
        write_json(self.runtime/"owner.json", {"source_snapshot":{"root":"/missing", "manifest_sha256":"a"*64}})
        report = self.report()["source"]
        self.assertIn("factorykit/new.py", report["changed_files"])
        self.assertEqual(report["recorded_snapshot"]["state"], "invalid_or_missing")


if __name__ == "__main__": unittest.main()
