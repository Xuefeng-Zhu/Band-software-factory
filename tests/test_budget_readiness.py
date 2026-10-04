"""Offline cumulative-budget readiness tests using temporary synthetic ledgers.

No real configuration, consumption ledger, credentials, API, model, or worker is
modified or started. The inspector must not construct the mutating runtime ledger.
"""
import copy
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import yaml

from factorykit.budgets import persisted_budget_blockers
from factorykit.common import canonical, digest, utc_now
from factorykit.operations import freeze, launch_prepare
from factorykit.runtime import STAGE_STOP, fingerprint, judged_launch_errors, preflight_runtime

FACTORY = Path(__file__).resolve().parents[1]
ORIGIN = 1791049765.700437
TOY_ROOM = "00000000-0000-4000-8000-000000000001"
JUDGED_ROOM = "00000000-0000-4000-8000-000000000002"


class BudgetReadinessFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = yaml.safe_load((FACTORY / "config/factory.example.yaml").read_text())
        for name in ("factory", "runs", "result", "rehearsal", "challenge"):
            path = self.root / name
            path.mkdir()
            self.config["paths"][name] = str(path)
        self.config["band"].update(rehearsal_room_id=TOY_ROOM, judged_room_id=JUDGED_ROOM)
        self.config["budgets"].update(billing_mode="subscription_only", approved=True,
            api_billing_allowed=False, paid_provisioning_allowed=False, spend_cap_usd=None,
            max_active_seats=1, overall_timeout_seconds=28800, stage_timeout_seconds=1800,
            max_total_tokens=100000000, max_turns_per_seat=100)
        self.config["runtime"].pop("permission_profile", None)
        self.config["runtime"].pop("docker_host", None)
        self.config["runtime"].update(sandbox="workspace-write", allow_network=False,
                                      approval_policy="never", approval_mode="auto_decline")
        self.config["launch"]["practice_mode"] = True
        for seat in self.config["seats"]:
            mandate = self.root / "factory" / "mandates" / f"factory-{seat['id']}.md"
            mandate.parent.mkdir(exist_ok=True)
            mandate.write_text("Synthetic generic mandate.\n")
            seat.update(mandate=str(mandate), agent_id="agent-" + seat["id"],
                        handle="owner/" + seat["id"], registration_verified=True)
        self.path = self.root / "runs" / "runtime" / "budget-subscription.json"
        self.data = {"room_id": None, "room_ids": sorted([TOY_ROOM, JUDGED_ROOM]),
            "started_epoch": ORIGIN, "tokens": 9000, "turns": {"pm": 4, "architect": 2},
            "token_threads": {TOY_ROOM + ":pm:existing-thread": 9000},
            "room_started_epochs": {TOY_ROOM: ORIGIN},
            "room_turns": {TOY_ROOM: {"pm": 4, "architect": 2}},
            "room_stopped_reasons": {TOY_ROOM: STAGE_STOP}, "stopped_reason": None,
            "updated_at": "2026-10-03T21:00:00Z", "membership_attempts": {"architect": 1}}
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch("factorykit.runtime.BudgetLedger", side_effect=AssertionError("Readiness must not construct/save a budget ledger")))
        self.guards.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("Tests must remain offline")))
        self.guards.enter_context(patch("subprocess.Popen", side_effect=AssertionError("No live process may start")))

    def save_ledger(self, data=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data if data is None else data, indent=2) + "\n")
        return self.path.read_bytes()

    def assert_overall_blocked(self, blockers):
        self.assertTrue(any("overall" in message.lower() for message in blockers), blockers)

    def ready_files(self):
        factory = self.root / "factory"
        for relative in ("AGENTS.md", "pyproject.toml", "uv.lock", "config/harness-requirements.lock",
                         "tooling/codex/package.json", "tooling/codex/package-lock.json"):
            path = factory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic readiness fixture\n")
        specification = self.root / "challenge/synthetic-spec.md"
        specification.write_text("Synthetic source fixture.\n")
        (factory / "config/source-lock.json").write_text(json.dumps({"challenge": {
            "commit": "a" * 40, "files": {specification.name: digest(specification)}}}))
        task = factory / "tasks/judged-all-stages.md"
        task.parent.mkdir()
        task.write_text("Synthetic frozen task; never dispatch.\n")
        self.tasks = {"tasks": {task.name: {"sha256": digest(task)}}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        model = self.config["runtime"]["model"]
        (self.path.parent / "models.json").write_text(json.dumps({"models": [{"id": model,
            "supportedReasoningEfforts": [{"reasoningEffort": effort} for effort in
                sorted({s["reasoning_effort"] for s in self.config["seats"]})]}]}))
        for mode in ("rehearsal", "judged"):
            (self.path.parent / f"registration-{mode}.json").write_text(json.dumps({
                "config_sha256": fingerprint(self.config), "verified": True}))
        (self.root / "runs/doctor-latest.json").write_text(json.dumps({
            "status": "PASS", "created_at": utc_now(), "configuration_sha256": digest(canonical(self.config))}))

    @contextmanager
    def unrelated_checks_pass(self):
        permissions = [{"id": name} for name in ("permissions_agent_write_git", "permissions_docker_build",
                                                 "permissions_browser", "permissions_development_network")]
        with ExitStack() as stack:
            stack.enter_context(patch("factorykit.validation.run_command", return_value={
                "exit_code": 0, "stdout": json.dumps({"ServerVersion": "test", "NCPU": 4, "MemTotal": 4 * 1024 ** 3}), "stderr": ""}))
            stack.enter_context(patch("factorykit.runtime.subscription_auth_errors", return_value=[]))
            stack.enter_context(patch("factorykit.runtime.credentials", return_value={}))
            stack.enter_context(patch("factorykit.validation.observations", return_value=(permissions, [])))
            stack.enter_context(patch("factorykit.operations.validate", return_value={"errors": [], "launch_blockers": []}))
            stack.enter_context(patch("factorykit.operations.observations", return_value=([], [])))
            stack.enter_context(patch("factorykit.operations.pristine_result", return_value=[]))
            stack.enter_context(patch("factorykit.common.verify_sources", return_value=[]))
            stack.enter_context(patch("factorykit.operations.verify_sources", return_value=[]))
            stack.enter_context(patch("factorykit.tasks.verify_tasks", return_value=self.tasks))
            stack.enter_context(patch("factorykit.operations.verify_tasks", return_value=self.tasks))
            yield


class PersistedBudgetTests(BudgetReadinessFixture):
    def test_missing_ledger_before_first_session_is_allowed_without_creation(self):
        self.assertEqual(persisted_budget_blockers(self.config, now=ORIGIN), [])
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.parent.exists())

    def test_required_existing_ledger_missing_blocks_without_recreating_it(self):
        blockers = persisted_budget_blockers(self.config, now=ORIGIN, require_existing=True)
        self.assertTrue(blockers)
        self.assertTrue(any("ledger" in item.lower() for item in blockers), blockers)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.parent.exists())
        self.assertEqual(persisted_budget_blockers(self.config, now=ORIGIN), [])

    def test_exact_expiry_blocks_even_without_stored_global_halt(self):
        before = self.save_ledger()
        deadline = ORIGIN + 28800
        self.assertEqual(persisted_budget_blockers(self.config, now=deadline - 0.001), [])
        self.assert_overall_blocked(persisted_budget_blockers(self.config, now=deadline))
        self.assert_overall_blocked(persisted_budget_blockers(self.config, now=deadline + 1))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(json.loads(before)["stopped_reason"])

    def test_time_only_amendment_preserves_original_ledger_and_rehearsal_halt(self):
        before = self.save_ledger()
        mtime = self.path.stat().st_mtime_ns
        now = ORIGIN + 30000
        self.assert_overall_blocked(persisted_budget_blockers(self.config, now=now))
        amended = copy.deepcopy(self.config)
        amended["budgets"]["overall_timeout_seconds"] = 70834
        self.assertEqual(persisted_budget_blockers(amended, now=now), [])
        self.assert_overall_blocked(persisted_budget_blockers(amended, now=ORIGIN + 70834))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.stat().st_mtime_ns, mtime)
        self.assertEqual(json.loads(self.path.read_text()), self.data)
        self.assertEqual(self.data["room_stopped_reasons"][TOY_ROOM], STAGE_STOP)
        self.assertEqual(self.config["budgets"]["overall_timeout_seconds"], 28800)

    def test_rehearsal_stage_halt_alone_is_not_aggregate_exhaustion(self):
        before = self.save_ledger()
        self.assertEqual(persisted_budget_blockers(self.config, now=ORIGIN + 2000), [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_sticky_global_halt_remains_blocked_after_time_extension(self):
        self.data["stopped_reason"] = "overall time budget exhausted"
        before = self.save_ledger()
        self.config["budgets"]["overall_timeout_seconds"] = 70834
        self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 30000))
        self.assertEqual(self.path.read_bytes(), before)

    def test_token_cap_still_blocks_after_time_extension(self):
        self.config["budgets"]["overall_timeout_seconds"] = 70834
        self.data["tokens"] = self.config["budgets"]["max_total_tokens"]
        before = self.save_ledger()
        blockers = persisted_budget_blockers(self.config, now=ORIGIN + 30000)
        self.assertTrue(any("token" in item.lower() for item in blockers), blockers)
        self.assertEqual(self.path.read_bytes(), before)

    def test_any_required_seat_at_turn_cap_blocks_seven_seat_readiness(self):
        for seat in self.config["seats"]:
            with self.subTest(seat=seat["id"]):
                data = copy.deepcopy(self.data)
                data["turns"][seat["id"]] = self.config["budgets"]["max_turns_per_seat"]
                before = self.save_ledger(data)
                blockers = persisted_budget_blockers(self.config, now=ORIGIN + 100)
                self.assertTrue(any("turn" in item.lower() and seat["id"] in item for item in blockers), blockers)
                self.assertEqual(self.path.read_bytes(), before)

    def test_future_or_nonfinite_origin_is_not_fresh_authority(self):
        for start in (ORIGIN + 1, float("nan"), float("inf"), True, "1791049765.700437", -1):
            with self.subTest(start=start):
                data = copy.deepcopy(self.data)
                data["started_epoch"] = start
                before = self.save_ledger(data)
                self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN))
                self.assertEqual(self.path.read_bytes(), before)

    def test_truly_not_started_state_does_not_start_clock(self):
        data = copy.deepcopy(self.data)
        data.update(started_epoch=None, tokens=0, turns={}, token_threads={}, room_started_epochs={},
                    room_turns={}, room_stopped_reasons={}, membership_attempts={})
        before = self.save_ledger(data)
        self.assertEqual(persisted_budget_blockers(self.config, now=ORIGIN + 100000), [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_not_started_origin_cannot_hide_prior_consumption(self):
        data = copy.deepcopy(self.data)
        data["started_epoch"] = None
        before = self.save_ledger(data)
        self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 100000))
        self.assertEqual(self.path.read_bytes(), before)

    def test_room_scope_must_match_both_configured_rooms(self):
        scopes = ([TOY_ROOM], [TOY_ROOM, TOY_ROOM], [TOY_ROOM, "other-room"], [], "not-a-list")
        for rooms in scopes:
            with self.subTest(rooms=rooms):
                data = copy.deepcopy(self.data)
                data["room_ids"] = rooms
                before = self.save_ledger(data)
                self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 1))
                self.assertEqual(self.path.read_bytes(), before)

    def test_aggregate_ledger_cannot_be_replaced_by_a_single_room_scope(self):
        data = copy.deepcopy(self.data)
        data["room_id"] = TOY_ROOM
        before = self.save_ledger(data)
        self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 1))
        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_symlink_is_rejected_without_changing_target(self):
        self.path.parent.mkdir(parents=True)
        target = self.root / "preserved-ledger.json"
        target.write_text(json.dumps(self.data))
        self.path.symlink_to(target)
        before = target.read_bytes()
        self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 1))
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_bytes(), before)

    def test_malformed_existing_ledger_fails_closed_without_replacement(self):
        self.path.parent.mkdir(parents=True)
        for text in ("{broken", "null", "[]", "{}", '"unexpected"'):
            with self.subTest(text=text):
                self.path.write_text(text)
                self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 1))
                self.assertEqual(self.path.read_text(), text)

    def test_malformed_consumption_is_rejected_without_normalizing(self):
        for key, value in (("tokens", True), ("tokens", -1), ("tokens", "0"),
                           ("turns", []), ("turns", {"pm": -1}), ("turns", {"pm": True}),
                           ("turns", {"unknown-seat": 0})):
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.data)
                data[key] = value
                before = self.save_ledger(data)
                self.assertTrue(persisted_budget_blockers(self.config, now=ORIGIN + 1))
                self.assertEqual(self.path.read_bytes(), before)


class BudgetReadinessIntegrationTests(BudgetReadinessFixture):
    def setUp(self):
        super().setUp()
        self.ready_files()
        self.before = self.save_ledger()

    def test_preflight_rechecks_capacity_without_reusing_prior_success(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2000), patch(
                "factorykit.validation.run_command", side_effect=[
                    {"exit_code": 0, "stdout": json.dumps({"ServerVersion": "test", "NCPU": 4, "MemTotal": memory}), "stderr": ""}
                    for memory in (4 * 1024 ** 3, 1024 ** 3)]) as probe:
            self.assertEqual(preflight_runtime(self.config, "judged"), [])
            errors = preflight_runtime(self.config, "judged")
            self.assertTrue(any("Docker daemon memory" in error for error in errors), errors)
            self.assertEqual(probe.call_count, 2)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_ready_freeze_cannot_prepare_dispatch_after_daemon_capacity_shrinks(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2000):
            frozen = freeze(self.config)
            self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
            with patch("factorykit.validation.run_command", return_value={
                    "exit_code": 0, "stdout": json.dumps({"ServerVersion": "test", "NCPU": 4, "MemTotal": 1024 ** 3}), "stderr": ""}):
                result = launch_prepare(self.config, "all", None)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assertEqual(result["docker_resources"]["status"], "FAIL")
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_capacity_query_cannot_admit_launch_after_cumulative_deadline(self):
        deadline = ORIGIN + 28800
        with self.unrelated_checks_pass(), patch("time.time", return_value=deadline - 1) as clock:
            frozen = freeze(self.config)
            self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
            def slow_query(*args, **kwargs):
                clock.return_value = deadline
                return {"exit_code": 0, "stdout": json.dumps({"ServerVersion": "test", "NCPU": 4, "MemTotal": 4 * 1024 ** 3}), "stderr": ""}
            with patch("factorykit.validation.run_command", side_effect=slow_query):
                result = launch_prepare(self.config, "all", None)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assert_overall_blocked(result["blockers"])
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_expired_runtime_preflight_does_not_probe_docker(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800), patch("factorykit.validation.run_command") as probe:
            self.assert_overall_blocked(preflight_runtime(self.config, "judged"))
            probe.assert_not_called()

    def test_real_preflight_checks_elapsed_aggregate_and_does_not_apply_toy_halt_to_judged(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2000):
            self.assertEqual(preflight_runtime(self.config, "judged"), [])
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800):
            for mode in ("rehearsal", "judged"):
                self.assert_overall_blocked(preflight_runtime(self.config, mode))
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_freeze_uses_real_preflight_to_reject_elapsed_overall_budget(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800):
            result = freeze(self.config)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assert_overall_blocked(result["blockers"])
        self.assertFalse(result["dispatch_performed"])
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_prior_ready_freeze_expiring_by_time_alone_cannot_prepare_dispatch(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800 - 1):
            frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        freeze_path = self.root / "runs/freeze/latest.json"
        frozen_bytes = freeze_path.read_bytes()
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800):
            result = launch_prepare(self.config, "all", None)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assert_overall_blocked(result["blockers"])
        self.assertFalse(result["dispatch_performed"])
        self.assertNotIn("preparation_id", result)
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(freeze_path.read_bytes(), frozen_bytes)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_expiry_during_launch_validation_rejects_prepared_state(self):
        deadline = ORIGIN + 28800
        with self.unrelated_checks_pass(), patch("time.time", return_value=deadline - 1):
            frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        freeze_path = self.root / "runs/freeze/latest.json"
        frozen_bytes = freeze_path.read_bytes()
        with self.unrelated_checks_pass(), patch("time.time", return_value=deadline - 1) as clock:
            def delayed_verification(config):
                clock.return_value = deadline
                return self.tasks

            with patch("factorykit.operations.verify_tasks", side_effect=delayed_verification) as verify:
                result = launch_prepare(self.config, "all", None)
            verify.assert_called_once_with(self.config)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assert_overall_blocked(result["blockers"])
        self.assertFalse(result["dispatch_performed"])
        self.assertNotIn("preparation_id", result)
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(freeze_path.read_bytes(), frozen_bytes)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_freeze_rechecks_expiry_after_preflight_returns_no_blockers(self):
        deadline = ORIGIN + 28800
        with self.unrelated_checks_pass(), patch("time.time", return_value=deadline - 1) as clock:
            def delayed_preflight(config, mode):
                clock.return_value = deadline
                return []

            with patch("factorykit.runtime.preflight_runtime", side_effect=delayed_preflight) as preflight:
                result = freeze(self.config)
            self.assertEqual(preflight.call_count, 2)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assert_overall_blocked(result["blockers"])
        self.assertFalse(result["dispatch_performed"])
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_missing_ledger_blocks_judged_preflight_without_recreation(self):
        self.path.unlink()
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2000):
            blockers = preflight_runtime(self.config, "judged")
            self.assertTrue(any("ledger" in item.lower() for item in blockers), blockers)
            # First rehearsal remains the sole missing-ledger admission case.
            self.assertEqual(preflight_runtime(self.config, "rehearsal"), [])
        self.assertFalse(self.path.exists())

    def test_missing_ledger_turns_prior_ready_freeze_into_blocked(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2000):
            initial = freeze(self.config)
            self.assertEqual(initial["status"], "READY_TO_LAUNCH", initial["blockers"])
            self.path.unlink()
            result = freeze(self.config)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assertTrue(any("ledger" in item.lower() for item in result["blockers"]), result["blockers"])
        self.assertFalse(self.path.exists())
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())

    def test_stale_ready_freeze_cannot_launch_or_prepare_after_ledger_disappears(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 2000):
            frozen = freeze(self.config)
            self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
            freeze_path = self.root / "runs/freeze/latest.json"
            frozen_bytes = freeze_path.read_bytes()
            self.path.unlink()
            errors = judged_launch_errors(self.config)
            self.assertTrue(any("ledger" in item.lower() for item in errors), errors)
            result = launch_prepare(self.config, "all", None)
        self.assertEqual(result["status"], "BLOCKED_WITH_ACTIONS")
        self.assertTrue(any("ledger" in item.lower() for item in result["blockers"]), result["blockers"])
        self.assertFalse(result["dispatch_performed"])
        self.assertNotIn("preparation_id", result)
        self.assertFalse(self.path.exists())
        self.assertFalse((self.root / "runs/launch/ledger.json").exists())
        self.assertEqual(freeze_path.read_bytes(), frozen_bytes)

    def test_judged_launch_checks_current_budget_after_ready_freeze(self):
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800 - 1):
            frozen = freeze(self.config)
        self.assertEqual(frozen["status"], "READY_TO_LAUNCH", frozen["blockers"])
        with self.unrelated_checks_pass(), patch("time.time", return_value=ORIGIN + 28800):
            self.assert_overall_blocked(judged_launch_errors(self.config))
        self.assertEqual(self.path.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
