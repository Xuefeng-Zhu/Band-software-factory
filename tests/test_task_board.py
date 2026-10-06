"""Offline shared-board tests using real SDK tools and task response models.

No credentials, model turns, attached sessions or live BAND writes are used.
"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from band.adapters import CodexAdapter, CodexAdapterConfig
from band.client.rest import Task
from band.core.types import Capability
from band.runtime.tools.agent import AgentTools

from factorykit.common import FactoryError
from factorykit.runtime import BudgetLedger
from factorykit.task_board import MUTATION_TOOLS, TaskBoard
from factorykit.workflow import WorkflowWatchdog
from factorykit.workflow_runtime import WorkflowTools


def uid(n):
    return f"00000000-0000-4000-8000-{n:012d}"


ROOM, PM, OWNER, REVIEWER, OTHER = (uid(i) for i in range(1, 6))
ROSTER = [dict(id=name, agent_id=identity, handle=f"team/{name}") for name, identity in
          (("pm", PM), ("backend", OWNER), ("reviewer", REVIEWER), ("frontend", OTHER))]
COMMIT = "b" * 40
DATE = "2026-10-05T12:00:00Z"


class TaskBoardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "task-board.json"
        self.board = TaskBoard(self.path, ROOM, ROSTER)
        self.remote = {}
        self.transports = {}
        self.window = lambda: 10.0
        blocker = patch.object(socket.socket, "connect", side_effect=AssertionError("Tests must remain offline"))
        blocker.start()
        self.addCleanup(blocker.stop)

    def actor(self, identity):
        seat = next(s for s in ROSTER if s["agent_id"] == identity)
        return dict(id=identity, name=seat["id"], handle=seat["handle"], type="Agent")

    def response(self, task):
        return SimpleNamespace(data=Task.model_validate(deepcopy(task)))

    def tools(self, identity):
        if identity in self.transports:
            return self.transports[identity]

        async def create(**kwargs):
            task_id = uid(100 + len(self.remote))
            task = dict(id=task_id, chat_room_id=kwargs["chat_id"], number=len(self.remote) + 1,
                        subject=kwargs["subject"], detail=kwargs["detail"], state="active",
                        created_by=self.actor(identity), assignments=[], overall_status="pending",
                        inserted_at=DATE, updated_at=DATE)
            self.remote[task_id] = task
            return self.response(task)

        async def get(**kwargs):
            return self.response(self.remote[kwargs["id"]])

        async def update(**kwargs):
            task = self.remote[kwargs["id"]]
            for key in ("subject", "detail", "state"):
                if key in kwargs:
                    task[key] = kwargs[key]
            if "status" in kwargs:
                existing = next((a for a in task["assignments"] if a["assignee"]["id"] == identity), None)
                if existing is None:
                    existing = dict(assignee=self.actor(identity), active_form="", linked_native_id="", updated_at=DATE)
                    task["assignments"].append(existing)
                existing.update(status=kwargs["status"], active_form=kwargs.get("active_form", ""))
                task["overall_status"] = kwargs["status"]
            return self.response(task)

        endpoint = SimpleNamespace(create_chat_task=AsyncMock(side_effect=create),
                                   get_chat_task=AsyncMock(side_effect=get),
                                   update_chat_task=AsyncMock(side_effect=update),
                                   put_chat_board=AsyncMock())
        tools = AgentTools(ROOM, SimpleNamespace(agent_api_chat_tasks=endpoint), ROSTER, agent_id=identity)
        self.transports[identity] = tools
        return tools

    def item(self, identity="WORK-1", state="READY", dependencies=()):
        return dict(id=identity, owner="team/backend", reviewer="team/reviewer", dependencies=list(dependencies),
                    state=state, goal="Verify generic work", requirements=["Preserve the original inputs"],
                    starting_revision="a" * 40, workspace_paths=[str(self.root)],
                    ownership_boundaries=["Owned scratch only"], acceptance_conditions=["Independent review"],
                    candidate_commit=None, commands=[], results=[], evidence_paths=[], limitations=[],
                    next_recipient="team/backend")

    async def publish(self, item, version=0, actor=PM, board=None):
        return await (board or self.board).publish(self.tools(actor), actor, item, version, self.window)

    async def ready(self, identity="WORK-1"):
        return await self.publish(self.item(identity))

    async def delivered(self, identity="WORK-1"):
        record = await self.ready(identity)
        item = dict(record["item"], state="IN_PROGRESS")
        record = await self.publish(item, record["version"], OWNER)
        item = dict(item, state="REVIEW", candidate_commit=COMMIT, commands=["verify candidate"],
                    results=["PASS"], evidence_paths=[str(self.root / "candidate.json")],
                    next_recipient="team/reviewer")
        return await self.publish(item, record["version"], OWNER)

    def decision(self, record, state="ACCEPTED", event=None):
        return dict(record["item"], state=state, room_event=event or uid(500),
                    review_commands=["independent check"], review_results=["PASS" if state == "ACCEPTED" else "FAIL"],
                    review_evidence_paths=[str(self.root / "review.json")], next_recipient="team/backend",
                    **({"bounded_next_action": "Repair the recorded failure once"} if state == "REJECTED" else {}))

    def observe_review(self, event=None, actor=REVIEWER, recipient=OWNER, commit=COMMIT,
                       identity="WORK-1", verdict="ACCEPTED", version=None):
        version = version or self.board.snapshot()["items"][identity]["version"]
        self.board.observe_message(actor, dict(id=event or uid(500), success=True,
            recipients=[dict(id=recipient, handle=self.actor(recipient)["handle"])]),
            f"WORK-REVIEW {identity} version {version} {verdict} candidate {commit}\nIndependent review findings.")

    async def accepted(self, identity="WORK-1"):
        record = await self.delivered(identity)
        self.observe_review(identity=identity)
        return await self.publish(self.decision(record), record["version"], REVIEWER)

    def mutations(self):
        return sum(t.rest.agent_api_chat_tasks.create_chat_task.await_count
                   + t.rest.agent_api_chat_tasks.update_chat_task.await_count for t in self.transports.values())

    async def test_pm_create_records_full_item_without_claiming_assignment(self):
        record = await self.ready()
        self.assertEqual(record["version"], 1)
        task = self.remote[record["task_id"]]
        self.assertEqual(task["assignments"], [])
        self.assertIn('"acceptance_conditions"', task["detail"])
        kwargs = self.tools(PM).rest.agent_api_chat_tasks.create_chat_task.await_args.kwargs
        self.assertNotIn("status", kwargs)
        self.assertEqual(kwargs["request_options"], dict(max_retries=0, timeout_in_seconds=10.0))
        self.assertEqual(self.board.snapshot()["items"]["WORK-1"]["task_id"], task["id"])

    async def test_owner_progress_review_acceptance_then_owner_sync(self):
        record = await self.accepted()
        task = self.remote[record["task_id"]]
        self.assertEqual(task["overall_status"], "in_review")
        self.assertEqual([a["assignee"]["id"] for a in task["assignments"]], [OWNER])
        self.assertNotIn("status", self.tools(REVIEWER).rest.agent_api_chat_tasks.update_chat_task.await_args.kwargs)
        self.assertTrue(self.board.snapshot()["items"]["WORK-1"]["owner_sync_pending"])
        await self.board.sync_owner(self.tools(OWNER), OWNER, self.window)
        self.assertEqual(task["overall_status"], "completed")
        self.assertFalse(self.board.snapshot()["items"]["WORK-1"]["owner_sync_pending"])
        count = self.mutations()
        await self.board.sync_owner(self.tools(OWNER), OWNER, self.window)
        self.assertEqual(self.mutations(), count)

    async def test_rejection_uses_reviewer_evidence_and_owner_can_repair(self):
        record = await self.delivered()
        self.observe_review(verdict="REJECTED")
        rejected = await self.publish(self.decision(record, "REJECTED"), record["version"], REVIEWER)
        await self.board.sync_owner(self.tools(OWNER), OWNER, self.window)
        self.assertEqual(self.remote[record["task_id"]]["overall_status"], "blocked")
        current = self.board.snapshot()["items"]["WORK-1"]
        repaired = await self.publish(dict(rejected["item"], state="IN_PROGRESS"), current["version"], OWNER)
        self.assertEqual(repaired["owner_status"], "in_progress")

    async def test_non_pm_creation_and_wrong_owner_progress_are_rejected_before_transport(self):
        for actor in (OWNER, REVIEWER, OTHER):
            with self.subTest(actor=actor), self.assertRaises(FactoryError):
                await self.publish(self.item(), actor=actor)
        self.assertEqual(self.mutations(), 0)
        record = await self.ready()
        for actor in (PM, REVIEWER, OTHER):
            with self.subTest(actor=actor), self.assertRaises(FactoryError):
                await self.publish(dict(record["item"], state="IN_PROGRESS"), record["version"], actor)
        self.assertEqual(self.mutations(), 1)

    async def test_transport_identity_cannot_impersonate_pm_or_owner(self):
        with self.assertRaises(FactoryError):
            await self.board.publish(self.tools(OTHER), PM, self.item(), 0, self.window)
        self.assertEqual(self.mutations(), 0)

    async def test_ready_scope_is_immutable(self):
        record = await self.ready()
        mutations = dict(owner="team/frontend", reviewer="team/frontend", goal="Replace scope",
                         requirements=["Different requirement"], dependencies=["OTHER"],
                         acceptance_conditions=["Skip independent checking"])
        for key, value in mutations.items():
            with self.subTest(field=key), self.assertRaises(FactoryError):
                await self.publish(dict(record["item"], state="IN_PROGRESS", **{key: value}), record["version"], OWNER)
        self.assertEqual(self.mutations(), 1)

    async def test_reviewer_cannot_replace_delivered_candidate_or_evidence(self):
        record = await self.delivered()
        self.observe_review()
        for key, value in dict(candidate_commit="c" * 40, commands=["different command"],
                               results=["invented result"], evidence_paths=[str(self.root / "other.json")]).items():
            with self.subTest(field=key), self.assertRaises(FactoryError):
                await self.publish(dict(self.decision(record), **{key: value}), record["version"], REVIEWER)
        self.assertEqual(self.mutations(), 3)

    async def test_acceptance_needs_nominated_reviewer_and_candidate_bound_message(self):
        record = await self.delivered()
        decision = self.decision(record)
        for actor in (OWNER, PM, OTHER):
            with self.subTest(actor=actor), self.assertRaises(FactoryError):
                await self.publish(decision, record["version"], actor)
        for index, (actor, recipient, commit) in enumerate(((OWNER, OWNER, COMMIT),
                (REVIEWER, PM, COMMIT), (REVIEWER, OWNER, "c" * 40))):
            event = uid(510 + index)
            self.observe_review(event, actor, recipient, commit)
            with self.subTest(event=event), self.assertRaises(FactoryError):
                await self.publish(dict(decision, room_event=event), record["version"], REVIEWER)
        with self.assertRaises(FactoryError):
            await self.publish(decision, record["version"], REVIEWER)

    async def test_review_requires_separate_absolute_review_evidence(self):
        record = await self.delivered()
        self.observe_review()
        for field, value in (("review_commands", []), ("review_results", []),
                             ("review_evidence_paths", []), ("review_evidence_paths", ["relative.json"])):
            with self.subTest(field=field, value=value), self.assertRaises(FactoryError):
                await self.publish(dict(self.decision(record), **{field: value}), record["version"], REVIEWER)

    async def test_dependencies_must_be_accepted_and_distinct(self):
        record = await self.ready("PREREQ")
        for dependencies in (("missing",), ("WORK-1",), ("PREREQ",)):
            with self.subTest(dependencies=dependencies), self.assertRaises(FactoryError):
                await self.publish(self.item(dependencies=dependencies))
        prerequisite = await self.publish(dict(record["item"], state="IN_PROGRESS"), record["version"], OWNER)
        prerequisite = await self.publish(dict(prerequisite["item"], state="REVIEW", candidate_commit=COMMIT,
            commands=["verify"], results=["PASS"], evidence_paths=[str(self.root / "prereq.json")]), prerequisite["version"], OWNER)
        self.observe_review(identity="PREREQ")
        await self.publish(self.decision(prerequisite), prerequisite["version"], REVIEWER)
        with self.assertRaises(FactoryError):
            await self.publish(self.item(dependencies=("PREREQ", "PREREQ")))
        created = await self.publish(self.item(dependencies=("PREREQ",)))
        self.assertEqual(created["item"]["dependencies"], ["PREREQ"])

    async def test_stale_bool_and_negative_versions_never_write(self):
        for version in (True, False, -1, 1.0, "0"):
            with self.subTest(version=version), self.assertRaises(FactoryError):
                await self.publish(self.item(), version)
        record = await self.ready()
        with self.assertRaises(FactoryError):
            await self.publish(dict(record["item"], state="IN_PROGRESS"), 0, OWNER)
        self.assertEqual(self.mutations(), 1)

    async def test_duplicate_unchanged_write_is_noop(self):
        record = await self.ready()
        before = self.path.read_bytes()
        result = await self.publish(record["item"], record["version"])
        self.assertEqual(result["version"], record["version"])
        self.assertEqual(self.mutations(), 1)
        self.assertEqual(self.path.read_bytes(), before)

    async def test_accepted_is_terminal_even_for_blocked_transition(self):
        record = await self.accepted()
        with self.assertRaises(FactoryError):
            await self.publish(dict(record["item"], state="BLOCKED", bounded_next_action="Try again once"), record["version"], OWNER)

    async def fail_create_after_remote_write(self, error):
        endpoint = self.tools(PM).rest.agent_api_chat_tasks
        original = endpoint.create_chat_task.side_effect
        async def lost(**kwargs):
            await original(**kwargs)
            raise error
        endpoint.create_chat_task.side_effect = lost
        with self.assertRaises(type(error) if isinstance(error, asyncio.CancelledError) else FactoryError):
            await self.ready()
        return next(iter(self.remote))

    async def test_unknown_create_survives_restart_and_exact_read_reconciles_without_retry(self):
        task_id = await self.fail_create_after_remote_write(RuntimeError("response lost"))
        self.assertIsNotNone(self.board.snapshot()["items"]["WORK-1"]["pending"])
        restarted = TaskBoard(self.path, ROOM, ROSTER)
        with self.assertRaises(FactoryError):
            await self.publish(self.item(), board=restarted)
        record = await restarted.reconcile(self.tools(PM), "WORK-1", task_id, self.window)
        self.assertEqual(record["task_id"], task_id)
        self.assertEqual(record["version"], 1)
        self.assertIsNone(record["pending"])
        self.assertEqual(self.mutations(), 1)

    async def test_cancelled_create_keeps_claim_and_restart_does_not_retry(self):
        await self.fail_create_after_remote_write(asyncio.CancelledError())
        restarted = TaskBoard(self.path, ROOM, ROSTER)
        with self.assertRaises(FactoryError):
            await self.publish(self.item(), board=restarted)
        self.assertEqual(self.mutations(), 1)

    async def test_uncertain_create_exact_reconcile_rejects_different_returned_uuid(self):
        task_id = await self.fail_create_after_remote_write(RuntimeError("response lost"))
        fake = dict(self.remote[task_id], id=uid(999))
        self.tools(PM).rest.agent_api_chat_tasks.get_chat_task.side_effect = lambda **kwargs: self.response(fake)
        with self.assertRaises(FactoryError):
            await self.board.reconcile(self.tools(PM), "WORK-1", task_id, self.window)
        self.assertIsNotNone(self.board.snapshot()["items"]["WORK-1"]["pending"])

    async def test_wrong_room_create_response_is_unconfirmed(self):
        endpoint = self.tools(PM).rest.agent_api_chat_tasks
        original = endpoint.create_chat_task.side_effect
        async def wrong(**kwargs):
            response = await original(**kwargs)
            return self.response(dict(response.data.model_dump(mode="json"), chat_room_id=uid(999)))
        endpoint.create_chat_task.side_effect = wrong
        with self.assertRaises(FactoryError):
            await self.ready()
        self.assertIsNotNone(self.board.snapshot()["items"]["WORK-1"]["pending"])

    async def test_wrong_mapped_update_uuid_or_assignment_status_is_unconfirmed(self):
        record = await self.ready()
        endpoint = self.tools(OWNER).rest.agent_api_chat_tasks
        original = endpoint.update_chat_task.side_effect
        async def wrong(**kwargs):
            response = await original(**kwargs)
            raw = response.data.model_dump(mode="json")
            raw["assignments"][0]["status"] = "completed"
            return self.response(raw)
        endpoint.update_chat_task.side_effect = wrong
        with self.assertRaises(FactoryError):
            await self.publish(dict(record["item"], state="IN_PROGRESS"), record["version"], OWNER)
        self.assertIsNotNone(self.board.snapshot()["items"]["WORK-1"]["pending"])
        task_id = record["task_id"]
        self.tools(OWNER).rest.agent_api_chat_tasks.get_chat_task.side_effect = lambda **kwargs: self.response(
            dict(self.remote[task_id], id=uid(999)))
        with self.assertRaises(FactoryError):
            await self.board.reconcile(self.tools(OWNER), "WORK-1", task_id, self.window)

    async def test_external_detail_edit_prevents_overwrite(self):
        record = await self.ready()
        self.remote[record["task_id"]]["detail"] = "Manually changed scope"
        with self.assertRaises(FactoryError):
            await self.publish(dict(record["item"], state="IN_PROGRESS"), record["version"], OWNER)
        self.assertEqual(self.mutations(), 1)
        self.assertIsNone(self.board.snapshot()["items"]["WORK-1"]["pending"])

    async def test_budget_exhaustion_and_wrong_room_prevent_claim(self):
        self.window = lambda: 0
        with self.assertRaises(FactoryError):
            await self.ready()
        self.assertEqual(self.board.snapshot()["items"], {})
        self.window = lambda: 10
        self.tools(PM).room_id = uid(999)
        with self.assertRaises(FactoryError):
            await self.ready()
        self.assertEqual(self.board.snapshot()["items"], {})
        self.assertEqual(self.mutations(), 0)

    async def test_persisted_scope_cannot_be_loaded_as_another_room(self):
        await self.ready()
        with self.assertRaises(FactoryError):
            TaskBoard(self.path, uid(999), ROSTER).snapshot()

    def wrapper(self, identity=PM):
        ledger = BudgetLedger(dict(max_active_seats=1, overall_timeout_seconds=10000,
            stage_timeout_seconds=10000, max_turns_per_seat=100, max_total_tokens=1000000,
            turn_timeout_seconds=600, max_repairs=2), self.root / "budget.json", ROOM)
        watchdog = WorkflowWatchdog(self.root / "workflow.json", ROOM, PM,
                                   [s["agent_id"] for s in ROSTER], 120)
        seat = next(s["id"] for s in ROSTER if s["agent_id"] == identity)
        return WorkflowTools(self.tools(identity), ledger, seat, self.root / "audit.jsonl", ROSTER,
            watchdog=watchdog, actor_id=identity, turn_id="offline-turn", deadline_at=time.time()+600,
            task_board=self.board)

    async def test_actual_sdk_dynamic_schema_and_dispatch_block_raw_mutations(self):
        guard = self.wrapper()
        adapter = CodexAdapter(CodexAdapterConfig(), capabilities=[Capability.TASKS])
        schemas = {t["name"]: t for t in adapter._build_dynamic_tools(guard)}
        self.assertTrue({"factory_work_item", "factory_task_board", "factory_reconcile_task"} <= schemas.keys())
        self.assertTrue({"band_list_tasks", "band_get_task", "band_get_board"} <= schemas.keys())
        self.assertFalse(MUTATION_TOOLS & schemas.keys())
        for name in MUTATION_TOOLS:
            with self.subTest(tool=name):
                outcome = await guard.execute_tool_call_structured(name, {})
                self.assertFalse(outcome.ok)
        outcome = await guard.execute_tool_call_structured("factory_work_item", dict(item=self.item(), expected_version=0))
        self.assertTrue(outcome.ok, outcome.value)
        read = await guard.execute_tool_call_structured("factory_task_board", {})
        self.assertTrue(read.ok)
        self.assertEqual(read.value["items"]["WORK-1"]["version"], 1)
        self.assertEqual(self.mutations(), 1)
        self.tools(PM).rest.agent_api_chat_tasks.put_chat_board.assert_not_awaited()

    async def test_workflow_guard_records_confirmed_review_message(self):
        record = await self.delivered()
        guard = self.wrapper(REVIEWER)
        self.tools(REVIEWER).send_message = AsyncMock(return_value=dict(id=uid(500), success=True,
            recipients=[dict(id=OWNER, handle="team/backend")]))
        await guard.send_message(f"WORK-REVIEW WORK-1 version {record['version']} ACCEPTED candidate {COMMIT}\nReview completed.", mentions=[OWNER])
        outcome = await guard.execute_tool_call_structured("factory_work_item",
            dict(item=self.decision(record), expected_version=record["version"]))
        self.assertTrue(outcome.ok, outcome.value)
        await self.wrapper(OWNER).sync_task_board()
        self.assertEqual(self.remote[record["task_id"]]["overall_status"], "completed")

    async def test_review_proof_cannot_change_item_version_or_verdict(self):
        record = await self.delivered()
        for index, overrides in enumerate(({"verdict": "REJECTED"}, {"version": record["version"]-1})):
            event = uid(700 + index)
            self.observe_review(event=event, **overrides)
            with self.assertRaises(FactoryError):
                await self.publish(self.decision(record, event=event), record["version"], REVIEWER)
        other = await self.delivered("WORK-2")
        self.observe_review(event=uid(702), identity="WORK-2")
        with self.assertRaises(FactoryError):
            await self.publish(self.decision(record, event=uid(702)), record["version"], REVIEWER)
        self.assertEqual(other["item"]["candidate_commit"], record["item"]["candidate_commit"])

    async def test_rejection_requires_new_candidate_and_fresh_review(self):
        record = await self.delivered()
        self.observe_review(verdict="REJECTED")
        rejected = await self.publish(self.decision(record, "REJECTED"), record["version"], REVIEWER)
        progress = await self.publish(dict(rejected["item"], state="IN_PROGRESS"), rejected["version"], OWNER)
        with self.assertRaises(FactoryError):
            await self.publish(dict(progress["item"], state="REVIEW"), progress["version"], OWNER)
        new_commit = "c" * 40
        reviewed = await self.publish(dict(progress["item"], state="REVIEW", candidate_commit=new_commit), progress["version"], OWNER)
        with self.assertRaises(FactoryError):
            await self.publish(self.decision(reviewed), reviewed["version"], REVIEWER)
        self.observe_review(event=uid(710), commit=new_commit)
        accepted = await self.publish(self.decision(reviewed, event=uid(710)), reviewed["version"], REVIEWER)
        self.assertEqual(accepted["item"]["state"], "ACCEPTED")

    async def test_sync_read_failure_is_visible_without_starving_owner_or_retrying(self):
        await self.ready()
        endpoint = self.tools(OWNER).rest.agent_api_chat_tasks
        original = endpoint.get_chat_task.side_effect
        endpoint.get_chat_task.side_effect = RuntimeError("provider detail must not leak")
        await self.wrapper(OWNER).sync_task_board()
        record = self.board.snapshot()["items"]["WORK-1"]
        self.assertIn("sync_error", record)
        self.assertNotIn("provider detail", json.dumps(record))
        self.assertIsNone(record["pending"])
        await self.wrapper(OWNER).sync_task_board()
        self.assertEqual(endpoint.get_chat_task.await_count, 1)
        endpoint.get_chat_task.side_effect = original
        synced = await self.publish(record["item"], record["version"], OWNER)
        self.assertNotIn("sync_error", synced)
        self.assertFalse(synced["owner_sync_pending"])

    async def test_sync_unknown_write_remains_pending_but_owner_can_read(self):
        await self.ready()
        self.tools(OWNER).rest.agent_api_chat_tasks.update_chat_task.side_effect = RuntimeError("response lost")
        guard = self.wrapper(OWNER)
        await guard.sync_task_board()
        result = await guard.execute_tool_call_structured("factory_task_board", {})
        self.assertTrue(result.ok)
        record = result.value["items"]["WORK-1"]
        self.assertIsNotNone(record["pending"])
        self.assertIn("sync_error", record)
        await guard.sync_task_board()
        self.assertEqual(self.tools(OWNER).rest.agent_api_chat_tasks.update_chat_task.await_count, 1)

    async def test_final_admitted_turn_can_update_board_without_extending_limits(self):
        guard = self.wrapper()
        guard.ledger.data["turns"]["pm"] = guard.ledger.limits["max_turns_per_seat"]
        before = deepcopy(guard.ledger.data)
        result = await guard.execute_tool_call_structured("factory_work_item", dict(item=self.item(), expected_version=0))
        self.assertTrue(result.ok, result.value)
        self.assertEqual(guard.ledger.data, before)
        guard.ledger.stop.set()
        self.assertEqual(guard.board_window(), 0)

    async def test_native_mcp_method_dispatch_cannot_bypass_raw_mutation_guards(self):
        from factorykit.runtime import GateError
        guard = self.wrapper()
        for name in ("create_task", "update_task", "set_board"):
            with self.subTest(method=name), self.assertRaises(GateError):
                await getattr(guard, name)()
        self.assertEqual(self.mutations(), 0)


if __name__ == "__main__":
    unittest.main()
