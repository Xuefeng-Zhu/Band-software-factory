"""Utility tests with synthetic specifications and fake process output.

These tests do not establish BAND integration, application behavior or rehearsal.
"""
from __future__ import annotations

import copy
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from factorykit.common import FactoryError, canonical, contains_secret, digest, load_config, redact, run_command, verify_sources, write_json
from factorykit.operations import harness, pristine_result, validate_launch_request
from factorykit.tasks import generate, verify_tasks
from factorykit.validation import doctor, observations, validate
from factorykit.workitems import validate_item


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory path ' quote ")
        self.root = Path(self.temp.name)
        paths = {name: str(self.root / name) for name in ("challenge", "factory", "rehearsal", "runs", "result")}
        for value in paths.values():
            Path(value).mkdir()
        self.config = {
            "schema_version": 1, "paths": paths,
            "runtime": {"python": sys.executable, "harness_python": sys.executable, "codex_command": str(self.root / "codex tool"), "browser_path": str(self.root / "browsers"),
                        "sandbox": "workspace-write", "approval_policy": "never", "model": "discovered-model"},
            "band": {"credentials_file": str(self.root / "private/config.yaml"), "rehearsal_room_id": None, "judged_room_id": None},
            "budgets": {"max_active_seats": 2, "max_repairs": 2, "turn_timeout_seconds": 30, "stage_timeout_seconds": 90,
                        "overall_timeout_seconds": 180, "max_turns_per_seat": 2, "max_total_tokens": 1000, "approved": False, "spend_cap_usd": None},
            "launch": {"mode": "all", "practice_mode": False, "registration_verified": False, "submission_open_verified": False}, "seats": []}
        mandates = Path(paths["factory"]) / "mandates"
        mandates.mkdir()
        for name in ("pm", "architect", "designer", "backend", "frontend", "qa", "reviewer"):
            mandate = mandates / f"factory-{name}.md"
            mandate.write_text("Harness: Codex test\nModel: discovered-model\nPurpose: verify independent evidence.\n")
            self.config["seats"].append({"id": name, "display_name": f"Factory {name}", "handle": f"test-{name}", "agent_id": f"agent-{name}",
                                         "model": "discovered-model", "mandate": str(mandate), "harness": "Codex test",
                                         "git_name": f"Factory {name}", "git_email": f"{name}@example.invalid", "registration_verified": False})
        files = {}
        for track in ("tablekeeper", "toy"):
            for stage in range(1, 5):
                relative = f"{track}/spec/stage-{stage}.md"
                target = Path(paths["challenge"]) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((f"# Official synthetic {track} specification {stage}\n\nComplete unicode text Ω — preserve bytes.\n" + "\n" * stage).encode())
                files[relative] = digest(target)
        write_json(Path(paths["factory"]) / "config/source-lock.json", {"challenge": {"commit": "a" * 40, "files": files}})
        self.config_path = Path(paths["factory"]) / "config/factory.yaml"
        self.save()

    def save(self):
        self.config_path.write_text(yaml.safe_dump(self.config))

    def tearDown(self):
        self.temp.cleanup()


class ConfigTests(Fixture):
    def test_valid_absolute_quoted_path(self):
        self.assertEqual(load_config(self.config_path), self.config)

    def test_malformed_yaml_does_not_echo_input(self):
        self.config_path.write_text("secret-looking-private-text: [unterminated")
        with self.assertRaises(FactoryError) as error:
            load_config(self.config_path)
        self.assertNotIn("secret-looking", str(error.exception))

    def test_wrong_root_and_missing_mapping(self):
        for value in ([], {"schema_version": 1}, {"schema_version": 2}):
            self.config_path.write_text(yaml.safe_dump(value))
            with self.assertRaises(FactoryError):
                load_config(self.config_path)

    def test_duplicate_handles_case_at_prefix(self):
        self.config["seats"][0]["handle"] = "@Same"
        self.config["seats"][1]["handle"] = "same"
        self.save()
        with self.assertRaisesRegex(FactoryError, "Duplicate seat handle"):
            load_config(self.config_path)

    def test_relative_nested_paths_rejected(self):
        self.config["paths"]["runs"] = "relative"
        self.save()
        with self.assertRaisesRegex(FactoryError, "absolute"):
            load_config(self.config_path)
        self.config["paths"]["runs"] = str(Path(self.config["paths"]["result"]) / "runs")
        self.save()
        with self.assertRaisesRegex(FactoryError, "non-nested"):
            load_config(self.config_path)

    def test_inherited_instruction_hash_drift_rejected(self):
        inherited = self.root / "global-instructions.md"
        inherited.write_text("Original neutral instructions")
        lock_path = Path(self.config["paths"]["factory"]) / "config/source-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["instruction_inputs"] = [{"path": str(inherited), "sha256": digest(inherited)}]
        write_json(lock_path, lock)
        responses = [{"exit_code": 0, "stdout": "a" * 40}, {"exit_code": 0, "stdout": ""}]
        with patch("factorykit.common.run_command", side_effect=responses):
            self.assertEqual(verify_sources(self.config), [])
        inherited.write_text("Changed instructions")
        with patch("factorykit.common.run_command", side_effect=responses):
            errors = verify_sources(self.config)
        self.assertTrue(any("global-instructions.md" in item for item in errors))

    def test_credentials_never_inside_workspace(self):
        self.config["band"]["credentials_file"] = str(Path(self.config["paths"]["factory"]) / "secret.yaml")
        self.save()
        with self.assertRaisesRegex(FactoryError, "outside"):
            load_config(self.config_path)

    def test_zero_or_infinite_budgets_rejected(self):
        for invalid in (0, -1, float("inf"), True):
            self.config["budgets"]["max_total_tokens"] = invalid
            self.save()
            with self.assertRaises(FactoryError):
                load_config(self.config_path)

    def test_doctor_preserves_verified_failed_permission_observation(self):
        proof = self.root / "permission-evidence.json"
        proof.write_text('{"actual_exit_code": 1}')
        write_json(Path(self.config["paths"]["runs"]) / "readiness/observations.json", {
            "configuration_sha256": digest(canonical(self.config)),
            "source_lock_sha256": digest(Path(self.config["paths"]["factory"]) / "config/source-lock.json"),
            "observations": [{"id": "permissions_agent_write_git", "status": "FAIL", "observed": True,
                              "observer": "utility test", "observed_at": "2026-10-03T00:00:00Z",
                              "evidence": [{"path": str(proof), "sha256": digest(proof)}]}]})
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "fixture", "stderr": ""}):
            report = doctor(self.config)
        status = {item["id"]: item["status"] for item in report["checks"]}
        self.assertEqual(status["permissions_agent_write_git"], "FAIL")
        self.assertEqual(status["toy_isolated_harness"], "NOT_TESTED")
        self.assertEqual(report["status"], "FAIL")

    def test_unknown_models_are_blockers_not_invented(self):
        self.config["runtime"]["model"] = None
        for seat in self.config["seats"]:
            seat["model"] = None
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
            result = validate(self.config, check_sources=False)
        self.assertTrue(any("Resolve" in item for item in result["launch_blockers"]))

    def test_ordinary_unresolved_prose_is_not_a_placeholder(self):
        for seat in self.config["seats"]:
            mandate = Path(seat["mandate"])
            mandate.write_text(mandate.read_text() + "Reject unresolved defects and report unknown limitations before acceptance.\n")
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
            result = validate(self.config, check_sources=False)
        self.assertFalse(any("Resolve placeholders" in item for item in result["launch_blockers"]))
        self.assertEqual(result["errors"], [])

    def test_explicit_and_metadata_placeholders_still_block(self):
        mandate = Path(self.config["seats"][0]["mandate"])
        original = mandate.read_text()
        for pending in ("BAND handle: UNRESOLVED", "BAND handle: unresolved", "Required output: TODO", "BAND handle: {{handle}}"):
            with self.subTest(pending=pending):
                mandate.write_text(original + pending + "\n")
                with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
                    result = validate(self.config, check_sources=False)
                self.assertIn("Resolve placeholders in pm's mandate", result["launch_blockers"])

    def test_mandate_wrong_model_and_domain_instruction_rejected(self):
        Path(self.config["seats"][0]["mandate"]).write_text("Harness: Codex test\nModel: guessed-model\nBuild a restaurant reservation.\n")
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
            result = validate(self.config, check_sources=False)
        self.assertTrue(any("differs" in item for item in result["errors"]))
        self.assertTrue(any("track-specific" in item for item in result["errors"]))


class ProcessTests(Fixture):
    def test_argv_keeps_spaces_and_quotes(self):
        argv = ["tool", "literal ' quoted path", "$(must not execute)"]
        with patch("factorykit.common.subprocess.run", return_value=subprocess.CompletedProcess(argv, 0, "ok", "")) as run:
            report = run_command(argv, self.root)
        self.assertEqual(run.call_args.args[0], argv)
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(report["exit_code"], 0)

    def test_missing_tools_failure_and_timeout(self):
        with patch("factorykit.common.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(run_command(["missing"], self.root)["exit_code"], 127)
        with patch("factorykit.common.subprocess.run", side_effect=subprocess.TimeoutExpired(["slow"], 1, b"partial", b"err")):
            result = run_command(["slow"], self.root)
        self.assertEqual(result["exit_code"], 124)
        self.assertIn("partial", result["stdout"])

    def test_harness_timeout_grace_interrupts_only_owned_group(self):
        process = MagicMock(pid=54321, returncode=130)
        process.poll.return_value = None
        process.communicate.side_effect = [subprocess.TimeoutExpired(["harness"], 1), ("partial evidence", "cleanup complete")]
        with patch("factorykit.common.subprocess.Popen", return_value=process) as popen, patch("factorykit.common.os.killpg") as kill:
            report = run_command(["harness"], self.root, timeout=1, graceful_interrupt=True)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(report["exit_code"], 124)
        self.assertEqual(kill.call_args_list[0].args, (54321, signal.SIGINT))
        self.assertEqual(kill.call_count, 1)
        self.assertIn("cleanup complete", report["stderr"])

    def test_harness_unresponsive_group_escalates_after_grace(self):
        process = MagicMock(pid=54321, returncode=-9)
        process.poll.return_value = None
        timeout = subprocess.TimeoutExpired(["harness"], 1)
        process.communicate.side_effect = [timeout, timeout, timeout, ("retained", "failed cleanup")]
        with patch("factorykit.common.subprocess.Popen", return_value=process), patch("factorykit.common.os.killpg") as kill:
            report = run_command(["harness"], self.root, timeout=1, graceful_interrupt=True)
        self.assertEqual(report["exit_code"], 124)
        self.assertEqual([call.args for call in kill.call_args_list], [(54321, signal.SIGINT), (54321, signal.SIGTERM), (54321, signal.SIGKILL)])
        self.assertIn("cleanup unverified", report["stderr"])

    def test_native_band_credentials_redacted_without_a_label(self):
        for prefix in ("band_a_", "band_u_"):
            with self.subTest(prefix=prefix):
                synthetic = prefix + "TESTONLYx1" * 4
                self.assertTrue(contains_secret(synthetic))
                self.assertEqual(redact(synthetic), "[REDACTED]")
                argv = ["fixture-tool", synthetic]
                with patch("factorykit.common.subprocess.run", return_value=subprocess.CompletedProcess(argv, 19, synthetic, json.dumps({"key": synthetic}))):
                    report = run_command(argv, self.root)
                self.assertNotIn(synthetic, json.dumps(report))
                self.assertEqual(report["argv"][1], "[REDACTED]")
                self.assertIn("[REDACTED]", report["stdout"])
                self.assertIn("[REDACTED]", report["stderr"])
        self.assertFalse(contains_secret("BAND key prefixes: band_a_ and band_u_"))

    def test_secrets_redacted_in_failures(self):
        token = "sk-" + "X1" * 20
        with patch("factorykit.common.subprocess.run", return_value=subprocess.CompletedProcess(["bad"], 19, token, "Bearer " + "abc123" * 8)):
            result = run_command(["bad"], self.root)
        self.assertEqual(result["exit_code"], 19)
        self.assertNotIn(token, json.dumps(result))
        self.assertIn("[REDACTED]", result["stdout"])
        self.assertNotIn("abc123", result["stderr"])

    def test_harness_unique_evidence_retains_exit(self):
        fake = {"exit_code": 7, "stdout": "fixture failure", "stderr": "intentional"}
        with patch("factorykit.operations.verify_sources", return_value=[]), patch("factorykit.operations.run_command", return_value=fake) as run:
            first_code, first = harness(self.config, "toy", 1, False, "isolated")
            first_path = first["evidence_directory"]
            second_code, second = harness(self.config, "toy", None, True, "host")
        self.assertEqual((first_code, second_code), (7, 7))
        self.assertNotEqual(first_path, second["evidence_directory"])
        self.assertEqual(json.loads((Path(first_path) / "invocation.json").read_text())["exit_code"], 7)
        self.assertIn("--all", run.call_args.args[0])
        self.assertIn(self.config["paths"]["rehearsal"], run.call_args.args[0])


class TaskTests(Fixture):
    def generate(self):
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            return generate(self.config)

    def test_repeat_is_identical_full_inherited_specs(self):
        first = self.generate()
        second = self.generate()
        self.assertEqual(first, second)
        for stage in range(1, 5):
            item = first["tasks"][f"judged-stage-{stage}.md"]
            self.assertEqual(len(item["spec_payloads"]), stage)
            raw = (Path(self.config["paths"]["factory"]) / "tasks" / f"judged-stage-{stage}.md").read_bytes()
            for payload in item["spec_payloads"]:
                self.assertEqual(raw[payload["offset"]:payload["offset"] + payload["bytes"]],
                                 (Path(self.config["paths"]["challenge"]) / payload["source"]).read_bytes())
        self.assertEqual(len(first["tasks"]), 6)

    def test_practice_mode_labels_tablekeeper_without_claiming_eligibility(self):
        self.config["launch"]["practice_mode"] = True
        self.generate()
        tasks = Path(self.config["paths"]["factory"]) / "tasks"
        for name in ("judged-all-stages.md", "judged-stage-1.md", "judged-stage-4.md"):
            packet = (tasks / name).read_text()
            self.assertTrue(packet.startswith("# Practice (unscored; eligibility not claimed)"))
            self.assertNotIn("during the judged run", packet)
            self.assertIn(self.config["paths"]["result"], packet)
            self.assertIn("Do not dispatch before the freeze reports READY_TO_LAUNCH", packet)
        self.assertEqual(len(verify_tasks(self.config)["tasks"]), 6)

    def test_rehearsal_has_no_circular_freeze_gate(self):
        self.generate()
        tasks = Path(self.config["paths"]["factory"]) / "tasks"
        toy = (tasks / "rehearsal-toy.md").read_text()
        self.assertNotIn("Do not dispatch before the freeze reports", toy)
        self.assertIn("judged freeze is not required", toy)
        separate = (tasks / "judged-stage-2.md").read_text()
        self.assertIn("Execute only stage 2", separate)
        self.assertNotIn("Attempt all stages", separate)

    def test_tampered_payload_and_stale_config_fail(self):
        self.generate()
        path = Path(self.config["paths"]["factory"]) / "tasks/judged-stage-4.md"
        path.write_bytes(path.read_bytes()[:-20])
        with self.assertRaises(FactoryError):
            verify_tasks(self.config)
        self.generate()
        self.config["seats"][0]["handle"] = "new-handle"
        with self.assertRaisesRegex(FactoryError, "stale"):
            verify_tasks(self.config)

    def test_changed_source_without_lock_change_fails(self):
        target = Path(self.config["paths"]["challenge"]) / "tablekeeper/spec/stage-1.md"
        target.write_text("changed")
        with self.assertRaisesRegex(FactoryError, "locked specification"):
            self.generate()

    def test_manifest_cannot_redefine_stage_inheritance(self):
        self.generate()
        path = Path(self.config["paths"]["factory"]) / "tasks/task-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["tasks"]["judged-stage-4.md"]["stages"] = [1]
        write_json(path, manifest)
        with self.assertRaisesRegex(FactoryError, "inheritance"):
            verify_tasks(self.config)

    def test_manifest_cannot_skip_inherited_payload(self):
        self.generate()
        path = Path(self.config["paths"]["factory"]) / "tasks/task-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["tasks"]["judged-stage-4.md"]["spec_payloads"].pop(0)
        write_json(path, manifest)
        with self.assertRaises(FactoryError):
            verify_tasks(self.config)


class LaunchTests(Fixture):
    def test_mixed_and_duplicate_dispatch_forbidden(self):
        self.assertEqual(validate_launch_request({}, "all", None), [1, 2, 3, 4])
        ledger = {"mode": "all", "entries": [{"stages": [1, 2, 3, 4], "state": "PREPARED"}]}
        with self.assertRaisesRegex(FactoryError, "mixing"):
            validate_launch_request(ledger, "separate", 1)
        with self.assertRaisesRegex(FactoryError, "duplicate"):
            validate_launch_request(ledger, "all", None)

    def test_separate_requires_prior_independent_acceptance(self):
        ledger = {"mode": "separate", "entries": [{"stages": [1], "state": "DISPATCHED"}]}
        with self.assertRaises(FactoryError):
            validate_launch_request(ledger, "separate", 2)
        ledger["entries"][0]["state"] = "ACCEPTED"
        self.assertEqual(validate_launch_request(ledger, "separate", 2), [2])

    def test_non_pristine_result_rejected(self):
        (Path(self.config["paths"]["result"]) / "unwanted.txt").write_text("not allowed")
        self.assertTrue(pristine_result(self.config))

    def test_missing_observations_never_ready(self):
        records, blockers = observations(self.config)
        self.assertEqual(records, [])
        self.assertGreater(len(blockers), 5)

    def test_claimed_pass_without_hashed_evidence_rejected(self):
        write_json(Path(self.config["paths"]["runs"]) / "readiness/observations.json", {
            "configuration_sha256": digest(canonical(self.config)),
            "source_lock_sha256": digest(Path(self.config["paths"]["factory"]) / "config/source-lock.json"),
            "observations": [{"id": "toy_isolated_harness", "status": "PASS", "observed": True,
                              "observed_at": "test", "observer": "test", "evidence": [{"path": "/missing", "sha256": "madeup"}]}]})
        records, blockers = observations(self.config)
        self.assertFalse(records)
        self.assertTrue(any("toy_isolated_harness" in value for value in blockers))


class WorkItemTests(Fixture):
    def item(self):
        return {"id": "W-001", "owner": "test-pm", "dependencies": [], "state": "PROPOSED", "goal": "Generic setup work",
                "requirements": ["Preserve source evidence"], "starting_revision": "a" * 40,
                "workspace_paths": [self.config["paths"]["runs"]], "ownership_boundaries": "Owned scratch only",
                "acceptance_conditions": ["Independent check"], "candidate_commit": None, "commands": [], "results": [],
                "evidence_paths": [], "limitations": [], "next_recipient": "test-reviewer"}

    def test_lifecycle_and_invalid_skip(self):
        item = validate_item(self.item(), self.config, "READY")
        item = validate_item(item, self.config, "IN_PROGRESS")
        with self.assertRaises(FactoryError):
            validate_item(item, self.config, "ACCEPTED")
        with self.assertRaises(FactoryError):
            validate_item(item, self.config, "REVIEW")

    def test_acceptance_requires_registered_distinct_reviewer(self):
        item = self.item()
        item.update(state="REVIEW", candidate_commit="b" * 40, commands=["verify"], results=["PASS"], evidence_paths=[str(self.root / "evidence.json")], room_event="actual-event")
        for reviewer in ("unknown-seat", "@TEST-PM"):
            item["reviewer"] = reviewer
            with self.assertRaises(FactoryError):
                validate_item(item, self.config, "ACCEPTED")
        item["reviewer"] = "@test-reviewer"
        self.assertEqual(validate_item(item, self.config, "ACCEPTED")["state"], "ACCEPTED")

    def test_blocked_requires_bounded_action_and_evidence(self):
        item = self.item()
        with self.assertRaises(FactoryError):
            validate_item(item, self.config, "BLOCKED")
        item["bounded_next_action"] = "Retry once after permission is granted"
        item["evidence_paths"] = [str(self.root / "evidence.json")]
        self.assertEqual(validate_item(item, self.config, "BLOCKED")["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
