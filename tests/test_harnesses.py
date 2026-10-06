"""Backend selection/configuration tests; no provider inference or BAND calls."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from factorykit import harnesses as h


def config(root, harness="claude-code"):
    return {"runtime": {"harness": harness, "claude_command": "/test/claude", "opencode_command": "/test/opencode",
                        "model": "sonnet" if harness == "claude-code" else "openai/model",
                        "sandbox": "native-policy", "native_permissions": {
                            "read": True, "write": True, "bash": False, "network": False}},
            "paths": {"factory": str(root), "rehearsal": str(root), "result": str(root)},
            "budgets": {"turn_timeout_seconds": 90, "billing_mode": "spend_cap"},
            "seats": [{"id": "pm", "harness": h.harness_label(harness),
                       "model": "sonnet" if harness == "claude-code" else "openai/model",
                       "reasoning_effort": "high" if harness == "claude-code" else None,
                       "git_name": "Factory PM", "git_email": "pm@factory.invalid"}]}


class SelectionTests(unittest.TestCase):
    def test_legacy_missing_runtime_harness_is_codex(self):
        cfg = {"runtime": {}, "seats": [{"harness": "Codex test", "model": "test-model"}]}
        self.assertEqual(h.selected_harness(cfg), "codex")
        self.assertEqual(h.validate_selection(cfg), [])

    def test_mixed_harnesses_rejected(self):
        cfg = config(Path("/tmp"))
        cfg["seats"][0]["harness"] = "Codex"
        self.assertIn("uniform profile", ";".join(h.validate_selection(cfg)))

    def test_opencode_requires_provider_model(self):
        cfg = config(Path("/tmp"), "opencode")
        cfg["seats"][0]["model"] = "model"
        self.assertIn("provider/model", ";".join(h.validate_selection(cfg)))

    def test_permissions_must_be_explicit_and_typed(self):
        cfg = config(Path("/tmp"))
        self.assertEqual(h.permission_errors(cfg), [])
        cfg["runtime"]["native_permissions"]["bash"] = "false"
        self.assertTrue(h.permission_errors(cfg))

    def test_codex_permission_profile_cannot_transfer(self):
        cfg = config(Path("/tmp"))
        cfg["runtime"]["permission_profile"] = "unattended"
        self.assertIn("Codex-specific", ";".join(h.permission_errors(cfg)))

    def test_exact_model_and_effort_catalog(self):
        cfg = config(Path("/tmp"))
        catalog = {"harness": "claude-code", "models": [{"id": "sonnet", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]}]}
        self.assertEqual(h.model_errors(cfg, catalog), [])
        cfg["seats"][0]["reasoning_effort"] = "max"
        self.assertTrue(h.model_errors(cfg, catalog))

    def test_opencode_requires_connected_provider(self):
        cfg = config(Path("/tmp"), "opencode")
        row = {"id": "openai/model", "connected": False, "supportedReasoningEfforts": []}
        self.assertIn("not connected", ";".join(h.model_errors(cfg, {"harness": "opencode", "models": [row]})))


class NativePolicyTests(unittest.TestCase):
    def test_resolved_paths_reject_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            workspace = Path(root)
            (workspace / "escape").symlink_to(outside, target_is_directory=True)
            policy = dict(read=True, write=True, bash=False, network=False)
            self.assertTrue(h.native_tool_allowed(policy, workspace, "Write", {"file_path": "safe.txt"}))
            self.assertFalse(h.native_tool_allowed(policy, workspace, "Read", {"file_path": "escape/private"}))
            self.assertFalse(h.native_tool_allowed(policy, workspace, "Write", {"file_path": "../outside"}))
            self.assertFalse(h.native_tool_allowed(policy, workspace, "Glob", {"pattern": "../*"}))

    def test_unlisted_native_tools_and_shell_are_denied(self):
        policy = dict(read=True, write=True, bash=False, network=False)
        for name in ["Bash", "Agent", "Task", "Skill", "WebFetch", "unknown"]:
            self.assertFalse(h.native_tool_allowed(policy, Path("/tmp"), name, {}))

    def test_opencode_policy_has_deny_default_and_external_directory(self):
        policy = h.opencode_permissions(dict(read=True, write=False, bash=False, network=False))
        self.assertEqual(policy["*"], "deny")
        self.assertEqual(policy["external_directory"], "deny")
        self.assertEqual(policy["read"], "allow")
        self.assertEqual(policy["edit"], "deny")


class ActualAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    async def test_claude_config_and_actual_permission_callback(self):
        from band.adapters import ClaudeSDKAdapter
        cfg = config(self.root)
        adapter_config = h.alternate_adapter_config(cfg, cfg["seats"][0], "rehearsal", self.root, "instructions", {"GIT_AUTHOR_NAME": "PM"})
        self.assertEqual(adapter_config.model, "sonnet")
        self.assertEqual(adapter_config.effort, "high")
        self.assertEqual(adapter_config.setting_sources, ())
        self.assertEqual(adapter_config.cli.env["GIT_AUTHOR_NAME"], "PM")
        adapter = h.adapter_class(cfg)(adapter_config, **h.adapter_options(cfg))
        self.assertIsInstance(adapter, ClaudeSDKAdapter)
        callback = adapter._make_can_use_tool("room")
        allowed = await callback("Write", {"file_path": str(self.root / "result.txt")}, SimpleNamespace(tool_use_id="write"))
        denied = await callback("Write", {"file_path": "/outside/result.txt"}, SimpleNamespace(tool_use_id="write"))
        self.assertEqual(allowed.behavior, "allow")
        self.assertEqual(denied.behavior, "deny")

    async def test_claude_task_events_are_not_unsupported_emit(self):
        from band.core.types import Emit
        cfg = config(self.root)
        self.assertNotIn(Emit.TASK_EVENTS, h.adapter_options(cfg)["emit"])
        self.assertIn(Emit.TASK_EVENTS, h.adapter_options(config(self.root, "opencode"))["emit"])

    async def test_opencode_requires_owned_endpoint(self):
        cfg = config(self.root, "opencode")
        with self.assertRaisesRegex(ValueError, "owned local server"):
            h.alternate_adapter_config(cfg, cfg["seats"][0], "rehearsal", self.root, "instructions", {})

    def _opencode(self):
        cfg = config(self.root, "opencode")
        cfg["runtime"]["_opencode_endpoints"] = {"pm": {"url": "http://127.0.0.1:1234", "password": "ephemeral-test"}}
        conf = h.alternate_adapter_config(cfg, cfg["seats"][0], "rehearsal", self.root, "instructions", {})
        return conf, h.adapter_class(cfg)(conf, **h.adapter_options(cfg))

    async def test_opencode_config_pins_env_defaults_and_native_tool_mask(self):
        with patch.dict(os.environ, {"OPENCODE_APPROVAL_MODE": "auto_accept", "OPENCODE_BASE_URL": "https://unexpected.invalid"}):
            conf, adapter = self._opencode()
        self.assertEqual(conf.base_url, "http://127.0.0.1:1234")
        self.assertEqual(conf.provider_id, "openai")
        self.assertEqual(conf.model_id, "model")
        self.assertEqual(conf.approval_mode, "auto_decline")
        self.assertEqual(conf.agent, "factory")
        mask = adapter._mcp_tool_visibility()
        self.assertNotIn("*", mask)
        self.assertNotIn("bash", mask)
        self.assertNotIn("read", mask)
        self.assertFalse(mask[f"{adapter._mcp_server_name}_*"])
        self.assertNotIn("factory_http_password", conf.model_dump())

    async def test_opencode_real_http_client_receives_ephemeral_auth(self):
        import httpx
        conf, adapter = self._opencode()
        client = adapter._default_client_factory(conf)
        try:
            request = client._client.build_request("GET", "/global/health")
            authorized = next(client._client.auth.auth_flow(request))
            self.assertTrue(authorized.headers["authorization"].startswith("Basic "))
        finally:
            await client.close()

    async def test_opencode_error_with_text_still_marks_turn_failed(self):
        _, adapter = self._opencode()
        tools = SimpleNamespace(terminal_status=None, send_failure=AsyncMock())
        turn = SimpleNamespace(last_error_message="provider failed", text_parts={"text": "partial answer"}, tools=tools)
        await adapter._deliver_fallback_text("room", turn)
        self.assertEqual(tools.terminal_status, "failed")
        tools.send_failure.assert_awaited_once()

    async def test_opencode_delivery_failure_survives_failed_event_send(self):
        _, adapter = self._opencode()
        tools = SimpleNamespace(terminal_status=None, send_event=AsyncMock(side_effect=RuntimeError("offline")))
        await adapter._report_delivery_failure("room", SimpleNamespace(tools=tools))
        self.assertEqual(tools.terminal_status, "failed")

    async def test_opencode_missing_reply_fails_instead_of_posting_success_filler(self):
        _, adapter = self._opencode()
        tools = SimpleNamespace(terminal_status=None, send_failure=AsyncMock())
        turn = SimpleNamespace(last_error_message=None, replied_via_room_tool=False, text_parts={}, tools=tools)
        await adapter._deliver_fallback_text("room", turn)
        self.assertEqual(tools.terminal_status, "failed")
        tools.send_failure.assert_awaited_once()

    async def test_opencode_catalog_does_not_call_prompt_endpoint(self):
        response = Mock()
        response.json.return_value = {"connected": ["openai"], "all": [{"id": "openai", "models": {"model": {"variants": {"high": {}, "low": {}}}}}]}
        client = SimpleNamespace(get=AsyncMock(return_value=response))
        result = await h._opencode_catalog(client)
        client.get.assert_awaited_once_with("/provider")
        self.assertEqual(result["models"][0]["id"], "openai/model")
        self.assertEqual(len(result["models"][0]["supportedReasoningEfforts"]), 2)

    async def test_owned_process_cleanup_is_bounded(self):
        process = SimpleNamespace(returncode=None, terminate=Mock(), kill=Mock(), wait=AsyncMock())
        await h._terminate(process)
        process.terminate.assert_called_once()
        process.wait.assert_awaited_once()
        process.kill.assert_not_called()

    async def test_owned_server_cleans_up_after_invalid_effective_permissions(self):
        import httpx
        cfg = config(self.root, "opencode")
        process = SimpleNamespace(returncode=None, terminate=Mock(), kill=Mock(), wait=AsyncMock())
        reservation = Mock()
        reservation.__enter__ = Mock(return_value=reservation)
        reservation.__exit__ = Mock(return_value=None)
        reservation.getsockname.return_value = ("127.0.0.1", 12345)
        health = Mock()
        effective = Mock()
        effective.json.return_value = {"agent": {"factory": {"permission": {"*": "allow"}}}}
        client = SimpleNamespace(get=AsyncMock(side_effect=[health, effective]))
        context = Mock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=None)
        with patch.object(h.socket, "socket", return_value=reservation), \
             patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)) as spawn, \
             patch.object(httpx, "AsyncClient", return_value=context):
            with self.assertRaisesRegex(ValueError, "permission policy differs"):
                async with h._opencode_server(cfg, self.root, "openai/model", cfg["runtime"]["native_permissions"], {"GIT_AUTHOR_NAME": "PM"}):
                    self.fail("Unsafe server was yielded")
            environment = spawn.call_args.kwargs["env"]
            self.assertEqual(environment["GIT_AUTHOR_NAME"], "PM")
            self.assertTrue(environment["OPENCODE_SERVER_PASSWORD"])
            self.assertIn("--pure", spawn.call_args.args)
        process.terminate.assert_called_once()
        process.wait.assert_awaited_once()

    async def test_owned_server_hanging_health_has_overall_deadline_and_cleanup(self):
        import httpx
        cfg = config(self.root, "opencode")
        process = SimpleNamespace(returncode=None, terminate=Mock(), kill=Mock(), wait=AsyncMock())
        reservation = Mock()
        reservation.__enter__ = Mock(return_value=reservation)
        reservation.__exit__ = Mock(return_value=None)
        reservation.getsockname.return_value = ("127.0.0.1", 12345)
        request_cancelled = asyncio.Event()

        async def hung_request(_path):
            try:
                await asyncio.Event().wait()
            finally:
                request_cancelled.set()

        client = SimpleNamespace(get=AsyncMock(side_effect=hung_request))
        context = Mock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=None)
        with patch.object(h.socket, "socket", return_value=reservation), \
             patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)), \
             patch.object(httpx, "AsyncClient", return_value=context), \
             patch.object(h, "OPENCODE_READY_TIMEOUT_SECONDS", 0.02):
            async with asyncio.timeout(1):
                with self.assertRaisesRegex(ValueError, "readiness exceeded"):
                    async with h._opencode_server(cfg, self.root, "openai/model", cfg["runtime"]["native_permissions"], {}):
                        self.fail("Hanging server was yielded")
        self.assertTrue(request_cancelled.is_set())
        client.get.assert_awaited_once_with("/global/health")
        process.terminate.assert_called_once()
        process.wait.assert_awaited_once()
        context.__aexit__.assert_awaited_once()

    async def test_claude_real_sdk_hanging_initialization_is_cancelled_and_closed(self):
        import claude_agent_sdk
        from claude_agent_sdk._internal.transport import Transport
        real_client = claude_agent_sdk.ClaudeSDKClient

        class HangingInitializationTransport(Transport):
            def __init__(self):
                self.connected = False
                self.closed = False
                self.sent = []

            async def connect(self):
                self.connected = True

            async def write(self, data):
                self.sent.append(json.loads(data))

            async def read_messages(self):
                await asyncio.Event().wait()
                yield {}  # The initialized control response never arrives.

            async def close(self):
                self.closed = True

            async def end_input(self):
                pass

            def is_ready(self):
                return self.connected and not self.closed

        transport = HangingInitializationTransport()
        with patch.object(claude_agent_sdk, "ClaudeSDKClient", side_effect=lambda options: real_client(options, transport=transport)), \
             patch.object(h, "DISCOVERY_TIMEOUT_SECONDS", 0.02):
            async with asyncio.timeout(1):
                with self.assertRaisesRegex(ValueError, "Claude Code model discovery exceeded"):
                    await h.discover_models(config(self.root))
        self.assertTrue(transport.connected)
        self.assertTrue(transport.closed)
        self.assertTrue(transport.sent)
        self.assertTrue(all(message.get("type") == "control_request" for message in transport.sent))
        self.assertEqual(transport.sent[0]["request"]["subtype"], "initialize")

    async def test_non_opencode_runtime_does_not_spawn(self):
        cfg = config(self.root)
        with patch.object(asyncio, "create_subprocess_exec") as spawn:
            async with h.start_runtime(cfg, "rehearsal", cfg["seats"]) as selected:
                self.assertIs(selected, cfg)
            spawn.assert_not_called()


class AuthenticationTests(unittest.TestCase):
    def test_claude_subscription_status_requires_oauth_subscription(self):
        cfg = config(Path("/tmp"))
        cfg["budgets"]["billing_mode"] = "subscription_only"
        result = SimpleNamespace(returncode=0, stdout=json.dumps({"loggedIn": True, "authMethod": "api_key"}))
        with patch.object(subprocess := h.subprocess, "run", return_value=result), patch.dict(os.environ, {}, clear=True):
            self.assertTrue(h.auth_errors(cfg))
            result.stdout = json.dumps({"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "max"})
            self.assertEqual(h.auth_errors(cfg), [])

    def test_opencode_never_claims_subscription_billing(self):
        cfg = config(Path("/tmp"), "opencode")
        cfg["budgets"]["billing_mode"] = "subscription_only"
        self.assertIn("cannot verify", ";".join(h.auth_errors(cfg)))


if __name__ == "__main__":
    unittest.main()
