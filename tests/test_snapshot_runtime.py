"""Offline launcher/snapshot integration, including a real Python child.

The child imports the actual factory runtime but replaces serve with local
assertions before cmd_serve is called. No socket, SDK connection or model is used.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from factorykit import runtime, source_snapshot
from factorykit.common import artifact_path, canonical, digest, write_json
from factorykit.tasks import generate
import test_toolkit as toolkit


class SnapshotRuntimeTests(toolkit.Fixture):
    def setUp(self):
        super().setUp()
        self.factory = Path(self.config["paths"]["factory"])
        self.runs = Path(self.config["paths"]["runs"])
        self.source_binding()
        package = Path(__file__).resolve().parents[1] / "factorykit"
        shutil.copytree(package, self.factory / "factorykit", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.factory / "protocols").mkdir()
        (self.factory / "protocols/collaboration.md").write_text("Frozen protocol for synthetic integration.\n")
        executable = Path(self.config["runtime"]["codex_command"])
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        self.config["progress"] = {"milestones": [{"id": "synthetic", "max_turns": 5, "max_seconds": 60,
                                                  "command": [sys.executable, "-c", "print('synthetic')"],
                                                  "timeout_seconds": 5, "max_attempts": 1}]}
        self.patch_active = patch.object(source_snapshot, "_active_snapshot", None)
        self.patch_active.start()
        self.addCleanup(self.patch_active.stop)
        self.freeze_inputs()

    def freeze_inputs(self):
        with patch("factorykit.tasks.verify_sources", return_value=[]):
            tasks = generate(self.config)
        files, errors = source_snapshot.source_inventory(self.config)
        self.assertEqual(errors, [])
        self.frozen = {"status": "READY_TO_LAUNCH", "configuration_sha256": digest(canonical(self.config)),
                       "files": files, "source_lock_sha256": digest(artifact_path(self.config, "source_lock")),
                       "tasks": tasks["tasks"]}
        if "mandates" in self.config.get("artifacts", {}):
            self.frozen["mandate_files"] = {str(Path(s["mandate"]).resolve()): digest(Path(s["mandate"])) for s in self.config["seats"]}
        write_json(self.runs / "freeze/latest.json", self.frozen)
        self.save()

    def materialize(self):
        return source_snapshot.materialize_source_snapshot(self.config, self.frozen)

    def child_assertions(self, descriptor):
        code = '''
import json, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from factorykit import runtime
from factorykit.common import load_config, artifact_path, verify_sources, scoped_mandate_errors
from factorykit.source_snapshot import factory_source_root, frozen_source_errors
from factorykit.tasks import verify_tasks
config = load_config(sys.argv[1])
frozen = json.loads(Path(sys.argv[3]).read_text())
args = SimpleNamespace(config=sys.argv[1], source_snapshot=sys.argv[2], mode="judged", owner_token="offline-test", recovery_id=None)
async def offline_serve(actual, mode, token, recovery):
    assert actual == config
    assert factory_source_root(actual) == Path(sys.argv[2]) / "source"
    assert frozen_source_errors(actual, frozen) == []
    assert scoped_mandate_errors(actual, frozen) == [], scoped_mandate_errors(actual, frozen)
    from factorykit.tasks import render_packet
    generated = render_packet(actual, "tablekeeper", [1,2,3,4], "all")[0]
    expected = (artifact_path(actual, "tasks") / "judged-all-stages.md").read_bytes()
    if generated != expected:
        import difflib
        print("".join(list(difflib.unified_diff(expected.decode().splitlines(True), generated.decode().splitlines(True)))[:20]), file=sys.stderr)
    assert verify_tasks(actual)["tasks"] == frozen["tasks"]
    assembled = runtime.standing_instructions(actual, actual["seats"][0])
    assert "Frozen protocol for synthetic integration." in assembled
    assert "Purpose: verify independent evidence." in assembled
    assert "MUTATED" not in assembled
    assert artifact_path(actual, "tasks").is_relative_to(Path(sys.argv[2]))
    with patch("factorykit.common.run_command", side_effect=[{"exit_code": 0, "stdout": "a" * 40}, {"exit_code": 0, "stdout": ""}]):
        assert verify_sources(actual) == []
    print(json.dumps({"imported_from_snapshot": True, "task_packets_verified": 6, "standing_inputs_preserved": True}))
runtime.serve = offline_serve
original_run = runtime.asyncio.run
def visible_run(coro):
    try:
        return original_run(coro)
    except BaseException:
        import traceback
        traceback.print_exc()
        raise
runtime.asyncio.run = visible_run
raise SystemExit(runtime.cmd_serve(args))
'''
        env = os.environ.copy()
        # Intentionally retain the original tree in PYTHONPATH: Python's -m/-c
        # cwd takes precedence, and cmd_serve verifies its own import location.
        env["PYTHONPATH"] = str(self.factory)
        env["PYTHONNOUSERSITE"] = "1"
        return subprocess.run([sys.executable, "-B", "-c", code, descriptor["config_path"], descriptor["root"],
                               str(self.runs / "freeze/latest.json")], cwd=descriptor["source_root"],
                              capture_output=True, text=True, timeout=20, env=env)

    def test_actual_child_uses_snapshot_code_packets_and_instructions_after_source_drift(self):
        descriptor = self.materialize()
        (self.factory / "factorykit/runtime.py").write_text("raise AssertionError('MUTATED runtime must never import')\n")
        (self.factory / "protocols/collaboration.md").write_text("MUTATED protocol\n")
        Path(self.config["seats"][0]["mandate"]).write_text("MUTATED mandate\n")
        (self.factory / "tasks/judged-all-stages.md").write_text("MUTATED task\n")
        result = self.child_assertions(descriptor)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["imported_from_snapshot"])

    def test_actual_child_maps_scoped_profile_mandates_and_keeps_configuration(self):
        profile = self.runs / "profile"
        profile.mkdir()
        for name in ("tasks", "mandates"):
            shutil.copytree(self.factory / name, profile / name)
        shutil.copyfile(self.factory / "config/source-lock.json", profile / "source-lock.json")
        self.config["artifacts"] = {"source_lock": str(profile / "source-lock.json"),
                                    "tasks": str(profile / "tasks"), "mandates": str(profile / "mandates")}
        for seat in self.config["seats"]:
            seat["mandate"] = str(profile / "mandates" / Path(seat["mandate"]).name)
        self.freeze_inputs()
        descriptor = self.materialize()
        Path(self.config["seats"][0]["mandate"]).write_text("MUTATED profile mandate\n")
        result = self.child_assertions(descriptor)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(Path(descriptor["config_path"]).read_bytes()), self.config)

    def test_start_supervisor_invokes_absolute_python_from_sealed_source(self):
        args = SimpleNamespace(config=str(self.config_path), mode="judged", loaded_config=self.config)
        process = MagicMock(pid=424242)
        with ExitStack() as stack:
            stack.enter_context(patch.object(runtime, "require_ready"))
            stack.enter_context(patch.object(runtime, "read_registry", side_effect=[{}, {"token": "offline-token", "status": "running"}]))
            stack.enter_context(patch.object(runtime, "is_owned", return_value=True))
            stack.enter_context(patch.object(runtime.secrets, "token_hex", return_value="offline-token"))
            stack.enter_context(patch.object(runtime, "process_identity", return_value={"pid": process.pid}))
            stack.enter_context(patch.object(runtime.psutil, "Process", return_value=object()))
            stack.enter_context(patch("builtins.print"))
            spawn = stack.enter_context(patch.object(runtime.subprocess, "Popen", return_value=process))
            self.assertEqual(runtime.start_supervisor(args), 0)
        argv = spawn.call_args.args[0]
        self.assertEqual(argv[:4], [self.config["runtime"]["python"], "-B", "-m", "factorykit.runtime"])
        root = Path(argv[argv.index("--source-snapshot") + 1])
        self.assertEqual(spawn.call_args.kwargs["cwd"], str(root / "source"))
        self.assertEqual(argv[argv.index("--config") + 1], str(root / "inputs/config.json"))
        self.assertFalse((root / "source").stat().st_mode & 0o222)
        saved = json.loads(runtime.registry_path(self.config).read_text())
        self.assertEqual(saved["source_snapshot"]["root"], str(root))
        self.assertEqual(saved["config_sha256"], runtime.fingerprint(self.config))

    def test_cmd_serve_rejects_original_checkout_import_for_snapshot(self):
        descriptor = self.materialize()
        args = SimpleNamespace(loaded_config=self.config, config=descriptor["config_path"], source_snapshot=descriptor["root"],
                               mode="judged", owner_token="offline-test", recovery_id=None)
        with patch.object(runtime, "serve", new_callable=AsyncMock) as serve, patch.object(runtime, "read_registry", return_value={}):
            self.assertEqual(runtime.cmd_serve(args), 2)
        serve.assert_not_awaited()

    def test_added_source_file_blocks_spawn_even_with_mocked_other_admission_gates(self):
        added = self.factory / "factorykit/unfrozen.py"
        added.write_text("pass\n")
        args = SimpleNamespace(config=str(self.config_path), mode="judged", loaded_config=self.config)
        with patch.object(runtime, "require_ready"), patch.object(runtime, "read_registry", return_value={}), \
                patch.object(runtime.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "Frozen input added"):
                runtime.start_supervisor(args)
        spawn.assert_not_called()
