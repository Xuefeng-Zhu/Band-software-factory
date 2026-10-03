import asyncio
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from factorykit.runtime import (
    AuditedTools, BudgetLedger, GateError, RoomPreprocessor, adapter_config,
    credentials, is_owned, preflight_runtime, process_identity, room_workspace,
    slash_command,
    judged_launch_errors,
    docker_environment,
)
import psutil
import yaml

FACTORY = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((FACTORY / "config/factory.example.yaml").read_text())
        self.config["paths"]["factory"] = str(FACTORY)
        for seat in self.config["seats"]:
            seat["mandate"] = str(FACTORY / "mandates" / f"factory-{seat['id']}.md")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config["paths"]["runs"] = str(self.root / "runs")
        self.config["paths"]["result"] = str(self.root / "result")
        self.config["paths"]["rehearsal"] = str(self.root / "rehearsal")
        (self.root / "result").mkdir()
        (self.root / "rehearsal").mkdir()
        self.config["band"]["rehearsal_room_id"] = "room-allowed"
        self.config["band"]["credentials_file"] = str(self.root / "credentials.yaml")
        self.config["budgets"]["max_active_seats"] = 1
        self.config["budgets"]["approved"] = False
        # Keep baseline coverage independent of the evolving example defaults.
        self.config["runtime"].pop("permission_profile", None)
        self.config["runtime"].pop("docker_host", None)
        self.config["runtime"].update(sandbox="workspace-write", allow_network=False, approval_policy="never", approval_mode="auto_decline")

    def tearDown(self):
        self.temp.cleanup()

    def test_slash_commands_cannot_override_budget_policy(self):
        for text in ["/model costly", "@owner/agent /sandbox danger-full-access", "@[[6b5c2cba-e7ae-441d-a982-74bdbd1f6740]] /approve-session x", " /reasoning\txhigh", "/thread new"]:
            self.assertTrue(slash_command(text), text)
        self.assertFalse(slash_command("Do not /model switch"))

    def test_room_preprocessor_rejects_unknown_rooms_without_hydration(self):
        from band.platform.event import MessageEvent
        guard = RoomPreprocessor("room-allowed")
        guard.default.process = AsyncMock()
        asyncio.run(guard.process(None, MessageEvent(room_id="wrong"), "a"))
        guard.default.process.assert_not_called()

    def test_no_credentials_and_budget_never_ready(self):
        blockers = preflight_runtime(self.config)
        self.assertTrue(any("credentials" in text for text in blockers))
        self.assertTrue(any("budget" in text for text in blockers))
        self.assertTrue(any("permissions_agent_write_git" in text for text in blockers))
        self.assertTrue(any("registration" in text for text in blockers))

    def test_cannot_enable_concurrency_in_shared_checkout(self):
        self.config["budgets"]["max_active_seats"] = 2
        self.assertIn("Shared checkouts require max_active_seats=1; use the real single-writer fallback.", preflight_runtime(self.config))

    def test_adapter_constructs_with_supported_workspace_resolver(self):
        from band.adapters import CodexAdapter
        from band.core.types import Emit
        seat = self.config["seats"][0]
        seat["mandate"] = str(self.root / "mandate.md")
        Path(seat["mandate"]).write_text("Test instructions")
        conf = adapter_config(self.config, seat, "rehearsal")
        adapter = CodexAdapter(conf, emit=[Emit.TOOL_CALLS, Emit.TASK_EVENTS, Emit.USAGE])
        self.assertEqual(conf.workspace_for_room("room-allowed"), str((self.root / "rehearsal").resolve()))
        with self.assertRaises(GateError):
            conf.workspace_for_room("wrong")
        self.assertIsNone(conf.cwd)
        self.assertFalse(conf.enable_self_config_tools)
        self.assertEqual(conf.approval_mode, "auto_decline")
        self.assertFalse(conf.sandbox_policy["networkAccess"])
        self.assertEqual(conf.reasoning_summary, "none")
        self.assertNotIn(Emit.THOUGHTS, adapter.features.emit)
        self.assertIn(Emit.TASK_EVENTS, adapter.features.emit)
        self.assertEqual(conf.codex_env["GIT_AUTHOR_NAME"], seat["git_name"])
        self.assertIn("Full handoffs and receipts", conf.custom_section)
        with patch.dict(os.environ, {"CODEX_SYSTEM_PROMPT": "override", "CODEX_ENABLE_SELF_CONFIG_TOOLS": "true", "CODEX_SANDBOX": "danger-full-access"}):
            protected = adapter_config(self.config, seat, "rehearsal")
        self.assertIsNone(protected.system_prompt)
        self.assertFalse(protected.enable_self_config_tools)
        self.assertEqual(protected.sandbox, "workspace-write")

    def test_judged_start_cannot_bypass_ready_freeze(self):
        self.assertIn("Judged start requires a READY_TO_LAUNCH freeze.", judged_launch_errors(self.config))

    def test_named_profile_inherits_on_both_sdk_thread_and_turn_without_environment_override(self):
        from band.adapters import CodexAdapter
        from factorykit.permissions import profile_arguments
        profile = {"name": "factory-test", "domains": ["pypi.org", "localhost", "127.0.0.1"], "allow_local_binding": True, "unix_sockets": ["/tmp/factory-test.sock"]}
        self.config["runtime"]["permission_profile"] = profile
        with patch.dict(os.environ, {"CODEX_SANDBOX": "danger-full-access", "CODEX_SANDBOX_POLICY": '{"type":"dangerFullAccess"}'}):
            conf = adapter_config(self.config, self.config["seats"][0], "rehearsal")
        self.assertIsNone(conf.sandbox)
        self.assertIsNone(conf.sandbox_policy)
        argv = list(conf.codex_command)
        expected = profile_arguments(**profile)
        index = argv.index(expected[1]) - 1
        self.assertEqual(argv[index:index + len(expected)], expected)
        self.assertLess(index, argv.index("app-server"))
        adapter = CodexAdapter(conf)
        thread, turn = {}, {}
        adapter._apply_thread_sandbox(thread, room_id="room-allowed")
        adapter._apply_turn_sandbox(turn, room_id="room-allowed")
        self.assertEqual(thread, {})
        self.assertEqual(turn, {})

    def test_invalid_profile_cannot_fall_back_to_legacy_adapter(self):
        from factorykit.common import FactoryError
        self.config["runtime"]["permission_profile"] = {"name": "factory-test", "domains": ["*"]}
        with self.assertRaises(FactoryError):
            adapter_config(self.config, self.config["seats"][0], "rehearsal")
        with patch("factorykit.runtime.subscription_auth_errors", return_value=[]):
            blockers = preflight_runtime(self.config)
        self.assertTrue(any("Invalid runtime.permission_profile" in error for error in blockers))

    def test_valid_profile_does_not_replace_required_observed_permission_evidence(self):
        self.config["runtime"]["permission_profile"] = {"name": "factory-test", "domains": ["pypi.org"]}
        with patch("factorykit.runtime.subscription_auth_errors", return_value=[]):
            blockers = preflight_runtime(self.config)
        self.assertFalse(any("Invalid runtime.permission_profile" in error for error in blockers))
        for check in ("permissions_agent_write_git", "permissions_docker_build", "permissions_browser", "permissions_development_network"):
            self.assertTrue(any(check in error for error in blockers))

    def test_docker_environment_is_private_isolated_and_pinned_for_each_room(self):
        self.config["runtime"].update(permission_profile={"name": "factory-test", "domains": ["pypi.org"], "unix_sockets": ["/tmp/factory-test.sock"]}, docker_host="unix:///tmp/factory-test.sock")
        self.config["band"]["judged_room_id"] = "room-judged"
        paths = []
        with patch("factorykit.runtime.tempfile.gettempdir", return_value=str(self.root)), patch.dict(os.environ, {"DOCKER_HOST": "tcp://wrong:2375", "DOCKER_CONTEXT": "wrong", "BUILDX_CONFIG": "/not-writable"}):
            for mode in ("rehearsal", "judged"):
                for seat in self.config["seats"][:2]:
                    conf = adapter_config(self.config, seat, mode)
                    self.assertEqual(conf.codex_env["DOCKER_HOST"], "unix:///tmp/factory-test.sock")
                    self.assertEqual(conf.codex_env["DOCKER_CONTEXT"], "")
                    directory = Path(conf.codex_env["BUILDX_CONFIG"])
                    self.assertEqual(directory.parent, self.root.resolve())
                    self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                    self.assertEqual(docker_environment(self.config, seat, mode)["BUILDX_CONFIG"], str(directory))
                    paths.append(directory)
            other = copy.deepcopy(self.config)
            other["paths"]["factory"] += "-other"
            self.assertNotIn(Path(docker_environment(other, other["seats"][0], "rehearsal")["BUILDX_CONFIG"]), paths)
        self.assertEqual(len(set(paths)), 4)

    def test_docker_state_rejects_symlink_and_shared_directory(self):
        self.config["runtime"].update(permission_profile={"name": "factory-test", "domains": ["pypi.org"], "unix_sockets": ["/tmp/factory-test.sock"]}, docker_host="unix:///tmp/factory-test.sock")
        seat = self.config["seats"][0]
        with patch("factorykit.runtime.tempfile.gettempdir", return_value=str(self.root)):
            directory = Path(docker_environment(self.config, seat, "rehearsal")["BUILDX_CONFIG"])
            directory.rmdir()
            directory.symlink_to(self.root / "result", target_is_directory=True)
            with self.assertRaises(GateError):
                docker_environment(self.config, seat, "rehearsal")
            directory.unlink()
            directory.mkdir(mode=0o755)
            with self.assertRaises(GateError):
                docker_environment(self.config, seat, "rehearsal")
            self.assertEqual(list((self.root / "result").iterdir()), [])

    def test_pm_membership_restore_is_exact_and_bounded(self):
        async def scenario():
            ledger = BudgetLedger(self.config["budgets"], self.root / "m.json", "r")
            base = SimpleNamespace(get_participants=AsyncMock(return_value=[]), add_participant=AsyncMock(return_value={"status": "added"}))
            roster = [{"id": "qa", "agent_id": "registered-qa", "handle": "owner/qa", "display_name": "Factory QA"}]
            pm = AuditedTools(base, ledger, "pm", self.root / "events", roster)
            with self.assertRaises(GateError):
                await pm.add_participant("some-stranger")
            peer = AuditedTools(base, ledger, "qa", self.root / "events", roster)
            with self.assertRaises(GateError):
                await peer.add_participant("registered-qa")
            await pm.add_participant("owner/qa")
            base.add_participant.assert_awaited_with("registered-qa", role="member")
            await pm.add_participant("registered-qa")
            with self.assertRaises(GateError):
                await pm.add_participant("registered-qa")
        asyncio.run(scenario())

    def test_pid_reuse_or_token_mismatch_is_never_owned(self):
        proc = psutil.Process()
        identity = process_identity(proc)
        self.assertTrue(is_owned(identity))
        wrong = dict(identity, created=identity["created"] - 5)
        self.assertFalse(is_owned(wrong))
        self.assertFalse(is_owned(identity, "not-the-owner-token"))
        wrong = dict(identity, cmdline=["unrelated"])
        self.assertFalse(is_owned(wrong))

    def test_credential_permissions_checked_before_parse(self):
        path = Path(self.config["band"]["credentials_file"])
        path.write_text("secret-test: private")
        path.chmod(0o644)
        with self.assertRaisesRegex(GateError, "owner-only"):
            credentials(self.config)

    def test_token_deltas_restart_and_finite_turns(self):
        async def scenario():
            limits = dict(self.config["budgets"], max_total_tokens=100, max_turns_per_seat=2)
            path = self.root / "budget.json"
            ledger = BudgetLedger(limits, path, "room")
            self.assertTrue(ledger.reserve("pm"))
            self.assertTrue(ledger.reserve("pm"))
            self.assertFalse(ledger.reserve("pm"))
            ledger.record("pm", {"codex_thread_id": "t", "codex_total_tokens": 40})
            ledger.record("pm", {"codex_thread_id": "t", "codex_total_tokens": 40})
            restored = BudgetLedger(limits, path, "room")
            restored.record("pm", {"codex_thread_id": "t", "codex_total_tokens": 80})
            restored.record("qa", {"codex_thread_id": "other", "codex_total_tokens": 25})
            self.assertEqual(restored.data["tokens"], 105)
            self.assertTrue(restored.stop.is_set())
            self.assertFalse(restored.reserve("qa"))
            with self.assertRaises(GateError):
                BudgetLedger(limits, path, "wrong-room")
        asyncio.run(scenario())

    def test_thoughts_suppressed_and_audit_does_not_copy_tool_secrets(self):
        async def scenario():
            ledger = BudgetLedger(self.config["budgets"], self.root / "b.json", "r")
            base = SimpleNamespace(send_event=AsyncMock())
            audit = self.root / "events.jsonl"
            tools = AuditedTools(base, ledger, "pm", audit)
            await tools.send_event("private", "thought", {"secret": "never-log"})
            base.send_event.assert_not_called()
            await tools.send_event("command", "tool_call", {"command": "secret-do-not-copy", "codex_turn_id": "turn"})
            self.assertNotIn("secret", audit.read_text())
            self.assertIn("turn", audit.read_text())
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
