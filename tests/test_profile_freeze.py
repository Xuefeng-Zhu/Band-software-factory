"""Scoped mandate freeze checks with synthetic sources and offline ready proofs.

The readiness fixture mocks admission evidence only. Real packet rendering,
manifest hashing, artifact path checks and both launch gates remain exercised.
"""
from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import patch

import test_attempt_branches as attempt_fixtures
from factorykit.common import FactoryError, artifact_path, digest, load_config, write_json
from factorykit.operations import freeze, launch_prepare
from factorykit.runtime import judged_launch_errors
from factorykit.runtime_profiles import select_runtime


class ProfileFreezeTests(attempt_fixtures.Fixture):
    def setUp(self):
        super().setUp()
        self.source_config = copy.deepcopy(self.config)
        selected = select_runtime(self.config, harness="codex", model="selected-model",
                                  output=Path(self.config["paths"]["runs"]) / "profile",
                                  command="/tools/codex", source_config=self.config_path)
        self.config_path = Path(selected["config"])
        self.config = load_config(self.config_path)
        self.frozen_path = Path(self.config["paths"]["runs"]) / "freeze/latest.json"

    def ready(self):
        attempt_fixtures.ScopedArtifactTests.ready(self)

    def judged_errors(self):
        with patch("factorykit.runtime.persisted_budget_blockers", return_value=[]), \
                patch("factorykit.common.verify_sources", return_value=[]):
            return judged_launch_errors(self.config)

    def freeze_ready(self):
        self.ready()
        frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        self.assertEqual(self.judged_errors(), [])
        return frozen

    def assert_launch_rejected(self, fragment):
        preparation = launch_prepare(self.config, "all", None)
        self.assertEqual(preparation["status"], "BLOCKED_WITH_ACTIONS")
        self.assertTrue(any(fragment in value for value in preparation["blockers"]), preparation["blockers"])
        errors = self.judged_errors()
        self.assertTrue(any(fragment in value for value in errors), errors)
        self.assertFalse((Path(self.config["paths"]["runs"]) / "launch/ledger.json").exists())

    def test_freeze_hashes_exact_selected_mandates_and_launch_accepts_unchanged_profile(self):
        frozen = self.freeze_ready()
        expected = {str(Path(seat["mandate"]).resolve()): digest(Path(seat["mandate"])) for seat in self.config["seats"]}
        self.assertEqual(frozen["mandate_files"], expected)
        self.assertEqual(len(expected), 7)
        self.assertFalse(any(name.startswith("mandates/") for name in frozen["files"]))
        original_paths = {str(Path(seat["mandate"]).resolve()) for seat in self.source_config["seats"]}
        self.assertTrue(original_paths.isdisjoint(frozen["mandate_files"]))
        prepared = launch_prepare(self.config, "all", None)
        self.assertEqual(prepared["status"], "PREPARED_NOT_DISPATCHED", prepared["blockers"])

    def test_original_mandate_change_does_not_rebind_selected_profile(self):
        self.freeze_ready()
        original = Path(self.source_config["seats"][0]["mandate"])
        original.write_text(original.read_text() + "\nSource-only role revision.\n")
        self.assertEqual(self.judged_errors(), [])
        prepared = launch_prepare(self.config, "all", None)
        self.assertEqual(prepared["status"], "PREPARED_NOT_DISPATCHED", prepared["blockers"])

    def test_mixed_model_profile_freezes_and_blocks_later_role_model_change(self):
        selected = select_runtime(self.config, harness="codex", model="selected-model",
                                  seat_models={"qa": "review-model", "designer": "design-model"},
                                  output=Path(self.config["paths"]["runs"]) / "mixed",
                                  command="/tools/codex", source_config=self.config_path)
        self.config_path = Path(selected["config"])
        self.config = load_config(self.config_path)
        self.frozen_path = Path(self.config["paths"]["runs"]) / "freeze/latest.json"
        frozen = self.freeze_ready()
        qa = next(seat for seat in self.config["seats"] if seat["id"] == "qa")
        self.assertEqual(qa["model"], "review-model")
        self.assertEqual(frozen["mandate_files"][str(Path(qa["mandate"]).resolve())], digest(Path(qa["mandate"])))
        qa["model"] = "changed-after-freeze"
        self.assertIn("Configuration changed after freeze.", self.judged_errors())
        with self.assertRaisesRegex(FactoryError, "stale"):
            launch_prepare(self.config, "all", None)
        self.assertFalse((Path(self.config["paths"]["runs"]) / "launch/ledger.json").exists())

    def test_changed_selected_mandate_blocks_both_launch_paths(self):
        self.freeze_ready()
        selected = Path(self.config["seats"][0]["mandate"])
        selected.write_text(selected.read_text() + "\nA changed role instruction.\n")
        self.assert_launch_rejected("Frozen profile mandate changed: " + selected.name)

    def test_missing_selected_mandate_blocks_both_launch_paths(self):
        self.freeze_ready()
        selected = Path(self.config["seats"][0]["mandate"])
        selected.unlink()
        self.assert_launch_rejected("Frozen profile mandate changed: " + selected.name)

    def test_missing_or_extra_frozen_inventory_blocks_both_launch_paths(self):
        frozen = self.freeze_ready()
        for change in ("missing", "extra", "absent"):
            with self.subTest(change=change):
                altered = copy.deepcopy(frozen)
                if change == "missing":
                    altered["mandate_files"].pop(next(iter(altered["mandate_files"])))
                elif change == "extra":
                    altered["mandate_files"][str(self.root / "unconfigured.md")] = "0" * 64
                else:
                    del altered["mandate_files"]
                write_json(self.frozen_path, altered)
                self.assert_launch_rejected("Frozen profile mandate inventory differs")

    def test_configured_mandate_inventory_cannot_swap_to_an_unfrozen_file(self):
        self.freeze_ready()
        selected = Path(self.config["seats"][0]["mandate"])
        replacement = selected.with_name("replacement.md")
        replacement.write_bytes(selected.read_bytes())
        self.config["seats"][0]["mandate"] = str(replacement)
        errors = self.judged_errors()
        self.assertIn("Configuration changed after freeze.", errors)
        self.assertTrue(any("Frozen profile mandate inventory differs" in value for value in errors))
        # Preparing dispatch also fails the existing task/config binding before
        # it can reserve a launch, even when replacement bytes are identical.
        with self.assertRaisesRegex(FactoryError, "stale"):
            launch_prepare(self.config, "all", None)
        self.assertFalse((Path(self.config["paths"]["runs"]) / "launch/ledger.json").exists())

    def test_symlinked_selected_mandate_rejected_by_load_and_both_launch_paths(self):
        self.freeze_ready()
        selected = Path(self.config["seats"][0]["mandate"])
        outside = self.root / "outside-mandate.md"
        outside.write_bytes(selected.read_bytes())
        selected.unlink()
        selected.symlink_to(outside)
        for check in (lambda: load_config(self.config_path),
                      lambda: launch_prepare(self.config, "all", None), self.judged_errors):
            with self.subTest(check=check), self.assertRaisesRegex(FactoryError, "symlinks"):
                check()
        self.assertFalse((Path(self.config["paths"]["runs"]) / "launch/ledger.json").exists())

    def test_mandates_directory_escape_rejected_even_when_named_mandates(self):
        outside = self.root / "outside/mandates"
        outside.mkdir(parents=True)
        linked = Path(self.config["paths"]["runs"]) / "linked"
        linked.symlink_to(outside.parent, target_is_directory=True)
        candidates = (str(outside), str(linked / "mandates"), "relative/mandates")
        for directory in candidates:
            with self.subTest(directory=directory):
                self.config["artifacts"]["mandates"] = directory
                self.save()
                with self.assertRaisesRegex(FactoryError, "absolute path|under paths.runs"):
                    load_config(self.config_path)

    def test_each_selected_mandate_must_be_direct_child_of_scoped_directory(self):
        mandates = artifact_path(self.config, "mandates")
        nested = mandates / "nested/factory-pm.md"
        nested.parent.mkdir()
        nested.write_bytes(Path(self.config["seats"][0]["mandate"]).read_bytes())
        self.config["seats"][0]["mandate"] = str(nested)
        self.save()
        with self.assertRaisesRegex(FactoryError, "direct children"):
            load_config(self.config_path)
