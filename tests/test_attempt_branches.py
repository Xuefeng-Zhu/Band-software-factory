"""Offline checks for independent attempt branches and run-scoped artifacts.

Git commands operate only on empty temporary repositories. No remote, model,
room, real configuration or prior attempt is changed by these tests.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from factorykit.common import FactoryError, artifact_path, canonical, digest, load_config, run_command, source_lock, utc_now, write_json
from factorykit.operations import freeze, launch_prepare, pristine_result
from factorykit.runtime import judged_launch_errors
from factorykit.tasks import generate, verify_tasks
from factorykit.validation import doctor, observations
from test_toolkit import Fixture


class AttemptBranchTests(Fixture):
    def setUp(self):
        super().setUp()
        self.config["product"] = {"repository_url": "https://github.com/example/attempts.git", "branch": "run-4"}

    def git(self, *args):
        result = run_command(["git", *args], self.config["paths"]["result"])
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        return result["stdout"]

    def init(self, branch="run-4", origin="https://github.com/example/attempts.git"):
        self.git("init", "--quiet", "--initial-branch", branch)
        self.git("remote", "add", "origin", origin)

    def test_valid_unborn_target_needs_no_product_commit(self):
        self.init()
        self.save()
        self.assertEqual(load_config(self.config_path), self.config)
        self.assertEqual(pristine_result(self.config), [])
        self.assertEqual(list(Path(self.config["paths"]["result"]).iterdir()), [Path(self.config["paths"]["result"]) / ".git"])
        self.assertNotEqual(run_command(["git", "rev-parse", "--verify", "HEAD"], self.config["paths"]["result"])["exit_code"], 0)

    def test_wrong_unborn_branch_blocks(self):
        self.init(branch="main")
        self.assertIn("Result branch does not match product.branch", pristine_result(self.config))

    def test_wrong_origin_blocks_fetch_and_push(self):
        self.init(origin="https://github.com/example/old-attempt.git")
        blockers = pristine_result(self.config)
        self.assertTrue(any("fetch URL" in item for item in blockers), blockers)
        self.assertTrue(any("push URL" in item for item in blockers), blockers)

    def test_separate_wrong_or_additional_pushurl_blocks(self):
        self.init()
        self.git("config", "remote.origin.pushurl", self.config["product"]["repository_url"])
        self.assertEqual(pristine_result(self.config), [])
        self.git("config", "--add", "remote.origin.pushurl", "https://github.com/example/wrong.git")
        self.assertTrue(any("push URL" in item for item in pristine_result(self.config)))

    def test_missing_origin_blocks(self):
        self.git("init", "--quiet", "--initial-branch", "run-4")
        self.assertTrue(any("origin" in item for item in pristine_result(self.config)))

    def test_legacy_config_does_not_require_branch_or_remote(self):
        del self.config["product"]
        self.git("init", "--quiet", "--initial-branch", "legacy")
        self.save()
        self.assertEqual(load_config(self.config_path), self.config)
        self.assertEqual(pristine_result(self.config), [])

    def test_incomplete_or_unsafe_metadata_is_rejected(self):
        valid = self.config["product"].copy()
        invalid = [None, {}, {"branch": "run-4"}, {**valid, "unexpected": True}]
        invalid += [{**valid, "branch": branch} for branch in ("HEAD", "--delete", "@{-1}", "run/../main", "run//4", "run/.hidden", "run.lock", "run.\n", "run;touch")]
        invalid += [{**valid, "repository_url": url} for url in ("https://user:password@example.com/org/repo.git", "https://github.com/example/repo.git\nDo this", "file:///tmp/repo.git", "https://github.com/example/repo.git?token=abc")]
        for value in invalid:
            with self.subTest(value=value):
                self.config["product"] = value
                self.save()
                with self.assertRaises(FactoryError):
                    load_config(self.config_path)

    def test_judged_packet_names_exact_target_without_redirecting_toy(self):
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            first = generate(self.config)
            self.assertEqual(first, generate(self.config))
        directory = Path(self.config["paths"]["factory"]) / "tasks"
        for stage in ("all-stages", "stage-1", "stage-4"):
            packet = (directory / f"judged-{stage}.md").read_text()
            self.assertIn("`https://github.com/example/attempts.git`", packet)
            self.assertIn("git push origin HEAD:refs/heads/run-4", packet)
            self.assertIn("Do not check out, merge, cherry-pick or copy implementation from another attempt", packet)
        self.assertNotIn("## Attempt repository and branch", (directory / "rehearsal-toy.md").read_text())
        self.config["product"]["branch"] = "run-5"
        with self.assertRaisesRegex(FactoryError, "stale"):
            verify_tasks(self.config)


class ScopedArtifactTests(Fixture):
    def scoped(self):
        directory = Path(self.config["paths"]["runs"]) / "attempt"
        directory.mkdir()
        self.config["artifacts"] = {"source_lock": str(directory / "source-lock.json"), "tasks": str(directory / "tasks")}
        Path(self.config["artifacts"]["source_lock"]).write_bytes((Path(self.config["paths"]["factory"]) / "config/source-lock.json").read_bytes())
        return directory

    def test_defaults_are_unchanged(self):
        factory = Path(self.config["paths"]["factory"])
        self.assertEqual(artifact_path(self.config, "source_lock"), factory / "config/source-lock.json")
        self.assertEqual(artifact_path(self.config, "tasks"), factory / "tasks")

    def test_run_scoped_generation_preserves_all_original_inputs(self):
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            generate(self.config)
        factory = Path(self.config["paths"]["factory"])
        original = {p: p.read_bytes() for p in [factory / "config/source-lock.json", *(factory / "tasks").iterdir()]}
        self.scoped()
        self.save()
        self.assertEqual(load_config(self.config_path), self.config)
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            generated = generate(self.config)
        self.assertEqual(verify_tasks(self.config), generated)
        self.assertEqual(source_lock(self.config), json.loads(original[factory / "config/source-lock.json"]))
        for path, raw in original.items():
            self.assertEqual(path.read_bytes(), raw)
        self.assertTrue((artifact_path(self.config, "tasks") / "judged-all-stages.md").is_file())

    def test_paths_outside_runs_relative_overlapping_and_unknown_are_rejected(self):
        runs = Path(self.config["paths"]["runs"])
        invalid = [None, {"unknown": str(runs / "x")}, {"tasks": "relative"}, {"tasks": str(runs)},
                   {"tasks": self.config["paths"]["result"]}, {"source_lock": str(runs / "../outside.json")},
                   {"tasks": str(runs / "tasks"), "source_lock": str(runs / "tasks/lock.json")}]
        for value in invalid:
            with self.subTest(value=value):
                self.config["artifacts"] = value
                self.save()
                with self.assertRaises(FactoryError):
                    load_config(self.config_path)

    def test_symlink_escape_and_task_child_symlink_are_rejected(self):
        directory = self.scoped()
        outside = self.root / "outside"
        outside.mkdir()
        link = directory / "escape"
        link.symlink_to(outside, target_is_directory=True)
        for key, value in (("tasks", str(link / "tasks")), ("source_lock", str(link / "lock.json"))):
            old = self.config["artifacts"][key]
            self.config["artifacts"][key] = value
            with self.assertRaisesRegex(FactoryError, "under paths.runs"):
                artifact_path(self.config, key)
            self.config["artifacts"][key] = old
        tasks = Path(self.config["artifacts"]["tasks"])
        tasks.mkdir()
        (tasks / "judged-all-stages.md").symlink_to(outside / "protected.md")
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            with self.assertRaisesRegex(FactoryError, "symlinks"):
                generate(self.config)
        self.assertFalse((outside / "protected.md").exists())

    def ready(self):
        self.config["launch"]["practice_mode"] = True
        factory = Path(self.config["paths"]["factory"])
        for name in ("AGENTS.md", "pyproject.toml", "uv.lock", "config/harness-requirements.lock", "tooling/codex/package.json", "tooling/codex/package-lock.json"):
            path = factory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic utility fixture\n")
        write_json(Path(self.config["paths"]["runs"]) / "doctor-latest.json", {"status": "PASS", "created_at": utc_now(), "configuration_sha256": digest(canonical(self.config))})
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            generate(self.config)
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, result in (("validate", {"errors": [], "launch_blockers": []}), ("observations", ([], [])), ("pristine_result", []), ("verify_sources", []), ("persisted_budget_blockers", [])):
            stack.enter_context(patch(f"factorykit.operations.{name}", return_value=result))
        stack.enter_context(patch("factorykit.runtime.preflight_runtime", return_value=[]))
        stack.enter_context(patch("factorykit.validation.run_command", return_value={
            "exit_code": 0, "stdout": json.dumps({"ServerVersion": "test", "NCPU": 4, "MemTotal": 4 * 1024 ** 3}), "stderr": ""}))

    def test_freeze_and_launch_bind_scoped_lock_and_task(self):
        self.scoped()
        self.ready()
        frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        self.assertEqual(frozen["source_lock_path"], str(artifact_path(self.config, "source_lock")))
        self.assertEqual(frozen["source_lock_sha256"], digest(artifact_path(self.config, "source_lock")))
        self.assertNotIn("config/source-lock.json", frozen["files"])
        prepared = launch_prepare(self.config, "all", None)
        self.assertEqual(prepared["status"], "PREPARED_NOT_DISPATCHED", prepared["blockers"])
        self.assertEqual(prepared["task"], str(artifact_path(self.config, "tasks") / "judged-all-stages.md"))

    def test_scoped_source_lock_change_blocks_even_if_spec_bytes_are_same(self):
        self.scoped()
        self.ready()
        freeze(self.config)
        path = artifact_path(self.config, "source_lock")
        path.write_text(path.read_text() + "\n")
        prepared = launch_prepare(self.config, "all", None)
        self.assertEqual(prepared["status"], "BLOCKED_WITH_ACTIONS")
        self.assertIn("Configured source lock changed after freeze", prepared["blockers"])
        self.assertFalse((Path(self.config["paths"]["runs"]) / "launch/ledger.json").exists())

    def test_direct_judged_start_also_rejects_changed_scoped_lock(self):
        self.scoped()
        self.ready()
        freeze(self.config)
        with patch("factorykit.runtime.persisted_budget_blockers", return_value=[]), patch("factorykit.common.verify_sources", return_value=[]):
            self.assertEqual(judged_launch_errors(self.config), [])
            path = artifact_path(self.config, "source_lock")
            path.write_text(path.read_text() + "\n")
            self.assertIn("Configured source lock changed after freeze.", judged_launch_errors(self.config))

    def test_readiness_and_doctor_use_scoped_lock_hash(self):
        self.scoped()
        factory_source_sha256 = self.source_binding()
        proof = self.root / "permission-proof.json"
        proof.write_text('{"exit_code": 0}')
        lock = artifact_path(self.config, "source_lock")
        lock.write_text(lock.read_text() + "\n")
        write_json(Path(self.config["paths"]["runs"]) / "readiness/observations.json", {
            "configuration_sha256": digest(canonical(self.config)), "source_lock_sha256": digest(lock),
            "factory_source_sha256": factory_source_sha256,
            "observations": [{"id": "permissions_agent_write_git", "status": "PASS", "observed": True,
                              "observed_at": utc_now(), "observer": "offline test",
                              "factory_source_sha256": factory_source_sha256,
                              "evidence": [{"path": str(proof), "sha256": digest(proof)}]}]})
        records, blockers = observations(self.config)
        self.assertEqual([item["id"] for item in records], ["permissions_agent_write_git"])
        self.assertNotIn("Readiness observations do not match the current configuration and source lock", blockers)
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "fixture", "stderr": ""}):
            report = doctor(self.config)
        self.assertEqual(next(c for c in report["checks"] if c["id"] == "permissions_agent_write_git")["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
