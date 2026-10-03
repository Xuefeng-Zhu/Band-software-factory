"""No model calls: budget authorization and aggregate consumption regressions."""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import yaml

from factorykit.budgets import API_ENVIRONMENT, budget_blockers, budget_errors, codex_argv, subscription_auth_errors, subscription_auth_probe
from factorykit.runtime import GateError, adapter_config, session_ledger


class SubscriptionBudgetTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.config = yaml.safe_load((root / "config/factory.example.yaml").read_text())
        self.config["paths"]["factory"] = str(root)
        self.config["runtime"]["codex_command"] = str(root / "scripts/codex-local")
        for seat in self.config["seats"]:
            seat["mandate"] = str(root / "mandates" / f"factory-{seat['id']}.md")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for key in ("runs", "rehearsal", "result"):
            self.config["paths"][key] = str(self.root / key)
            (self.root / key).mkdir()
        self.config["band"].update(rehearsal_room_id="toy-room", judged_room_id="judged-room")
        self.config["budgets"].update(billing_mode="subscription_only", approved=False,
            api_billing_allowed=False, paid_provisioning_allowed=False, spend_cap_usd=None,
            max_total_tokens=100, max_turns_per_seat=2,
            turn_timeout_seconds=10, stage_timeout_seconds=30, overall_timeout_seconds=100)

    def tearDown(self):
        self.temp.cleanup()

    def test_subscription_requires_explicit_approval_without_dollar_cap(self):
        self.assertEqual(budget_errors(self.config["budgets"]), [])
        self.assertTrue(any("approved=false" in e for e in budget_blockers(self.config["budgets"])))
        self.config["budgets"]["approved"] = True
        self.assertEqual(budget_blockers(self.config["budgets"]), [])
        for cap in (0, 1, True, float("nan"), float("inf")):
            with self.subTest(cap=cap):
                self.assertTrue(budget_errors(dict(self.config["budgets"], spend_cap_usd=cap)))

    def test_unapproved_or_malformed_policy_cannot_pass(self):
        for name, value in (("billing_mode", "unlimited"), ("approved", "true"),
                ("max_total_tokens", 0), ("max_turns_per_seat", True),
                ("overall_timeout_seconds", float("inf")),
                ("api_billing_allowed", True), ("paid_provisioning_allowed", None)):
            with self.subTest(name=name):
                self.assertTrue(budget_blockers(dict(self.config["budgets"], **{name: value})))
        legacy = dict(self.config["budgets"], billing_mode="spend_cap", approved=True)
        self.assertTrue(budget_blockers(legacy))
        self.assertEqual(budget_blockers(dict(legacy, spend_cap_usd=1)), [])

    @patch("factorykit.budgets.subscription_auth_probe", new_callable=AsyncMock, return_value=True)
    @patch("factorykit.common.run_command")
    def test_existing_chatgpt_checked_before_forced_probe(self, run, probe):
        with patch.dict(os.environ, {}, clear=True):
            for output in ("Logged in using an API key", "", "Logged in using ChatGPT but unverified"):
                run.return_value = {"exit_code": 0, "stdout": output, "stderr": ""}
                self.assertTrue(subscription_auth_errors(self.config))
                probe.assert_not_called()
            run.return_value = {"exit_code": 0, "stdout": "", "stderr": "Logged in using ChatGPT\n"}
            self.assertEqual(subscription_auth_errors(self.config), [])
        self.assertEqual(run.call_args.args[0], [self.config["runtime"]["codex_command"], "login", "status"])

    @patch("factorykit.common.run_command")
    def test_external_auth_rejected_without_reading_or_logging_values(self, run):
        for name in API_ENVIRONMENT:
            with patch.dict(os.environ, {name: "secret-never-log"}, clear=True):
                errors = subscription_auth_errors(self.config)
                self.assertTrue(errors)
                self.assertNotIn("secret-never-log", str(errors))
        run.assert_not_called()

    @patch("factorykit.budgets.subscription_auth_probe", new_callable=AsyncMock)
    @patch("factorykit.common.run_command", return_value={"exit_code": 0, "stdout": "Logged in using ChatGPT", "stderr": ""})
    def test_effective_probe_failure_is_closed_and_redacted(self, run, probe):
        with patch.dict(os.environ, {}, clear=True):
            probe.return_value = False
            self.assertTrue(subscription_auth_errors(self.config))
            probe.side_effect = RuntimeError("secret-response")
            self.assertNotIn("secret-response", str(subscription_auth_errors(self.config)))

    def test_sdk_command_deletes_auth_overrides_and_pins_provider(self):
        argv = codex_argv(self.config, "app-server", "--listen", "stdio://")
        self.assertEqual(argv[0], "/usr/bin/env")
        for name in API_ENVIRONMENT:
            self.assertIn(["-u", name], [argv[i:i+2] for i in range(len(argv)-1)])
        self.assertIn('forced_login_method="chatgpt"', argv)
        self.assertIn('model_provider="openai"', argv)
        self.assertIn('openai_base_url=""', argv)
        conf = adapter_config(self.config, self.config["seats"][0], "rehearsal")
        self.assertEqual(list(conf.codex_command), argv)

    def test_probe_reads_only_auth_and_effective_config_for_every_workspace(self):
        client = AsyncMock()
        client.request.side_effect = lambda method, params: ({"requiresOpenaiAuth": True, "account": {"type": "chatgpt"}} if method == "account/read" else {"config": {"model_provider": "openai", "forced_login_method": "chatgpt"}})
        self.config["seats"][0]["judged_cwd"] = str(self.root / "worktree")
        with patch("band.integrations.codex.stdio_client.CodexStdioClient", return_value=client):
            self.assertTrue(asyncio.run(subscription_auth_probe(self.config)))
        methods = [call.args[0] for call in client.request.call_args_list]
        self.assertEqual(methods, ["account/read", "config/read", "config/read", "config/read", "config/read"])
        self.assertEqual(client.request.call_args_list[0].args[1], {"refreshToken": False})
        client.close.assert_awaited_once()

    def test_effective_managed_provider_override_rejected(self):
        client = AsyncMock()
        client.request.side_effect = [{"requiresOpenaiAuth": True, "account": {"type": "chatgpt"}}, {"config": {"model_provider": "other", "forced_login_method": "chatgpt"}}]
        with patch("band.integrations.codex.stdio_client.CodexStdioClient", return_value=client):
            self.assertFalse(asyncio.run(subscription_auth_probe(self.config)))

    def test_rooms_share_turns_tokens_and_first_turn_clock(self):
        with patch("factorykit.runtime.time.time", return_value=100):
            toy = session_ledger(self.config, "rehearsal")
            self.assertIsNone(toy.data["started_epoch"])
            self.assertTrue(toy.reserve("pm"))
            toy.record("pm", {"codex_thread_id": "t", "codex_total_tokens": 60})
        with patch("factorykit.runtime.time.time", return_value=120):
            judged = session_ledger(self.config, "judged")
            self.assertEqual(judged.data["started_epoch"], 100)
            self.assertTrue(judged.reserve("pm"))
            self.assertFalse(judged.reserve("pm"))
            judged.record("qa", {"codex_thread_id": "t", "codex_total_tokens": 45})
            self.assertEqual(judged.data["tokens"], 105)
            self.assertFalse(judged.reserve("qa"))
            restored = session_ledger(self.config, "rehearsal")
            self.assertEqual(restored.data["tokens"], 105)
            self.assertFalse(restored.reserve("qa"))

    def test_stage_clock_is_room_scoped_but_overall_cannot_reset(self):
        with patch("factorykit.runtime.time.time", return_value=100):
            toy = session_ledger(self.config, "rehearsal")
            toy.reserve("pm")
        with patch("factorykit.runtime.time.time", return_value=135):
            toy.halt(toy.reason())
            judged = session_ledger(self.config, "judged")
            self.assertIsNone(judged.reason())
            judged.reserve("qa")
            self.assertEqual(judged.data["room_started_epochs"]["judged-room"], 135)
            self.assertEqual(judged.data["started_epoch"], 100)
        with patch("factorykit.runtime.time.time", return_value=201):
            judged = session_ledger(self.config, "judged")
            self.assertEqual(judged.reason(), "overall time budget exhausted")
            self.assertFalse(judged.reserve("reviewer"))

    def test_legacy_ledgers_and_changed_rooms_fail_closed(self):
        legacy = self.root / "runs/runtime/budget-rehearsal.json"
        legacy.parent.mkdir()
        legacy.write_text("{}")
        with self.assertRaises(GateError):
            session_ledger(self.config, "judged")
        legacy.unlink()
        session_ledger(self.config, "rehearsal")
        self.config["band"]["judged_room_id"] = "changed"
        with self.assertRaises(GateError):
            session_ledger(self.config, "judged")


if __name__ == "__main__":
    unittest.main()
