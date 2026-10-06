"""Readiness cannot turn historical rehearsal into current source proof."""
import copy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from factorykit.common import canonical, digest, write_json
from factorykit.source_snapshot import source_fingerprint
from factorykit.validation import doctor, observations, validate
import test_toolkit as toolkit


class RehearsalSourceTests(toolkit.Fixture):
    def setUp(self):
        super().setUp()
        self.source_hash = self.source_binding()
        self.path = Path(self.config["paths"]["runs"]) / "readiness/observations.json"
        self.proof = self.root / "synthetic-proof.json"
        self.proof.write_text('{"synthetic": true}\n')
        self.check = "toy_pm_assignment_peer_handoffs"
        self.record = {"id": self.check, "status": "PASS", "observed": True,
                       "observed_at": "2026-10-05T00:00:00Z", "observer": "synthetic utility test",
                       "factory_source_sha256": self.source_hash,
                       "evidence": [{"path": str(self.proof), "sha256": digest(self.proof)}]}
        self.report = {"configuration_sha256": digest(canonical(self.config)),
                       "source_lock_sha256": digest(Path(self.config["paths"]["factory"]) / "config/source-lock.json"),
                       "factory_source_sha256": self.source_hash, "observations": [self.record]}
        self.save_report()

    def save_report(self):
        write_json(self.path, self.report)

    def test_fresh_matching_source_retains_hash_verified_observation(self):
        records, _ = observations(self.config)
        self.assertEqual([row["id"] for row in records], [self.check])

    def test_historical_unbound_report_fails_without_rewriting_evidence(self):
        self.report.pop("factory_source_sha256")
        self.record.pop("factory_source_sha256")
        self.save_report()
        original = self.path.read_bytes()
        records, blockers = observations(self.config)
        self.assertEqual(records, [])
        self.assertTrue(any("stale or missing factory source binding" in value for value in blockers))
        self.assertEqual(self.path.read_bytes(), original)

    def test_report_cannot_rebind_historical_observations(self):
        self.record["factory_source_sha256"] = "a" * 64
        self.save_report()
        records, blockers = observations(self.config)
        self.assertEqual(records, [])
        self.assertIn(f"Observed readiness evidence has a stale or missing factory source binding: {self.check}", blockers)

    def test_source_edits_additions_and_removals_invalidate_saved_rehearsal(self):
        root = Path(self.config["paths"]["factory"])
        path = root / "protocols/collaboration.md"
        path.parent.mkdir()
        path.write_text("Original standing protocol.\n")
        current = source_fingerprint(self.config)
        self.report["factory_source_sha256"] = current
        self.record["factory_source_sha256"] = current
        self.save_report()
        path.write_text("Changed standing protocol.\n")
        self.assertEqual(observations(self.config)[0], [])
        path.write_text("Original standing protocol.\n")
        self.assertTrue(observations(self.config)[0])
        addition = root / "factorykit/added.py"
        addition.parent.mkdir()
        addition.write_text("pass\n")
        self.assertEqual(observations(self.config)[0], [])
        addition.unlink()
        path.unlink()
        self.assertEqual(observations(self.config)[0], [])

    def test_source_inventory_error_blocks_all_observations(self):
        (Path(self.config["paths"]["factory"]) / "uv.lock").unlink()
        records, blockers = observations(self.config)
        self.assertEqual(records, [])
        self.assertTrue(any("Cannot verify factory source" in value for value in blockers))

    def test_selected_profile_mandate_edit_invalidates_source_binding(self):
        profile = Path(self.config["paths"]["runs"]) / "selected"
        profile.mkdir()
        shutil.copytree(Path(self.config["paths"]["factory"]) / "mandates", profile / "mandates")
        self.config["artifacts"] = {"mandates": str(profile / "mandates")}
        for seat in self.config["seats"]:
            seat["mandate"] = str(profile / "mandates" / Path(seat["mandate"]).name)
        current = source_fingerprint(self.config)
        self.report["configuration_sha256"] = digest(canonical(self.config))
        self.report["factory_source_sha256"] = current
        self.record["factory_source_sha256"] = current
        self.save_report()
        self.assertTrue(observations(self.config)[0])
        Path(self.config["seats"][0]["mandate"]).write_text("Changed selected role instructions.\n")
        self.assertNotEqual(source_fingerprint(self.config), current)
        self.assertEqual(observations(self.config)[0], [])

    def test_doctor_does_not_promote_stale_pass(self):
        self.record["id"] = "permissions_agent_write_git"
        self.record.pop("factory_source_sha256")
        self.save_report()
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "synthetic", "stderr": ""}):
            result = doctor(self.config)
        status = {row["id"]: row["status"] for row in result["checks"]}
        self.assertEqual(status["permissions_agent_write_git"], "NOT_TESTED")
        self.assertEqual(result["factory_source_sha256"], self.source_hash)

    def test_duplicate_or_malformed_observation_list_is_blocked(self):
        for entries in ([self.record, copy.deepcopy(self.record)], None, {}):
            with self.subTest(entries=entries):
                self.report["observations"] = entries
                self.save_report()
                self.assertEqual(observations(self.config)[0], [])


class ToyExportSourceTests(unittest.TestCase):
    def test_current_check_cannot_use_export_with_stale_source_binding(self):
        fixture = toolkit.ToyFinishLoopTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.export["factory_source_sha256"] = "a" * 64
        path = Path(fixture.config["paths"]["runs"]) / "readiness/observations.json"
        saved = json.loads(path.read_text())
        saved["observations"] = [fixture.export, fixture.check]
        write_json(path, saved)
        self.assertEqual(fixture.accepted(), set())


class ProgressReadinessTests(toolkit.Fixture):
    def validation(self):
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]", "stderr": ""}):
            return validate(self.config, check_sources=False)

    def policy(self, executable):
        return {"milestones": [{"id": "first-runnable", "max_turns": 10, "max_seconds": 120,
                                "command": [str(executable), "--synthetic-test"],
                                "timeout_seconds": 10, "max_attempts": 2}]}

    def test_legacy_absence_is_a_launch_blocker_without_configuration_error(self):
        report = self.validation()
        self.assertIn("Fresh sessions require a finite runnable-checkpoint progress policy", report["launch_blockers"])
        self.assertFalse(any("progress" in str(value).lower() for value in report["errors"]))
        self.assertNotIn("progress", self.config)

    def test_invalid_progress_policy_is_a_launch_blocker(self):
        self.config["progress"] = {"milestones": []}
        report = self.validation()
        self.assertTrue(any(value.startswith("Progress policy is invalid:") for value in report["launch_blockers"]))

    def test_missing_or_nonexecutable_checkpoint_blocks_launch(self):
        executable = self.root / "synthetic-checkpoint"
        self.config["progress"] = self.policy(executable)
        self.assertIn("Configure each reviewed checkpoint executable before launching", self.validation()["launch_blockers"])
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o644)
        self.assertIn("Configure each reviewed checkpoint executable before launching", self.validation()["launch_blockers"])
        executable.chmod(0o755)
        self.assertNotIn("Configure each reviewed checkpoint executable before launching", self.validation()["launch_blockers"])
