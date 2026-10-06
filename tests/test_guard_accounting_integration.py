"""Pure readiness and real supervisor stop propagation, without provider calls."""

import asyncio
from contextlib import asynccontextmanager, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from band import Agent
from band.core.types import AgentInput, TurnUsage
from band.runtime.tools.agent import AgentTools
from pydantic import SecretStr

from factorykit import harnesses, runtime
from factorykit.budgets import budget_ledger_path, persisted_budget_blockers, persisted_guard_blockers
from factorykit.featherless import MODEL_IDS
from factorykit.featherless_guard import _Ledger, _policy
from factorykit.operations import freeze, launch_prepare

from test_budget_readiness import BudgetReadinessFixture, ORIGIN
import test_runtime_harness_integration as supervisor_fixture
from test_runtime_harness_integration import ROOM, PM, EVENT


def bind_guard(config):
    runs = Path(config["paths"]["runs"])
    models = {model: {"id": model, "status": "active", "tool_use": True,
                     "available_on_current_plan": True, "is_gated": False,
                     "effective_context_length": 64, "effective_max_completion_tokens": 16,
                     "pricing": {"prompt": "0.0000001", "completion": "0.0000002", "image": "0", "request": "0"}}
              for model in MODEL_IDS}
    evidence = {"status": "PASS", "blockers": [], "api_origin": "https://api.featherless.ai",
                "billing_attestation_verified_by_caller": True, "plan": {"id": "test_plan"},
                "credits": {"currency": "usd", "balance_nano_usd": 25000000000,
                            "reserved_nano_usd": 0, "available_nano_usd": 25000000000}, "models": models}
    metadata = runs / "readiness/models.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(evidence))
    guard = {"ledger": str(runs / "runtime/featherless-requests.json"),
             "model_metadata": str(metadata), "model_metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
             "approved_credit_nano_usd": 25000000000, "max_total_tokens": config["budgets"]["max_total_tokens"],
             "overall_timeout_seconds": config["budgets"]["overall_timeout_seconds"],
             "request_timeout_seconds": config["budgets"]["turn_timeout_seconds"]}
    config["runtime"].update(opencode_state_root=str(runs / "runtime/opencode"), featherless_budget_guard=guard,
        opencode_provider={"id": "featherless", "npm": "@ai-sdk/openai-compatible", "base_url": "https://api.featherless.ai/v1",
                           "api_key_env": "UNREAD_TEST_KEY", "models": {
                               model: {"id": model, "limit": {"context": 64, "output": 16}} for model in MODEL_IDS}})
    policy = _policy(models, guard["approved_credit_nano_usd"], guard["max_total_tokens"], guard["overall_timeout_seconds"])
    return _Ledger(Path(guard["ledger"]), policy)


class GuardReadinessTests(BudgetReadinessFixture):
    def setUp(self):
        super().setUp()
        self.config["budgets"].update(billing_mode="spend_cap", accounting_scope="session", spend_cap_usd=25,
                                      overall_timeout_seconds=21600, max_total_tokens=2000000)
        self.path = budget_ledger_path(self.config)
        self.guard = bind_guard(self.config)
        self.guard_path = self.guard.path
        self.ready_files()
        self.save_ledger()

    def open_guard(self):
        self.guard.open()
        self.addCleanup(self.guard.close)

    def test_missing_guard_allowed_for_initial_discovery_but_never_created_by_inspector(self):
        self.assertEqual(persisted_guard_blockers(self.config), [])
        self.assertFalse(self.guard_path.exists())
        self.assertFalse(self.guard_path.with_suffix(".json.lock").exists())
        self.assertTrue(persisted_guard_blockers(self.config, require_existing=True))
        self.assertFalse(self.guard_path.exists())

    def test_pending_is_not_launch_readiness_and_pure_inspection_keeps_holds_untouched(self):
        self.open_guard()
        self.guard.reserve(MODEL_IDS[0], 16)
        before, mtime = self.guard_path.read_bytes(), self.guard_path.stat().st_mtime_ns
        self.assertTrue(persisted_guard_blockers(self.config))
        self.assertEqual(persisted_guard_blockers(self.config, allow_in_flight=True), [])
        self.assertEqual(self.guard_path.read_bytes(), before)
        self.assertEqual(self.guard_path.stat().st_mtime_ns, mtime)

    def test_unknown_auxiliary_usage_blocks_preflight_freeze_and_launch_despite_valid_sdk_ledger(self):
        with patch("time.time", return_value=ORIGIN):
            self.open_guard()
            key = self.guard.reserve(MODEL_IDS[1], 16)
            self.guard.unknown(key)
        guard_before, factory_before = self.guard_path.read_bytes(), self.path.read_bytes()
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 1):
            preflight = runtime.preflight_runtime(self.config, "judged")
            frozen = freeze(self.config)
            launch = launch_prepare(self.config, "all", None)
        self.assertTrue(any("Featherless" in item for item in preflight))
        self.assertEqual(frozen["status"], "BLOCKED_WITH_ACTIONS")
        self.assertEqual(launch["status"], "BLOCKED_WITH_ACTIONS")
        self.assertEqual(self.guard_path.read_bytes(), guard_before)
        self.assertEqual(self.path.read_bytes(), factory_before)
        self.assertIsNone(json.loads(factory_before)["stopped_reason"])

    def test_stopped_guard_after_freeze_blocks_launch_even_when_sdk_usage_is_unchanged(self):
        with patch("time.time", return_value=ORIGIN):
            self.open_guard()
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 1):
            frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        self.guard.halt("money reservation would exceed the approved cap")
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2):
            launch = launch_prepare(self.config, "all", None)
        self.assertEqual(launch["status"], "BLOCKED_WITH_ACTIONS")
        self.assertTrue(any("Featherless" in item for item in launch["blockers"]))
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())

    def test_guard_deadline_and_policy_tampering_block_without_reset(self):
        with patch("time.time", return_value=ORIGIN):
            self.open_guard()
            key = self.guard.reserve(MODEL_IDS[0], 16)
            self.guard.settle(key, 10, 5)
        before = self.guard_path.read_bytes()
        self.assertTrue(any("overall" in value for value in persisted_guard_blockers(self.config, now=ORIGIN + 21600)))
        self.config["runtime"]["featherless_budget_guard"]["max_total_tokens"] -= 1
        self.assertTrue(persisted_guard_blockers(self.config, now=ORIGIN + 1))
        self.assertEqual(self.guard_path.read_bytes(), before)

    def test_missing_nullable_fields_and_changed_metadata_are_invalid_not_pristine(self):
        self.open_guard()
        data = json.loads(self.guard_path.read_text())
        del data["started_epoch"]
        self.guard_path.write_text(json.dumps(data))
        self.assertTrue(persisted_guard_blockers(self.config))
        before = self.guard_path.read_bytes()
        metadata = Path(self.config["runtime"]["featherless_budget_guard"]["model_metadata"])
        metadata.write_text(metadata.read_text() + "\n")
        self.assertTrue(persisted_guard_blockers(self.config))
        self.assertEqual(self.guard_path.read_bytes(), before)

    def test_status_reports_guard_block_even_when_factory_never_started(self):
        self.open_guard()
        self.guard.halt("money reservation would exceed the approved cap")
        output = io.StringIO()
        with patch.object(runtime, "read_registry", return_value={}), redirect_stdout(output):
            runtime.cmd_status(SimpleNamespace(loaded_config=self.config))
        value = json.loads(output.getvalue())
        self.assertEqual(value["status"], "not_started")
        self.assertTrue(value["request_guard_blockers"])


class GuardSupervisorTests(unittest.IsolatedAsyncioTestCase):
    setUp = supervisor_fixture.SupervisorHarnessTests.setUp
    configuration = supervisor_fixture.SupervisorHarnessTests.configuration

    async def test_auxiliary_guard_stop_halts_supervisor_after_successful_reported_main_turn(self):
        cfg = self.configuration("opencode")
        cfg["budgets"].update(accounting_scope="session", approved=True, spend_cap_usd=25)
        cfg["runtime"]["model"] = cfg["seats"][0]["model"] = "featherless/" + MODEL_IDS[0]
        guard = bind_guard(cfg)
        guard.open()
        self.addCleanup(guard.close)
        backend = harnesses.adapter_class(cfg)
        runtime.save_json(runtime.registry_path(cfg), {"token": "owned-test-token", "status": "starting"})
        original_ledger = runtime.session_ledger
        captured = {"stopped": False}

        def ledger_factory(*args, **kwargs):
            captured["ledger"] = original_ledger(*args, **kwargs)
            return captured["ledger"]

        @asynccontextmanager
        async def servers(config, mode, seats):
            live = {**config, "runtime": dict(config["runtime"])}
            live["runtime"]["_opencode_endpoints"] = {
                "pm": {"url": "http://127.0.0.1:43210", "password": SecretStr("fake-server-password")}}
            try:
                yield live
            finally:
                captured["servers_closed"] = True

        async def provider_boundary(adapter, inp):
            await adapter.emit_usage(inp.tools, TurnUsage(input_tokens=10, output_tokens=5))

        class LocalAgent:
            agent_name = "Factory PM"
            def __init__(self, adapter):
                self.adapter = adapter
            async def start(self):
                tools = AgentTools(ROOM, None, [], agent_id=PM)
                tools.send_event = AsyncMock(return_value={"ok": True})
                inp = AgentInput(msg=SimpleNamespace(id=EVENT, content="Synthetic turn"), tools=tools,
                                 history=None, participants_msg=None, contacts_msg=None,
                                 is_session_bootstrap=True, room_id=ROOM)
                await self.adapter.on_event(inp)
                # Auxiliary title/compaction failure happens after main turn
                # telemetry succeeded, so SDK usage alone cannot catch it.
                key = guard.reserve(MODEL_IDS[0], 16)
                guard.unknown(key)
                captured["guard_bytes"] = guard.path.read_bytes()
            async def stop(self, timeout):
                captured["stopped"] = True
                await self.adapter.on_cleanup(ROOM)

        with patch.object(runtime, "require_ready"), \
             patch.object(runtime, "credentials", return_value={"pm": {"agent_id": PM, "api_key": "fake"}}), \
             patch.object(runtime, "session_ledger", side_effect=ledger_factory), \
             patch.object(runtime.psutil, "Process", return_value=SimpleNamespace(children=lambda **kwargs: [])), \
             patch.object(Agent, "create", side_effect=lambda **kwargs: LocalAgent(kwargs["adapter"])), \
             patch.object(backend, "on_event", provider_boundary), \
             patch.object(harnesses, "start_runtime", servers):
            try:
                await asyncio.wait_for(runtime.serve(cfg, "rehearsal", "owned-test-token"), 2)
            finally:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    asyncio.get_running_loop().remove_signal_handler(sig)
        self.assertTrue(captured["stopped"])
        self.assertTrue(captured["servers_closed"])
        self.assertEqual(captured["ledger"].data["tokens"], 15)
        self.assertIn("Request budget guard blocked", captured["ledger"].data["stopped_reason"])
        self.assertTrue(captured["ledger"].stop.is_set())
        self.assertEqual(guard.path.read_bytes(), captured["guard_bytes"])
        self.assertEqual(guard.totals()["held_tokens"], 80)


if __name__ == "__main__":
    unittest.main()
