"""Offline runner tests: no native helper, browser, Docker or inference execution."""
from contextlib import asynccontextmanager, ExitStack, redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from factorykit import opencode_live_probe as probe
from factorykit import runtime
from factorykit.common import FactoryError, canonical, digest


def config_for(root):
    from factorykit.source_snapshot import SOURCE_FILES
    for name in SOURCE_FILES:
        if name == "config/source-lock.json":
            continue
        target = root / "factory" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Synthetic factory input for offline permission tests.\n")
    runs = root / "runs"
    runs.mkdir()
    source = runs / "source-lock.json"
    source.write_text("{}\n")
    seats = [{"id": name, "agent_id": name + "-identity", "harness": "OpenCode", "model": "featherless/" + name,
              "git_name": name, "git_email": name + "@factory.invalid", "reasoning_effort": None} for name in ("pm", "backend")]
    for seat in seats:
        mandate = root / "factory" / "mandates" / (seat["id"] + ".md")
        mandate.parent.mkdir(exist_ok=True)
        mandate.write_text("Synthetic role mandate for offline permission tests.\n")
        seat["mandate"] = str(mandate)
    return {"paths": {"runs": str(runs), "factory": str(root / "factory"), "result": str(root / "result"), "rehearsal": str(root / "toy")},
            "artifacts": {"source_lock": str(source)}, "band": {"rehearsal_room_id": "rehearsal", "judged_room_id": "judged"},
            "runtime": {"harness": "opencode", "model": seats[0]["model"], "python": "/fake/python", "harness_python": "/fake/harness-python",
                        "browser_path": "/fake/browser", "opencode_version": "1.18.34", "opencode_sha256": "a" * 64,
                        "opencode_provider": {"api_key_env": "FACTORY_TEST_PROVIDER_KEY"}, "featherless_budget_guard": {},
                        "native_permissions": dict.fromkeys(("read", "write", "bash", "network"), True)},
            "budgets": {"approved": True, "billing_mode": "spend_cap", "spend_cap_usd": 25, "accounting_scope": "session",
                        "max_total_tokens": 2_000_000, "max_active_seats": 1, "max_repairs": 1, "max_turns_per_seat": 10,
                        "turn_timeout_seconds": 10, "stage_timeout_seconds": 1800, "overall_timeout_seconds": 21600}, "seats": seats}


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"nonce": "a" * 32, "workspace": str(self.root), "image_tag": "factory-permission-probe:" + "a" * 32}
        (self.root / "marker.txt").write_text(self.manifest["nonce"] + "\n")
        (self.root / "browser.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        self.commit, self.image = "b" * 40, "sha256:" + "c" * 64
        self.command = "/python /immutable/helper --child-manifest /immutable/manifest"
        output = {"status": "PASS", "nonce": self.manifest["nonce"], "git_commit": self.commit, "docker_image": self.image,
                  "browser": {"observed_nonce": self.manifest["nonce"], "screenshot_sha256": digest(self.root / "browser.png")},
                  "development_network": {"url": probe.NETWORK_URL, "http_status": 200, "sample_sha256": "d" * 64}}
        self.sink = SimpleNamespace(failed=False, events=[
            {"type": "tool_call", "tool": {"name": "bash", "tool_call_id": "native-1", "args": {"command": self.command}}},
            {"type": "tool_result", "tool": {"name": "bash", "tool_call_id": "native-1", "is_error": False, "output": json.dumps(output)}}])

    def verify(self, sink=None):
        with patch.object(probe, "_command", side_effect=[self.commit, self.manifest["nonce"]]), \
             patch.object(probe, "_inspect_image", return_value=self.image):
            return probe.verify_evidence(self.manifest, self.command, sink or self.sink)

    def test_native_call_result_and_independent_artifacts_required(self):
        self.assertEqual(self.verify()["git_commit"], self.commit)
        for mutate in (lambda s: s.update(events=[]), lambda s: s["events"][0]["tool"]["args"].update(command="echo forged"),
                       lambda s: s["events"][1]["tool"].update(tool_call_id="wrong"),
                       lambda s: s["events"][1]["tool"].update(is_error=True)):
            data = deepcopy(vars(self.sink))
            mutate(data)
            with self.assertRaises(FactoryError):
                self.verify(SimpleNamespace(**data))
        (self.root / "marker.txt").write_text("unrelated")
        with self.assertRaisesRegex(FactoryError, "workspace-write"):
            self.verify()

    def test_native_helper_cannot_be_retried(self):
        path = self.root / "claim.json"
        probe._claim(path, {"nonce": self.manifest["nonce"]})
        before = path.read_bytes()
        with self.assertRaisesRegex(FactoryError, "retries are prohibited"):
            probe._claim(path, {"nonce": "new"})
        self.assertEqual(path.read_bytes(), before)

    def test_cli_without_explicit_paid_flag_cannot_start(self):
        with patch.object(probe, "run_probes") as run, redirect_stderr(io.StringIO()):
            self.assertEqual(probe.main(["--config", "/missing/config"]), 2)
        run.assert_not_called()

    def test_synthetic_git_cannot_inherit_another_repository_or_hooks(self):
        with patch.dict(os.environ, {"GIT_DIR": "/product/.git", "GIT_WORK_TREE": "/product"}), \
             patch.object(probe.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="ok")) as run:
            self.assertEqual(probe._command(["git", "status"], self.root), "ok")
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("GIT_DIR", environment)
        self.assertNotIn("GIT_WORK_TREE", environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertIn("core.hooksPath=" + os.devnull, run.call_args.args[0])


class LiveProbeRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = config_for(self.root)

    def fake_boundaries(self, *, emit_usage=True, guard_errors=None, fail_callback=False):
        selected = {seat["model"]: seat for seat in self.config["seats"]}
        calls, configurations = [], []
        @asynccontextmanager
        async def start(config, mode, seats):
            configurations.append(deepcopy(config))
            live = deepcopy(config)
            live["runtime"]["_opencode_endpoints"] = {seat["id"]: {"verification": {"main_model": seat["model"],
                "small_model": seat["model"], "executable_sha256": "a" * 64}} for seat in seats}
            yield live
        config = self.config
        class Adapter:
            def __init__(self, **kwargs):
                pass
            async def on_started(self, *args):
                pass
            async def on_cleanup(self, *args):
                pass
            async def on_event(self, inp):
                assert inp.tools.room_id == inp.room_id == config["band"]["rehearsal_room_id"]
                claims = list((runtime.state_dir(config) / "opencode-live-probe-claims").glob("*.json"))
                assert len(claims) == len(calls) + 1, "Claim must be durable before callback"
                calls.append(inp)
                selected_model = next(seat["model"] for seat in config["seats"] if seat["id"] == inp.tools.seat)
                self.live_routes.add(tuple(selected_model.split("/", 1)))
                if emit_usage:
                    await inp.tools.send_event("usage", "task", {"band_usage": {"input_tokens": 40, "output_tokens": 10}})
                if fail_callback:
                    raise RuntimeError("synthetic adapter failure")
        stack = ExitStack()
        stack.enter_context(patch.object(probe, "prerequisites", return_value=(selected, {"pm": {"api_key": "secret"}})))
        stack.enter_context(patch.object(probe.harnesses, "start_runtime", start))
        stack.enter_context(patch.object(probe.harnesses, "alternate_adapter_config", return_value=object()))
        stack.enter_context(patch.object(probe.harnesses, "adapter_class", return_value=Adapter))
        stack.enter_context(patch.object(probe, "persisted_guard_blockers", return_value=guard_errors or []))
        verified = stack.enter_context(patch.object(probe, "verify_evidence", return_value={"native_tool_call_id": "synthetic"}))
        stack.enter_context(patch.object(probe, "cleanup_image", return_value={"status": "PASS", "synthetic": True}))
        self.addCleanup(stack.close)
        return calls, configurations, verified

    async def test_two_models_share_real_session_accounting_and_original_binding(self):
        original = deepcopy(self.config)
        calls, configs, verified = self.fake_boundaries()
        path = await probe.run_probes(self.config)
        report = json.loads(path.read_text())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["configuration_sha256"], digest(canonical(original)))
        self.assertEqual(self.config, original)
        self.assertEqual(len(calls), 2)
        self.assertEqual(verified.call_count, 2)
        ledger = runtime.session_ledger(self.config, "judged")
        self.assertEqual(ledger.data["tokens"], 100)
        self.assertEqual(ledger.data["room_turns"], {"rehearsal": {"pm": 1, "backend": 1}})
        self.assertTrue(all(Path(s["rehearsal_cwd"]).is_relative_to(Path(self.config["paths"]["runs"])) for s in configs[0]["seats"]))
        observations = json.loads((Path(self.config["paths"]["runs"]) / "readiness/observations.json").read_text())
        self.assertEqual({entry["id"] for entry in observations["observations"]}, set(probe.CHECKS))
        with self.assertRaisesRegex(FactoryError, "already claimed"):
            await probe.run_probes(self.config)
        self.assertEqual(len(calls), 2)

    async def test_missing_usage_halts_and_does_not_claim_second_model(self):
        calls, _, verified = self.fake_boundaries(emit_usage=False)
        with self.assertRaisesRegex(FactoryError, "usage"):
            await probe.run_probes(self.config)
        self.assertEqual(len(calls), 1)
        verified.assert_not_called()
        ledger = runtime.session_ledger(self.config, "rehearsal")
        self.assertIn("usage was not reported", ledger.data["stopped_reason"])
        self.assertFalse((Path(self.config["paths"]["runs"]) / "readiness/observations.json").exists())

    async def test_auxiliary_guard_halt_blocks_pass_even_with_main_usage(self):
        calls, _, verified = self.fake_boundaries(guard_errors=["auxiliary usage unknown"])
        with self.assertRaisesRegex(FactoryError, "auxiliary failures"):
            await probe.run_probes(self.config)
        self.assertEqual(len(calls), 1)
        verified.assert_not_called()
        self.assertEqual(runtime.session_ledger(self.config, "rehearsal").data["tokens"], 50)

    async def test_adapter_error_retains_claim_and_accounts_observed_usage(self):
        calls, _, verified = self.fake_boundaries(fail_callback=True)
        with self.assertRaises(RuntimeError):
            await probe.run_probes(self.config)
        self.assertEqual(len(calls), 1)
        self.assertEqual(runtime.session_ledger(self.config, "rehearsal").data["tokens"], 50)
        report = json.loads((Path(self.config["paths"]["runs"]) / "opencode-live-probe/evidence.json").read_text())
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["models"][0]["failure_type"], "RuntimeError")

    async def test_missing_credentials_and_unapproved_budgets_fail_before_inference(self):
        with patch.object(probe.harnesses, "validate_selection", return_value=[]), \
             patch.object(probe.harnesses, "permission_errors", return_value=[]), \
             patch.object(probe.harnesses, "_featherless_metadata"), \
             patch.object(probe.runtime, "credentials") as credentials, patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(FactoryError, "credential is missing"):
                probe.prerequisites(self.config)
            credentials.assert_not_called()
            self.config["budgets"]["approved"] = False
            with self.assertRaisesRegex(FactoryError, "Approve finite"):
                probe.prerequisites(self.config)
        self.assertFalse((Path(self.config["paths"]["runs"]) / "opencode-live-probe").exists())

    async def test_sink_suppresses_reasoning_and_redacts_known_credentials(self):
        path = self.root / "events.jsonl"
        sink = probe.EvidenceSink("local-agent", "rehearsal", path, ["known-provider-secret"])
        await sink.send_event("private reasoning", "thought")
        await sink.send_event(json.dumps({"name": "bash", "args": {"command": "known-provider-secret"}}), "tool_call")
        self.assertEqual(len(sink.events), 1)
        self.assertNotIn("known-provider-secret", path.read_text())
        self.assertNotIn("private reasoning", path.read_text())
        with self.assertRaisesRegex(FactoryError, "unavailable"):
            await sink.execute_tool_call_structured("band_send_message", {})

    async def test_real_sdk_failure_reporting_stays_local_and_marks_failure(self):
        from band_sdk_core import AgentFailure
        sink = probe.EvidenceSink("local-agent", "rehearsal", self.root / "events.jsonl")
        ledger = runtime.session_ledger(self.config, "rehearsal")
        wrapped = runtime.AuditedTools(sink, ledger, "pm", self.root / "audit.jsonl", harness="opencode", turn_id="probe")
        await wrapped.send_failure(AgentFailure("opencode", "synthetic failure"))
        self.assertEqual(wrapped.room_id, "rehearsal")
        self.assertEqual(wrapped.terminal_status, "failed")
        self.assertTrue(sink.failed)
        self.assertEqual(sink.events[0]["type"], "error")

    async def test_source_lock_drift_cannot_publish_new_readiness_binding(self):
        self.fake_boundaries()
        path = await probe.run_probes(self.config)
        observation_path = Path(self.config["paths"]["runs"]) / "readiness/observations.json"
        before = observation_path.read_bytes()
        Path(self.config["artifacts"]["source_lock"]).write_text('{"changed": true}\n')
        with self.assertRaisesRegex(FactoryError, "drifted"):
            probe.publish_observations(self.config, path)
        self.assertEqual(observation_path.read_bytes(), before)
