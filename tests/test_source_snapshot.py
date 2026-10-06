"""Offline source publication, admission and child import isolation tests.

Only synthetic temporary factory inputs and a local Python process are used.
There are no BAND connections, model requests or historical artifact edits.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from factorykit.common import FactoryError, canonical, digest
from factorykit import source_snapshot as snapshots
from factorykit.operations import freeze, launch_prepare
import test_toolkit as toolkit


class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory snapshot ' ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.factory = self.root / "factory"
        self.runs = self.root / "runs"
        self.factory.mkdir()
        self.runs.mkdir()
        self.config = {"paths": {"factory": str(self.factory), "runs": str(self.runs)},
                       "runtime": {"python": sys.executable}, "seats": []}
        for name in snapshots.SOURCE_FILES:
            self.write(name, b"synthetic pinned input\n")
        self.write("factorykit/__init__.py", b"")
        self.write("factorykit/policy.py", b"VALUE = 'frozen-source'\n")
        self.write("factorykit/runtime.py", b"from factorykit.policy import VALUE\nprint(VALUE)\n")
        self.write("protocols/collaboration.md", b"Complete authentic handoffs only.\n")
        self.write("mandates/factory-pm.md", b"Independent coordinator.\n")
        self.write("scripts/runtime", b"#!/bin/sh\nexit 0\n")
        (self.factory / "scripts/runtime").chmod(0o755)
        self.write("tasks/judged-all-stages.md", b"Synthetic task; never dispatch.\n")
        self.write("tasks/task-manifest.json", b"{}\n")
        self.frozen = self.freeze()
        self.active_patch = patch.object(snapshots, "_active_snapshot", None)
        self.active_patch.start()
        self.addCleanup(self.active_patch.stop)

    def write(self, name, raw):
        path = self.factory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def freeze(self):
        files, errors = snapshots.source_inventory(self.config)
        self.assertEqual(errors, [])
        return {"configuration_sha256": digest(canonical(self.config)), "files": files,
                "source_lock_sha256": digest(self.factory / "config/source-lock.json"),
                "tasks": {"judged-all-stages.md": {"sha256": digest(self.factory / "tasks/judged-all-stages.md")}}}

    def snapshot(self):
        return snapshots.materialize_source_snapshot(self.config, self.frozen)

    def unseal(self, path):
        # Deliberate owner tampering for verification tests; never used by launch.
        Path(path).chmod(0o755 if Path(path).is_dir() else 0o644)

    def test_legacy_manifest_without_new_version_is_validated_exactly(self):
        self.assertNotIn("source_inventory_version", self.frozen)
        self.assertEqual(snapshots.frozen_source_errors(self.config, self.frozen), [])
        self.assertEqual(snapshots.factory_source_root(self.config), self.factory)
        self.assertIsNone(snapshots.snapshot_artifact_path(self.config, "tasks"))
        self.assertEqual(snapshots.snapshot_input_path(self.config, self.factory / "mandates/factory-pm.md"),
                         self.factory / "mandates/factory-pm.md")

    def test_new_runtime_or_protocol_file_invalidates_freeze(self):
        for name in ("factorykit/new_module.py", "protocols/new_policy.md"):
            with self.subTest(name=name):
                path = self.write(name, b"new input\n")
                self.assertIn(f"Frozen input added: {name}", snapshots.frozen_source_errors(self.config, self.frozen))
                with self.assertRaisesRegex(FactoryError, "Frozen input added"):
                    self.snapshot()
                path.unlink()

    def test_modified_or_removed_runtime_file_invalidates_freeze(self):
        path = self.factory / "factorykit/policy.py"
        path.write_text("VALUE = 'different'\n")
        self.assertIn("Frozen input changed: factorykit/policy.py", snapshots.frozen_source_errors(self.config, self.frozen))
        path.unlink()
        self.assertIn("Frozen input changed: factorykit/policy.py", snapshots.frozen_source_errors(self.config, self.frozen))

    def test_inventory_rejects_symlinked_file_directory_and_required_input(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "file.py").write_text("pass\n")
        for name, target in (("factorykit/link.py", outside / "file.py"),
                             ("factorykit/linked", outside), ("pyproject.toml", outside / "file.py")):
            with self.subTest(name=name):
                path = self.factory / name
                if path.exists():
                    path.unlink()
                path.symlink_to(target, target_is_directory=target.is_dir())
                self.assertTrue(any("symlink" in value for value in snapshots.frozen_source_errors(self.config, self.frozen)))
                path.unlink()

    def test_missing_empty_unsafe_and_malformed_inventories_fail_closed(self):
        for files in (None, {}, [], {"../escape": "a" * 64}, {"/absolute": "a" * 64}, {"factorykit/a.py": "bad"}):
            with self.subTest(files=files):
                self.assertTrue(snapshots.frozen_source_errors(self.config, {**self.frozen, "files": files}))

    def test_fingerprint_tracks_inventory_and_ignores_python_cache(self):
        before = snapshots.source_fingerprint(self.config)
        self.write("factorykit/__pycache__/policy.cpython-313.pyc", b"ephemeral cache")
        self.assertEqual(snapshots.source_fingerprint(self.config), before)
        self.write("factorykit/new.py", b"pass\n")
        self.assertNotEqual(snapshots.source_fingerprint(self.config), before)

    def test_snapshot_is_sealed_content_addressed_and_repeatable(self):
        descriptor = self.snapshot()
        root = Path(descriptor["root"])
        self.assertEqual(root.name, descriptor["manifest_sha256"])
        self.assertEqual(descriptor, self.snapshot())
        self.assertEqual(json.loads(Path(descriptor["config_path"]).read_bytes()), self.config)
        self.assertEqual(descriptor["manifest"]["external_runtime_entrypoints"]["python"]["path"], sys.executable)
        self.assertIn("remain external", descriptor["manifest"]["dependency_boundary"])
        for path in (root, *root.rglob("*")):
            self.assertFalse(path.stat().st_mode & 0o222, str(path))
        self.assertTrue((root / "source/scripts/runtime").stat().st_mode & 0o111)
        self.assertFalse((root / "source/factorykit/policy.py").stat().st_mode & 0o111)

    def test_child_imports_frozen_code_after_original_factory_is_removed(self):
        descriptor = self.snapshot()
        shutil.rmtree(self.factory)
        result = subprocess.run([sys.executable, "-B", "-m", "factorykit.runtime"],
                                cwd=descriptor["source_root"], capture_output=True, text=True, timeout=10,
                                env={"PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "frozen-source\n")
        self.assertEqual(snapshots.verify_source_snapshot(self.config, Path(descriptor["root"])), descriptor)

    def test_activation_uses_copied_inputs_without_changing_config(self):
        original = copy.deepcopy(self.config)
        descriptor = self.snapshot()
        snapshots.activate_source_snapshot(self.config, Path(descriptor["root"]))
        (self.factory / "protocols/collaboration.md").write_text("Changed after child starts.\n")
        (self.factory / "mandates/factory-pm.md").write_text("Changed mandate.\n")
        self.assertEqual(snapshots.frozen_source_errors(self.config, self.frozen), [])
        self.assertEqual(snapshots.snapshot_input_path(self.config, self.factory / "mandates/factory-pm.md").read_text(),
                         "Independent coordinator.\n")
        self.assertEqual(snapshots.snapshot_artifact_path(self.config, "tasks"), Path(descriptor["root"]) / "inputs/tasks")
        self.assertEqual(self.config, original)

    def test_extra_file_in_sealed_snapshot_is_rejected(self):
        descriptor = self.snapshot()
        directory = Path(descriptor["source_root"]) / "factorykit"
        self.unseal(directory)
        extra = directory / "added.py"
        extra.write_text("pass\n")
        extra.chmod(0o444)
        directory.chmod(0o555)
        with self.assertRaisesRegex(FactoryError, "inventory differs"):
            snapshots.verify_source_snapshot(self.config, Path(descriptor["root"]))

    def test_changed_content_even_when_resealed_is_rejected(self):
        descriptor = self.snapshot()
        path = Path(descriptor["source_root"]) / "factorykit/policy.py"
        self.unseal(path)
        path.write_text("VALUE = 'tampered'\n")
        path.chmod(0o444)
        with self.assertRaisesRegex(FactoryError, "input changed"):
            snapshots.verify_source_snapshot(self.config, Path(descriptor["root"]))

    def test_writable_mode_and_symlink_are_rejected_at_activation(self):
        descriptor = self.snapshot()
        root = Path(descriptor["root"])
        path = root / "source/factorykit/policy.py"
        self.unseal(path)
        with self.assertRaisesRegex(FactoryError, "read-only"):
            snapshots.activate_source_snapshot(self.config, root)
        path.chmod(0o444)
        self.unseal(path.parent)
        path.unlink()
        path.symlink_to(self.factory / "factorykit/policy.py")
        path.parent.chmod(0o555)
        with self.assertRaisesRegex(FactoryError, "symlinks"):
            snapshots.activate_source_snapshot(self.config, root)

    def test_external_entrypoint_drift_is_rejected_without_rebasing_venv(self):
        executable = self.root / "external-runtime"
        executable.write_text("#!/bin/sh\nexit 0\n")
        self.config["runtime"]["codex_command"] = str(executable)
        self.frozen = self.freeze()
        descriptor = self.snapshot()
        executable.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaisesRegex(FactoryError, "External runtime entrypoint changed"):
            snapshots.verify_source_snapshot(self.config, Path(descriptor["root"]))

    def test_snapshot_rejects_other_config_and_outside_run_directory(self):
        descriptor = self.snapshot()
        changed = copy.deepcopy(self.config)
        changed["new"] = True
        with self.assertRaisesRegex(FactoryError, "configuration binding differs"):
            snapshots.verify_source_snapshot(changed, Path(descriptor["root"]))
        with self.assertRaisesRegex(FactoryError, "run-owned"):
            snapshots.verify_source_snapshot(self.config, self.root)

    def test_scoped_artifacts_are_copied_with_original_config_binding(self):
        profile = self.runs / "profile"
        profile.mkdir()
        for name in ("mandates", "tasks"):
            shutil.copytree(self.factory / name, profile / name)
        shutil.copyfile(self.factory / "config/source-lock.json", profile / "source-lock.json")
        self.config["artifacts"] = {"mandates": str(profile / "mandates"), "tasks": str(profile / "tasks"),
                                    "source_lock": str(profile / "source-lock.json")}
        self.config["seats"] = [{"mandate": str(profile / "mandates/factory-pm.md")}]
        self.frozen = self.freeze()
        self.frozen["mandate_files"] = {str(profile / "mandates/factory-pm.md"): digest(profile / "mandates/factory-pm.md")}
        descriptor = self.snapshot()
        self.assertNotIn("mandates/factory-pm.md", descriptor["manifest"]["source_files"])
        snapshots.activate_source_snapshot(self.config, Path(descriptor["root"]))
        self.assertEqual(snapshots.snapshot_input_path(self.config, profile / "mandates/factory-pm.md").read_text(),
                         "Independent coordinator.\n")

    def test_source_edit_during_copy_never_publishes_snapshot(self):
        original = Path.read_bytes
        changed = False

        def read(path):
            nonlocal changed
            raw = original(path)
            if path == self.factory / "factorykit/policy.py" and not changed:
                changed = True
                (self.factory / "factorykit/late.py").write_text("pass\n")
            return raw

        with patch.object(Path, "read_bytes", read), self.assertRaisesRegex(FactoryError, "changed while copying"):
            self.snapshot()
        self.assertEqual(list((self.runs / "source-snapshots").iterdir()), [])


class SourceFreezeGateTests(toolkit.Fixture):
    def setUp(self):
        super().setUp()
        toolkit.LaunchTests.ready_freeze_fixture(self)
        self.patches = [
            patch("factorykit.operations.validate", return_value={"errors": [], "launch_blockers": []}),
            patch("factorykit.operations.observations", return_value=([], [])),
            patch("factorykit.operations.pristine_result", return_value=[]),
            patch("factorykit.operations.verify_sources", return_value=[]),
            patch("factorykit.runtime.preflight_runtime", return_value=[]),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_new_freeze_records_exact_source_fingerprint_and_blocks_added_module(self):
        frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        self.assertEqual(frozen["source_inventory_version"], 1)
        self.assertEqual(frozen["factory_source_sha256"], snapshots.source_fingerprint(self.config))
        added = Path(self.config["paths"]["factory"]) / "factorykit/late.py"
        added.parent.mkdir()
        added.write_text("pass\n")
        result = launch_prepare(self.config, "all", None)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assertIn("Frozen input added: factorykit/late.py", result["blockers"])
        self.assertFalse((Path(self.config["paths"]["runs"]) / "launch/ledger.json").exists())

    def test_historical_freeze_without_source_version_still_rejects_new_protocol(self):
        frozen = freeze(self.config)
        frozen.pop("source_inventory_version")
        frozen.pop("factory_source_sha256")
        path = Path(self.config["paths"]["runs"]) / "freeze/latest.json"
        path.write_text(json.dumps(frozen))
        added = Path(self.config["paths"]["factory"]) / "protocols/late.md"
        added.parent.mkdir()
        added.write_text("An added standing policy.\n")
        result = launch_prepare(self.config, "all", None)
        self.assertIn("Frozen input added: protocols/late.md", result["blockers"])


if __name__ == "__main__":
    unittest.main()
