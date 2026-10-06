"""Offline profile switching, source preservation and accounting boundaries."""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path
import subprocess
from unittest.mock import patch

from test_toolkit import Fixture
from factorykit.common import FactoryError, canonical, digest, load_config, write_json
from factorykit.runtime_profiles import register_commands, runtime_options, runtime_show, select_runtime
from factorykit.tasks import verify_tasks
from factorykit.validation import validate


class RuntimeProfileTests(Fixture):
    def setUp(self):
        super().setUp()
        self.config["runtime"].update(harness="codex", approval_mode="auto_decline", version="test-version")
        self.config["budgets"]["approved"] = True
        self.config["launch"].update(registration_verified=True, submission_open_verified=True)
        self.config["band"].update(rehearsal_room_id="rehearsal-original", judged_room_id="judged-original")
        for seat in self.config["seats"]:
            seat.update(harness="Codex", registration_verified=True, reasoning_effort="medium", cli_version="test-version")
            Path(seat["mandate"]).write_text("Harness: Codex\nModel: discovered-model\n\nKeep prose mentioning Model: unchanged.\n")
        self.save()
        self.output = Path(self.config["paths"]["runs"]) / "profiles/selected"

    def select(self, **kwargs):
        options = {"harness": "codex", "model": "new-model", "output": self.output,
                   "command": "/tools/codex", "source_config": self.config_path}
        options.update(kwargs)
        return select_runtime(self.config, **options)

    def test_codex_round_trip_preserves_original_and_regenerates_all_packets(self):
        snapshot = copy.deepcopy(self.config)
        source_bytes = self.config_path.read_bytes()
        mandates = {Path(seat["mandate"]): Path(seat["mandate"]).read_bytes() for seat in self.config["seats"]}
        report = self.select(reasoning_effort="high")
        selected = load_config(report["config"])
        self.assertEqual(self.config, snapshot)
        self.assertEqual(self.config_path.read_bytes(), source_bytes)
        for path, raw in mandates.items():
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(report["status"], "PREPARED_NOT_APPROVED")
        self.assertEqual(len(verify_tasks(selected)["tasks"]), 6)
        self.assertFalse(selected["budgets"]["approved"])
        self.assertFalse(selected["launch"]["registration_verified"])
        self.assertFalse(selected["launch"]["submission_open_verified"])
        self.assertEqual(selected["paths"]["result"], self.config["paths"]["result"])
        self.assertEqual(selected["band"], self.config["band"])
        self.assertEqual(selected["runtime_profile"]["source_rooms"], {"rehearsal": "rehearsal-original", "judged": "judged-original"})
        for seat in selected["seats"]:
            self.assertEqual(seat["model"], "new-model")
            self.assertEqual(seat["reasoning_effort"], "high")
            self.assertFalse(seat["registration_verified"])
            self.assertIn("Keep prose mentioning Model: unchanged.", Path(seat["mandate"]).read_text())
        self.assertEqual((self.output / "source-lock.json").read_bytes(),
                         (Path(self.config["paths"]["factory"]) / "config/source-lock.json").read_bytes())
        for name in ("owner.json", "models.json", "registration-rehearsal.json"):
            self.assertFalse((self.output / "runtime" / name).exists())

    def test_all_harnesses_create_valid_uniform_profiles(self):
        for harness, model, key, label in (("codex", "new-codex", "codex_command", "Codex"),
                                         ("claude-code", "claude-exact", "claude_command", "Claude Code"),
                                         ("opencode", "provider/model", "opencode_command", "OpenCode")):
            with self.subTest(harness=harness):
                path = self.output.parent / harness
                report = self.select(harness=harness, model=model, output=path, command=f"/tools/{harness}")
                selected = load_config(report["config"])
                self.assertEqual(selected["runtime"]["harness"], harness)
                self.assertEqual(selected["runtime"][key], f"/tools/{harness}")
                self.assertEqual(runtime_show(selected)["selection_errors"], [])
                self.assertTrue(all(seat["harness"] == label and seat["model"] == model for seat in selected["seats"]))
                self.assertEqual(len(verify_tasks(selected)["tasks"]), 6)
                if harness != "codex":
                    self.assertEqual(selected["runtime"]["sandbox"], "native-policy")
                    self.assertNotIn("version", selected["runtime"])
                    self.assertEqual(selected["runtime"]["native_permissions"],
                                     {"read": True, "write": False, "bash": False, "network": False})

    def test_role_models_round_trip_into_mandates_packets_and_receipt(self):
        model = "featherless/zai-org/GLM-5.3"
        flash = "featherless/zai-org/GLM-5.3-Flash"
        overrides = dict.fromkeys(("designer", "frontend", "qa"), flash)
        before = self.config_path.read_bytes()
        mandates = {Path(seat["mandate"]): Path(seat["mandate"]).read_bytes() for seat in self.config["seats"]}
        report = self.select(harness="opencode", model=model, command="/tools/opencode", seat_models=overrides)
        selected = load_config(report["config"])
        expected = {seat["id"]: overrides.get(seat["id"], model) for seat in selected["seats"]}
        self.assertEqual(selected["runtime"]["model"], model)
        self.assertEqual(report["seat_models"], expected)
        receipt = json.loads((self.output / "selection.json").read_text())
        self.assertEqual(receipt["seat_models"], expected)
        self.assertEqual(self.config_path.read_bytes(), before)
        for path, raw in mandates.items():
            self.assertEqual(path.read_bytes(), raw)
        for seat in selected["seats"]:
            self.assertEqual(seat["harness"], "OpenCode")
            self.assertEqual(seat["model"], expected[seat["id"]])
            self.assertIsNone(seat["reasoning_effort"])
            self.assertIn(f"\nModel: {seat['model']}\n", "\n" + Path(seat["mandate"]).read_text())
        manifest = json.loads((self.output / "tasks/task-manifest.json").read_text())
        self.assertEqual(manifest["configuration_sha256"], digest(canonical(selected)))
        self.assertEqual(len(verify_tasks(selected)["tasks"]), 6)
        for path in (self.output / "tasks").glob("*.md"):
            lines = path.read_text().splitlines()
            for role, selected_model in expected.items():
                line = next(line for line in lines if line.startswith(f"- {role}: "))
                self.assertTrue(line.endswith(f"harness: OpenCode; model: {selected_model}"), line)
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
            self.assertEqual(validate(selected, check_sources=False)["errors"], [])

    def test_changed_model_override_resets_inherited_variant_only_for_that_seat(self):
        first = self.select(harness="opencode", model="provider/model", command="/tools/opencode", variant="high")
        selected = load_config(first["config"])
        report = select_runtime(selected, harness="opencode", model="provider/model", output=self.output.parent / "mixed",
                                seat_models={"qa": "provider/other"}, source_config=first["config"])
        mixed = load_config(report["config"])
        for seat in mixed["seats"]:
            self.assertEqual(seat["reasoning_effort"], None if seat["id"] == "qa" else "high")

    def test_opencode_selection_rebases_private_state_and_preserves_binary_provider_pins(self):
        self.config["runtime"].update(opencode_state_root=str(Path(self.config["paths"]["runs"]) / "runtime/opencode"),
                                      opencode_version="1.18.34", opencode_sha256="a" * 64,
                                      opencode_provider={"id": "provider", "npm": "@ai-sdk/openai-compatible",
                                          "base_url": "https://provider.invalid/v1", "api_key_env": "PROVIDER_API_KEY",
                                          "models": {"model": {"limit": {"context": 32768, "output": 1024}}}})
        self.save()
        report = self.select(harness="opencode", model="provider/model", command="/tools/opencode")
        selected = load_config(report["config"])
        self.assertEqual(selected["runtime"]["opencode_state_root"], str(self.output.resolve() / "runtime/opencode"))
        for key in ("opencode_version", "opencode_sha256", "opencode_provider"):
            self.assertEqual(selected["runtime"][key], self.config["runtime"][key])
        self.assertEqual(runtime_show(selected)["selection_errors"], [])

    def guard_fixture(self):
        from factorykit.featherless_guard import MODEL_IDS, _Ledger, _policy
        models = {name: {"id": name, "status": "active", "tool_use": True,
                  "available_on_current_plan": True, "is_gated": False,
                  "effective_context_length": 32768, "effective_max_completion_tokens": 1024,
                  "pricing": {"prompt": "0.000001", "completion": "0.000002", "image": "0", "request": "0"}}
                  for name in MODEL_IDS}
        runs = Path(self.config["paths"]["runs"])
        metadata = runs / "provider-metadata.json"
        write_json(metadata, {"status": "PASS", "blockers": [], "api_origin": "https://api.featherless.ai",
                   "billing_attestation_verified_by_caller": True, "plan": {"id": "reviewed"},
                   "credits": {"currency": "usd", "balance_nano_usd": 25_000_000_000,
                               "reserved_nano_usd": 0, "available_nano_usd": 25_000_000_000}, "models": models})
        guard = {"ledger": str(runs / "runtime/provider-accounting.json"), "model_metadata": str(metadata),
                 "model_metadata_sha256": digest(metadata), "approved_credit_nano_usd": 25_000_000_000,
                 "max_total_tokens": 2_000_000, "overall_timeout_seconds": 21600, "request_timeout_seconds": 180}
        self.config["runtime"].update(opencode_state_root=str(runs / "opencode"), featherless_budget_guard=guard,
            opencode_provider={"id": "featherless", "npm": "@ai-sdk/openai-compatible",
                "base_url": "https://api.featherless.ai/v1", "api_key_env": "FEATHERLESS_API_KEY",
                "models": {name: {"limit": {"context": 32768, "output": 1024}} for name in models}})
        self.config["budgets"].update(billing_mode="spend_cap", spend_cap_usd=25, max_total_tokens=2_000_000,
                                       overall_timeout_seconds=21600, stage_timeout_seconds=1800,
                                       turn_timeout_seconds=180)
        policy = _policy(models, 25_000_000_000, 2_000_000, 21600)
        ledger = _Ledger(Path(guard["ledger"]), policy)
        ledger.open()
        ledger.close()
        self.save()
        return ledger, metadata

    def select_guard(self):
        return self.select(harness="opencode", model="featherless/zai-org/GLM-5.3", command="/tools/opencode")

    def test_unused_guard_profile_copies_exact_private_ledger_and_pinned_metadata(self):
        ledger, metadata = self.guard_fixture()
        original = {path: path.read_bytes() for path in (ledger.path, metadata, self.config_path)}
        selected = load_config(self.select_guard()["config"])
        guard = selected["runtime"]["featherless_budget_guard"]
        copied = Path(guard["ledger"])
        self.assertEqual(copied, self.output.resolve() / "runtime/featherless-requests.json")
        self.assertEqual(copied.read_bytes(), original[ledger.path])
        self.assertEqual(copied.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(guard["model_metadata"]).read_bytes(), original[metadata])
        self.assertEqual(guard["model_metadata_sha256"], digest(metadata))
        self.assertFalse(selected["budgets"]["approved"])
        self.assertFalse(selected["runtime_profile"]["source_session_consumed"])
        self.assertFalse((self.output / "inherited-runtime/provider-accounting.json").exists())
        for path, raw in original.items():
            self.assertEqual(path.read_bytes(), raw)
        from factorykit.featherless_guard import _Ledger
        reopened = _Ledger(copied, ledger.policy)
        reopened.open()
        reopened.close()
        self.assertEqual(copied.read_bytes(), original[ledger.path])

    def test_used_pending_unknown_clock_and_stopped_guard_profiles_cannot_fork_credit(self):
        ledger, _ = self.guard_fixture()
        pristine = ledger.path.read_bytes()
        for status in ("settled", "in_flight", "unknown", "clock", "stopped"):
            ledger.path.write_bytes(pristine)
            ledger.open()
            if status in ("settled", "in_flight", "unknown"):
                key = ledger.reserve("zai-org/GLM-5.3", 32)
                if status == "settled":
                    ledger.settle(key, 10, 2)
                elif status == "unknown":
                    ledger.unknown(key)
            elif status == "clock":
                ledger.data["started_epoch"] = time.time()
                ledger._save()
            else:
                ledger.halt("overall time budget exhausted")
            ledger.close()
            before = ledger.path.read_bytes()
            with self.subTest(status=status), self.assertRaisesRegex(FactoryError, "used or uncertain"):
                self.select_guard()
            self.assertEqual(ledger.path.read_bytes(), before)
            self.assertFalse(self.output.exists())

    def test_owned_missing_and_malformed_guard_ledgers_fail_without_source_changes(self):
        ledger, _ = self.guard_fixture()
        ledger.open()
        try:
            with self.assertRaisesRegex(FactoryError, "owned"):
                self.select_guard()
        finally:
            ledger.close()
        for raw in (b"{", b"{}"):
            ledger.path.write_bytes(raw)
            with self.assertRaises(FactoryError):
                self.select_guard()
            self.assertEqual(ledger.path.read_bytes(), raw)
        ledger.path.unlink()
        with self.assertRaises(FactoryError):
            self.select_guard()
        self.assertFalse(ledger.path.exists())
        self.assertFalse(self.output.exists())

    def test_guard_consumption_during_selection_aborts_published_profile(self):
        ledger, _ = self.guard_fixture()
        from factorykit.runtime_profiles import _control_snapshot
        calls = 0
        def consuming(config):
            nonlocal calls
            calls += 1
            if calls == 2:
                ledger.open()
                ledger.reserve("zai-org/GLM-5.3", 32)
                ledger.close()
            return _control_snapshot(config)
        with patch("factorykit.runtime_profiles._control_snapshot", side_effect=consuming), \
                self.assertRaisesRegex(FactoryError, "used or uncertain"):
            self.select_guard()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob(".selected.preparing-*")), [])

    def test_explicit_effort_applies_to_default_and_overridden_models(self):
        selected = load_config(self.select(seat_models={"qa": "review-model"}, reasoning_effort="high")["config"])
        self.assertTrue(all(seat["reasoning_effort"] == "high" for seat in selected["seats"]))

    def test_invalid_role_model_mapping_is_rejected_before_files_are_created(self):
        invalid = ({"unknown": "provider/other"}, {"qa": ""}, {"qa": "bad model"},
                   {"qa": "$(command)"}, {"qa": "no-provider"}, {"qa": "/model"},
                   {"qa": "provider/"}, {"qa": None}, {1: "provider/model"}, ["qa=provider/model"])
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(FactoryError):
                self.select(harness="opencode", model="provider/model", command="/tools/opencode", seat_models=overrides)
            self.assertFalse(self.output.parent.exists())

    def test_per_seat_validation_keeps_harness_and_mandate_consistency(self):
        selected = load_config(self.select(seat_models={"qa": "review-model"})["config"])
        qa = next(seat for seat in selected["seats"] if seat["id"] == "qa")
        qa["harness"] = "OpenCode"
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
            errors = validate(selected, check_sources=False)["errors"]
        self.assertTrue(any("harness differs" in item for item in errors), errors)
        qa["harness"] = "Codex"
        qa["model"] = "different-review-model"
        with patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": "[]"}):
            errors = validate(selected, check_sources=False)["errors"]
        self.assertIn("qa mandate Model: differs from configured runtime", errors)

    def test_switching_back_uses_new_directory_and_keeps_prior_profile_intact(self):
        write_json(Path(self.config["paths"]["runs"]) / "runtime/continuation/events.json", {"original_receipt": "retained"})
        first = self.select(harness="opencode", model="provider/model", command="/tools/opencode")
        first_path = Path(first["config"])
        before = {str(path): digest(path) for path in self.output.rglob("*") if path.is_file()}
        selected = load_config(first_path)
        second = self.output.parent / "back-to-codex"
        report = select_runtime(selected, harness="codex", model="another-model", output=second,
                                command="/tools/codex", source_config=first_path)
        restored = load_config(report["config"])
        self.assertEqual(restored["runtime"]["sandbox"], "workspace-write")
        self.assertNotIn("native_permissions", restored["runtime"])
        self.assertEqual(before, {str(path): digest(path) for path in self.output.rglob("*") if path.is_file()})
        self.assertEqual(len(verify_tasks(restored)["tasks"]), 6)
        self.assertTrue((second / "inherited-runtime/previous/continuation/events.json").is_file())

    def test_budgets_dispatch_and_receipts_preserved_without_readiness(self):
        runs = Path(self.config["paths"]["runs"])
        budget = {"tokens": 123, "turns": {"pm": 2}, "started_epoch": 1, "stopped_reason": "preserve-stop",
                  "token_threads": {"pm:thread": 123}, "room_ids": ["judged-original", "rehearsal-original"]}
        ledger = {"schema_version": 1, "mode": "all", "entries": [{"id": "once", "state": "DISPATCHED", "stages": [1, 2, 3, 4]}]}
        write_json(runs / "runtime/budget-subscription.json", budget)
        write_json(runs / "launch/ledger.json", ledger)
        write_json(runs / "runtime/continuation/claim/events.json", {"receipt": "original"})
        write_json(runs / "runtime/models.json", {"models": ["old"]})
        write_json(runs / "runtime/registration-judged.json", {"verified": True})
        selected = load_config(self.select()["config"])
        self.assertEqual((runs / "runtime/budget-subscription.json").read_bytes(),
                         (self.output / "runtime/budget-subscription.json").read_bytes())
        self.assertEqual((runs / "launch/ledger.json").read_bytes(), (self.output / "launch/ledger.json").read_bytes())
        self.assertTrue((self.output / "inherited-runtime/continuation/claim/events.json").is_file())
        self.assertTrue(selected["runtime_profile"]["source_session_consumed"])
        self.assertFalse((self.output / "runtime/models.json").exists())
        self.assertFalse((self.output / "runtime/registration-judged.json").exists())

    def test_output_overwrite_and_protected_overlap_rejected(self):
        outputs = [Path(self.config["paths"]["runs"]), Path(self.config["paths"]["factory"]) / "profile",
                   Path(self.config["paths"]["result"]) / "profile", Path(self.config["paths"]["runs"]) / "runtime/profile",
                   self.root, Path("relative-output")]
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(FactoryError):
                self.select(output=output)
        self.output.mkdir(parents=True)
        (self.output / "keep.txt").write_text("existing")
        with self.assertRaisesRegex(FactoryError, "already exists"):
            self.select()
        self.assertEqual((self.output / "keep.txt").read_text(), "existing")

    def test_symlink_output_and_source_controls_rejected(self):
        self.output.parent.mkdir(parents=True)
        self.output.symlink_to(self.root / "nonexistent")
        with self.assertRaisesRegex(FactoryError, "already exists"):
            self.select()
        self.output.unlink()
        (Path(self.config["paths"]["runs"]) / "runtime").symlink_to(self.root / "private")
        with self.assertRaisesRegex(FactoryError, "symlink"):
            self.select()

    def test_live_supervisor_prevents_inconsistent_snapshot(self):
        write_json(Path(self.config["paths"]["runs"]) / "runtime/owner.json", {"parent": {"pid": 1}, "token": "owned", "children": []})
        with patch("factorykit.runtime.is_owned", return_value=True), self.assertRaisesRegex(FactoryError, "live processes"):
            self.select()
        self.assertFalse(self.output.exists())

    def test_changed_sources_abort_staged_output(self):
        original = (Path(self.config["paths"]["factory"]) / "config/source-lock.json").read_bytes()
        from factorykit.runtime_profiles import _control_snapshot
        call_count = 0
        def changing(config):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                write_json(Path(config["paths"]["runs"]) / "runtime/budget-rehearsal.json", {"tokens": 1, "turns": {}})
            return _control_snapshot(config)
        with patch("factorykit.runtime_profiles._control_snapshot", side_effect=changing), self.assertRaisesRegex(FactoryError, "changed during selection"):
            self.select()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob(".selected.preparing-*")), [])
        self.assertEqual(original, (Path(self.config["paths"]["factory"]) / "config/source-lock.json").read_bytes())

    def test_changed_locked_spec_aborts_before_publication(self):
        (Path(self.config["paths"]["challenge"]) / "tablekeeper/spec/stage-3.md").write_text("changed")
        with self.assertRaisesRegex(FactoryError, "changed locked specification"):
            self.select()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob(".selected.preparing-*")), [])

    def test_duplicate_metadata_fails_without_rewriting_source(self):
        path = Path(self.config["seats"][0]["mandate"])
        path.write_text("Harness: Codex\nModel: first\nModel: second\n")
        before = path.read_bytes()
        with self.assertRaisesRegex(FactoryError, "exactly one anchored Model"):
            self.select()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.output.exists())

    def test_malformed_source_configuration_and_ledger_are_actionable(self):
        self.config_path.write_text("invalid: [")
        with self.assertRaisesRegex(FactoryError, "malformed YAML"):
            self.select()
        self.save()
        runtime = Path(self.config["paths"]["runs"]) / "runtime"
        runtime.mkdir()
        (runtime / "budget-subscription.json").write_text("not JSON")
        with self.assertRaisesRegex(FactoryError, "malformed JSON"):
            self.select()

    def test_invalid_identifiers_and_incompatible_options_rejected(self):
        for kwargs in ({"model": "bad model"}, {"model": "$(command)"}, {"harness": "unknown"},
                       {"harness": "opencode", "model": "no-provider"}, {"variant": "high"},
                       {"harness": "opencode", "model": "provider/model", "reasoning_effort": "high"},
                       {"command": "relative-command"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(FactoryError):
                self.select(**kwargs)
        self.assertFalse(self.output.exists())

    def test_missing_cli_requires_explicit_path_without_network_or_install(self):
        with patch("factorykit.runtime_profiles.shutil.which", return_value=None), self.assertRaisesRegex(FactoryError, "pass --command"):
            self.select(harness="claude-code", command=None)
        self.assertFalse(self.output.exists())

    def test_options_and_show_are_read_only(self):
        with patch("factorykit.runtime_profiles.shutil.which", side_effect=lambda name: f"/available/{name}"):
            options = runtime_options(self.config)
        self.assertEqual([value["id"] for value in options["harnesses"]], ["codex", "claude-code", "opencode"])
        self.assertEqual(runtime_show(self.config)["harness"], "codex")
        self.assertFalse(self.output.parent.exists())

    def test_cli_subcommands_select_output_directory(self):
        parser = argparse.ArgumentParser()
        register_commands(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["runtime-select", "--harness", "opencode", "--model", "provider/model",
                                  "--variant", "high", "--output", str(self.output), "--command", "/tools/opencode"])
        args.loaded_config, args.config = self.config, str(self.config_path)
        with patch("factorykit.cli.emit") as emit:
            self.assertEqual(args.func(args), 0)
        selected = load_config(emit.call_args.args[0]["config"])
        self.assertTrue(all(seat["reasoning_effort"] == "high" for seat in selected["seats"]))

    def test_cli_repeatable_seat_models_and_duplicate_or_malformed_rejection(self):
        parser = argparse.ArgumentParser()
        register_commands(parser.add_subparsers(dest="command", required=True))
        base = ["runtime-select", "--harness", "opencode", "--model", "provider/model",
                "--output", str(self.output), "--command", "/tools/opencode"]
        for overrides in (["qa=provider/other", "qa=provider/third"], ["qa"], ["qa="],
                          ["=provider/other"], ["qa==provider/other"], ["unknown=provider/other"]):
            with self.subTest(overrides=overrides):
                args = parser.parse_args(base + [item for value in overrides for item in ("--seat-model", value)])
                args.loaded_config, args.config = self.config, str(self.config_path)
                with self.assertRaises(FactoryError):
                    args.func(args)
                self.assertFalse(self.output.parent.exists())
        args = parser.parse_args(base + ["--seat-model", "qa=provider/qa", "--seat-model", "designer=provider/design"])
        args.loaded_config, args.config = self.config, str(self.config_path)
        with patch("factorykit.cli.emit") as emit:
            self.assertEqual(args.func(args), 0)
        expected = {seat["id"]: {"qa": "provider/qa", "designer": "provider/design"}.get(seat["id"], "provider/model")
                    for seat in self.config["seats"]}
        self.assertEqual(emit.call_args.args[0]["seat_models"], expected)

    def test_both_cli_entrypoints_load_config_for_options_and_selection(self):
        factory = Path(__file__).resolve().parents[1]
        for script in ("factory", "runtime"):
            with self.subTest(script=script):
                prefix = [str(factory / "scripts" / script), "--config", str(self.config_path)]
                shown = subprocess.run(prefix + ["runtime-show"], capture_output=True, text=True, cwd=factory)
                self.assertEqual(shown.returncode, 0, shown.stdout + shown.stderr)
                self.assertEqual(json.loads(shown.stdout)["harness"], "codex")
                output = self.output.parent / script
                selected = subprocess.run(prefix + ["runtime-select", "--harness", "opencode", "--model", "provider/model",
                                                      "--command", "/tools/opencode", "--output", str(output)],
                                          capture_output=True, text=True, cwd=factory)
                self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
                self.assertEqual(len(verify_tasks(load_config(json.loads(selected.stdout)["config"]))["tasks"]), 6)

    def test_atomic_publish_refuses_raced_existing_directory(self):
        from factorykit.runtime_profiles import _rename_exclusive
        def race(source, destination):
            destination.mkdir()
            (destination / "keep.txt").write_text("another writer")
            _rename_exclusive(source, destination)
        with patch("factorykit.runtime_profiles._rename_exclusive", side_effect=race), self.assertRaisesRegex(FactoryError, "nothing was overwritten"):
            self.select()
        self.assertEqual((self.output / "keep.txt").read_text(), "another writer")
        self.assertEqual(list(self.output.parent.glob(".selected.preparing-*")), [])
