"""Offline checks of the installed SDK's telemetry contract and normalization."""

import asyncio
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from factorykit.harness_usage import (
    is_trusted_metadata_key, lifecycle_status, usage_record,
)


class HarnessUsageTests(unittest.TestCase):
    def usage(self, **counts):
        return {"band_usage": counts}

    def test_alternate_counts_include_disjoint_caches_once(self):
        metadata = self.usage(input_tokens=20, output_tokens=7,
                              cache_read_tokens=50, cache_write_tokens=30,
                              total_tokens=27, reasoning_tokens=3)
        for harness in ("claude-code", "opencode"):
            with self.subTest(harness=harness):
                self.assertEqual(usage_record(metadata, turn_id="turn-1", harness=harness),
                                 (f"{harness}:turn:turn-1", 107))

    def test_replays_and_aggregate_updates_retain_same_accounting_key(self):
        observed = [usage_record(self.usage(input_tokens=n), turn_id="durable-1",
                                 harness="claude") for n in (10, 10, 20, 8)]
        self.assertEqual(observed, [("claude-code:turn:durable-1", n) for n in (10, 10, 20, 8)])
        self.assertNotEqual(
            observed[0][0],
            usage_record(self.usage(input_tokens=10), turn_id="durable-2", harness="claude")[0],
        )

    def test_harness_switch_has_distinct_accounting_identity(self):
        metadata = self.usage(input_tokens=4)
        self.assertNotEqual(
            usage_record(metadata, turn_id="same-trigger", harness="claude")[0],
            usage_record(metadata, turn_id="same-trigger", harness="opencode")[0],
        )

    def test_legacy_claude_alias_preserves_canonical_accounting_identity(self):
        metadata = self.usage(input_tokens=4)
        self.assertEqual(
            usage_record(metadata, turn_id="same-trigger", harness="claude"),
            usage_record(metadata, turn_id="same-trigger", harness="claude-code"),
        )

    def test_codex_unified_usage_never_double_counts_legacy_thread_totals(self):
        metadata = self.usage(input_tokens=20, output_tokens=7, cache_read_tokens=5)
        metadata.update(codex_thread_id="thread-1", codex_total_tokens=100)
        self.assertIsNone(usage_record(metadata, turn_id="turn-1", harness="codex"))
        self.assertIsNone(usage_record(metadata, turn_id="turn-1"))

    def test_missing_context_and_unsupported_harness_are_not_usage(self):
        for harness, turn_id in ((None, "turn-1"), ("unknown", "turn-1"),
                                 ({}, "turn-1"),
                                 ("claude", None), ("claude", ""), ("claude", " "),
                                 ("claude", True)):
            with self.subTest(harness=harness, turn_id=turn_id):
                self.assertIsNone(usage_record(self.usage(input_tokens=5),
                                               turn_id=turn_id, harness=harness))

    def test_bool_negative_and_malformed_counts_are_rejected(self):
        for invalid in (True, False, -1, 2.0, "2", None, [], {}):
            for field in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
                with self.subTest(field=field, value=invalid):
                    self.assertIsNone(usage_record(self.usage(**{field: invalid}),
                                                   turn_id="turn-1", harness="claude"))

    def test_missing_dimensions_are_zero_but_unknown_shape_is_not_zero_usage(self):
        self.assertEqual(usage_record(self.usage(cache_read_tokens=9),
                                      turn_id="turn-1", harness="claude"),
                         ("claude-code:turn:turn-1", 9))
        self.assertEqual(usage_record(self.usage(input_tokens=0),
                                      turn_id="turn-1", harness="claude")[1], 0)
        for metadata in (None, [], {}, {"band_usage": None}, self.usage(),
                         {"band_usage": []}, self.usage(total_tokens=20)):
            with self.subTest(metadata=metadata):
                self.assertIsNone(usage_record(metadata, turn_id="turn-1", harness="claude"))

    def test_failed_turn_still_accounts_usage(self):
        metadata = self.usage(input_tokens=25, cache_read_tokens=5)
        metadata["failure"] = {"provider": "claude_sdk", "message": "failed"}
        self.assertEqual(lifecycle_status(metadata), "failed")
        self.assertEqual(usage_record(metadata, turn_id="turn-1", harness="claude")[1], 30)

    def test_only_explicit_lifecycle_or_provider_failure_is_terminal(self):
        for prefix in ("codex", "factory"):
            for status in ("completed", "failed", "interrupted"):
                self.assertEqual(lifecycle_status({f"{prefix}_event_type": "turn_lifecycle",
                                                   f"{prefix}_turn_status": status}), status)
        for provider in ("codex", "claude_sdk", "opencode"):
            self.assertEqual(lifecycle_status({"failure": {"provider": provider}}), "failed")
        for metadata in (None, [], {}, self.usage(input_tokens=1),
                         {"codex_turn_status": "completed"},
                         {"factory_event_type": "task", "factory_turn_status": "completed"},
                         {"factory_event_type": "turn_lifecycle", "factory_turn_status": "running"},
                         {"failure": True}, {"failure": {"provider": "unknown"}},
                         {"failure": {"provider": []}},
                         {"factory_event_type": "turn_lifecycle", "factory_turn_status": []}):
            self.assertIsNone(lifecycle_status(metadata))

    def test_structured_failure_wins_over_success_lifecycle(self):
        self.assertEqual(lifecycle_status({"factory_event_type": "turn_lifecycle",
                                          "factory_turn_status": "completed",
                                          "failure": {"provider": "opencode"}}), "failed")

    def test_reserved_metadata_cannot_be_model_authored(self):
        for key in ("band_usage", "failure", "codex_thread_id", "claude_session_id",
                    "opencode_session_id", "factory_turn_status", "factory_harness"):
            self.assertTrue(is_trusted_metadata_key(key), key)
        for key in ("task_id", "status", "summary", None, 4):
            self.assertFalse(is_trusted_metadata_key(key), key)


class InstalledSDKUsageTests(unittest.IsolatedAsyncioTestCase):
    async def emit_metadata(self, usage):
        from band.core.simple_adapter import SimpleAdapter
        from band.core.types import Emit
        tools = SimpleNamespace(send_event=AsyncMock())
        adapter = SimpleNamespace(features=SimpleNamespace(emit=[Emit.USAGE]))
        await SimpleAdapter.emit_usage(adapter, tools, usage)
        tools.send_event.assert_awaited_once()
        metadata = tools.send_event.await_args.kwargs["metadata"]
        # This lack of provider IDs is why durable caller context is required.
        self.assertEqual(set(metadata), {"band_usage"})
        return metadata

    async def test_real_claude_result_mapping_and_emission(self):
        from band.adapters.claude_sdk import ClaudeSDKAdapter
        usage = ClaudeSDKAdapter._usage_from_result(SimpleNamespace(usage={
            "input_tokens": 11, "output_tokens": 13,
            "cache_read_input_tokens": 17, "cache_creation_input_tokens": 19,
        }))
        metadata = await self.emit_metadata(usage)
        self.assertEqual(usage_record(metadata, turn_id="claude-result", harness="claude")[1], 60)

    async def test_real_opencode_mapping_folds_reasoning_before_emission(self):
        from band.integrations.opencode.events import OpencodeTokens
        usage = OpencodeTokens(input=11, output=13, reasoning=7,
                               cache={"read": 17, "write": 19}).to_turn_usage()
        self.assertEqual(usage.output_tokens, 20)
        metadata = await self.emit_metadata(usage)
        self.assertEqual(usage_record(metadata, turn_id="opencode-result", harness="opencode")[1], 67)


class HarnessIntegrationFixture:
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "budget.json"
        self.limits = dict(max_active_seats=1, overall_timeout_seconds=10000,
                           stage_timeout_seconds=10000, max_turns_per_seat=100,
                           max_total_tokens=100000, turn_timeout_seconds=600,
                           max_repairs=2)
        network = patch.object(socket.socket, "connect", side_effect=AssertionError("Offline tests only"))
        network.start()
        self.addCleanup(network.stop)

    def ledger(self, room="room-1", **kwargs):
        from factorykit.runtime import BudgetLedger
        return BudgetLedger(self.limits, self.path, room, **kwargs)

    def metadata(self, input_tokens=11):
        return {"band_usage": dict(input_tokens=input_tokens, output_tokens=13,
                                    cache_read_tokens=17, cache_write_tokens=19)}


class HarnessLedgerIntegrationTests(HarnessIntegrationFixture, unittest.IsolatedAsyncioTestCase):
    async def test_alternate_aggregate_deltas_survive_replay_and_restart(self):
        ledger = self.ledger()
        ledger.reserve("pm")
        for _ in range(2):
            ledger.record("pm", self.metadata(), harness="claude-code", turn_id="turn-1")
        self.assertEqual(ledger.data["tokens"], 60)
        restored = self.ledger()
        restored.record("pm", self.metadata(), harness="claude-code", turn_id="turn-1")
        restored.record("pm", self.metadata(20), harness="claude-code", turn_id="turn-1")
        restored.record("pm", self.metadata(), harness="claude", turn_id="turn-1")
        self.assertEqual(restored.data["tokens"], 69)
        restored.record("pm", self.metadata(), harness="claude-code", turn_id="turn-2")
        restored.record("qa", self.metadata(), harness="claude-code", turn_id="turn-1")
        persisted = self.ledger().data
        self.assertEqual(persisted["tokens"], 189)
        self.assertEqual(sorted(persisted["token_threads"].values()), [60, 60, 69])
        self.assertEqual(persisted["turns"], {"pm": 1})

    async def test_same_turn_identity_is_scoped_by_harness_and_subscription_room(self):
        scope = dict(allowed_rooms=["rehearsal", "judged", "archived"],
                     active_rooms=["rehearsal", "judged"])
        ledger = self.ledger("rehearsal", **scope)
        for harness in ("claude-code", "opencode"):
            ledger.record("pm", self.metadata(), harness=harness, turn_id="same-trigger")
        self.assertEqual(ledger.data["tokens"], 120)
        judged = self.ledger("judged", **scope)
        judged.record("pm", self.metadata(), harness="opencode", turn_id="same-trigger")
        self.assertEqual(judged.data["tokens"], 180)
        restored = self.ledger("rehearsal", **scope)
        restored.record("pm", self.metadata(), harness="opencode", turn_id="same-trigger")
        self.assertEqual(restored.data["tokens"], 180)
        self.assertEqual(len(restored.data["token_threads"]), 3)

    async def test_codex_cumulative_path_does_not_add_unified_usage(self):
        ledger = self.ledger()
        ledger.record("pm", {"codex_thread_id": "thread-1", "codex_total_tokens": 100})
        ledger.record("pm", self.metadata(), harness="codex", turn_id="turn-1")
        ledger.record("pm", dict(self.metadata(), codex_thread_id="thread-1", codex_total_tokens=150),
                      harness="codex", turn_id="turn-2")
        restored = self.ledger()
        restored.record("pm", {"codex_thread_id": "thread-1", "codex_total_tokens": 150})
        self.assertEqual(restored.data["tokens"], 150)
        self.assertEqual(restored.data["token_threads"], {"pm:thread-1": 150})

    async def test_invalid_alternate_counts_cannot_corrupt_persistent_totals(self):
        ledger = self.ledger()
        ledger.record("pm", self.metadata(), harness="opencode", turn_id="turn-1")
        for invalid in (True, -1, 4.5, "6", None):
            ledger.record("pm", self.metadata(invalid), harness="opencode", turn_id="turn-1")
        ledger.record("pm", self.metadata(), harness="opencode")
        self.assertEqual(self.ledger().data["tokens"], 60)
        self.assertEqual(len(ledger.data["token_threads"]), 1)

    async def test_failed_turn_usage_trips_cap_and_later_usage_keeps_first_halt(self):
        self.limits["max_total_tokens"] = 50
        ledger = self.ledger()
        ledger.record("pm", dict(self.metadata(), failure={"provider": "opencode"}),
                      harness="opencode", turn_id="failed-turn")
        self.assertTrue(ledger.stop.is_set())
        self.assertEqual(ledger.reason(), "observed token budget exhausted")
        self.assertFalse(ledger.reserve("qa"))
        ledger.halt("later cleanup error")
        restored = self.ledger()
        restored.record("pm", self.metadata(20), harness="opencode", turn_id="failed-turn")
        self.assertEqual(restored.data["tokens"], 69)
        self.assertEqual(restored.reason(), "observed token budget exhausted")


class HarnessAuditIntegrationTests(HarnessIntegrationFixture, unittest.IsolatedAsyncioTestCase):
    ROOM = "00000000-0000-4000-8000-000000000001"
    PM = "00000000-0000-4000-8000-000000000002"
    ACTOR = "00000000-0000-4000-8000-000000000003"
    TRIGGER = "00000000-0000-4000-8000-000000000090"

    def setUp(self):
        super().setUp()
        from band.runtime.tools.agent import AgentTools
        from factorykit.runtime import AuditedTools
        self.base = AgentTools(self.ROOM, None, [])
        self.base.send_event = AsyncMock(return_value={})
        self.budget = self.ledger(self.ROOM)
        self.audit = self.root / "audit.jsonl"
        self.wrapped = AuditedTools(self.base, self.budget, "backend", self.audit,
                                    harness="opencode", turn_id="factory-turn")

    async def emit_sdk_usage(self, tools):
        from band.core.simple_adapter import SimpleAdapter
        from band.core.types import Emit, TurnUsage
        adapter = SimpleNamespace(features=SimpleNamespace(emit=[Emit.USAGE]))
        await SimpleAdapter.emit_usage(adapter, tools, TurnUsage(11, 13, 17, 19))

    async def test_actual_sdk_usage_flows_through_wrapper_accounting_and_audit(self):
        await self.emit_sdk_usage(self.wrapped)
        await self.emit_sdk_usage(self.wrapped)
        self.assertEqual(self.budget.data["tokens"], 60)
        rows = [json.loads(line) for line in self.audit.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["metadata"]["band_usage"], self.metadata()["band_usage"])
        self.assertEqual(self.base.send_event.await_count, 2)

    async def test_real_dispatch_rejects_forged_usage_failure_and_lifecycle(self):
        from factorykit.runtime import GateError
        for metadata in (self.metadata(), {"failure": {"provider": "opencode"}},
                         {"codex_thread_id": "forged"}, {"claude_session_id": "forged"},
                         {"opencode_session_id": "forged"},
                         {"factory_event_type": "turn_lifecycle", "factory_turn_status": "completed"}):
            with self.subTest(metadata=metadata), self.assertRaises(GateError):
                await self.wrapped.execute_tool_call_structured("band_send_event", {
                    "content": "Model event", "message_type": "task", "metadata": metadata,
                })
        self.base.send_event.assert_not_awaited()
        self.assertEqual(self.budget.data["tokens"], 0)
        result = await self.wrapped.execute_tool_call_structured("band_send_event", {
            "content": "Model task event", "message_type": "task", "metadata": {"task_id": "task-1"},
        })
        self.assertTrue(result.ok)
        self.base.send_event.assert_awaited_once()

    def workflow(self):
        from band.core.types import AgentInput
        from factorykit.workflow import WorkflowWatchdog
        from factorykit.workflow_runtime import WorkflowTools
        now = time.time()
        watchdog = WorkflowWatchdog(self.root / "workflow.json", self.ROOM, self.PM,
                                    [self.PM, self.ACTOR], 120, clock=lambda: now)
        wrapped = WorkflowTools(self.base, self.budget, "backend", self.audit,
                                watchdog=watchdog, actor_id=self.ACTOR,
                                turn_id="workflow-turn", deadline_at=now + 600,
                                harness="claude-code", clock=lambda: now)
        inp = AgentInput(msg=SimpleNamespace(id=self.TRIGGER), tools=self.base, history=None,
                         participants_msg=None, contacts_msg=None, is_session_bootstrap=False,
                         room_id=self.ROOM)
        return watchdog, wrapped, inp

    async def test_reported_provider_failure_survives_normal_return_and_broadcast_loss(self):
        from band.core.protocols import AgentFailure
        from factorykit.workflow_runtime import observed_turn
        watchdog, wrapped, inp = self.workflow()

        async def callback(inp):
            await self.emit_sdk_usage(inp.tools)
            self.base.send_event.side_effect = RuntimeError("offline transport")
            await inp.tools.send_failure(AgentFailure("claude_sdk", "private provider detail"))

        await observed_turn(callback, inp, wrapped, watchdog, actor_id=self.ACTOR,
                            turn_id=wrapped.turn_id, deadline_at=wrapped.deadline_at)
        state = json.loads(watchdog.path.read_text())
        self.assertEqual(state["turns"]["workflow-turn"]["status"], "failed")
        self.assertEqual(state["turns"]["workflow-turn"]["reason_code"], "provider_failure")
        self.assertEqual(self.budget.data["tokens"], 60)
        self.assertIn("claude-code:turn:workflow-turn", next(iter(self.budget.data["token_threads"])))
        self.assertNotIn("private provider detail", watchdog.path.read_text())
        self.assertNotIn("private provider detail", self.audit.read_text())

    async def test_factory_failure_lifecycle_survives_best_effort_broadcast_loss(self):
        from band.core.protocols import send_event_safe
        from factorykit.workflow_runtime import observed_turn
        watchdog, wrapped, inp = self.workflow()
        self.base.send_event.side_effect = RuntimeError("offline transport")

        async def callback(inp):
            await send_event_safe(inp.tools, "Failed result delivery", "error", metadata={
                "factory_event_type": "turn_lifecycle", "factory_turn_status": "failed",
            })

        await observed_turn(callback, inp, wrapped, watchdog, actor_id=self.ACTOR,
                            turn_id=wrapped.turn_id, deadline_at=wrapped.deadline_at)
        self.assertEqual(json.loads(watchdog.path.read_text())["turns"]["workflow-turn"]["status"], "failed")

    async def run_accounted_workflow(self, callback, wrapped=None):
        from factorykit.runtime import accounted_adapter_turn
        from factorykit.workflow_runtime import observed_turn
        watchdog, selected, inp = self.workflow()
        wrapped = wrapped or selected

        async def provider(admitted):
            return await accounted_adapter_turn(callback, admitted, wrapped)

        result = await observed_turn(provider, inp, wrapped, watchdog, actor_id=self.ACTOR,
                                     turn_id=wrapped.turn_id, deadline_at=wrapped.deadline_at)
        return result, watchdog, wrapped

    async def test_success_without_usage_becomes_failed_and_persistently_halts(self):
        result, watchdog, wrapped = await self.run_accounted_workflow(AsyncMock(return_value="provider returned"))
        self.assertEqual(result, "provider returned")
        self.assertFalse(wrapped.usage_observed)
        self.assertEqual(wrapped.terminal_status, "failed")
        state = json.loads(watchdog.path.read_text())
        self.assertEqual(state["turns"]["workflow-turn"]["status"], "failed")
        persisted = self.ledger(self.ROOM)
        self.assertIn("usage was not reported", persisted.reason())
        self.assertEqual(persisted.data["tokens"], 0)
        self.assertEqual(persisted.data["token_threads"], {})
        self.assertFalse(persisted.reserve("qa"))

    async def test_sdk_usage_allows_completion_even_if_usage_broadcast_fails(self):
        self.base.send_event.side_effect = RuntimeError("offline transport")

        async def callback(inp):
            await self.emit_sdk_usage(inp.tools)

        _, watchdog, wrapped = await self.run_accounted_workflow(callback)
        self.assertTrue(wrapped.usage_observed)
        self.assertEqual(json.loads(watchdog.path.read_text())["turns"]["workflow-turn"]["status"], "completed")
        persisted = self.ledger(self.ROOM)
        self.assertEqual(persisted.data["tokens"], 60)
        self.assertIsNone(persisted.reason())
        self.assertTrue(persisted.reserve("qa"))

    async def test_accounting_failure_is_not_mistaken_for_observed_usage(self):
        async def callback(inp):
            await self.emit_sdk_usage(inp.tools)

        with patch.object(self.budget, "record", side_effect=OSError("ledger unavailable")):
            _, watchdog, wrapped = await self.run_accounted_workflow(callback)
        self.assertFalse(wrapped.usage_observed)
        self.assertEqual(json.loads(watchdog.path.read_text())["turns"]["workflow-turn"]["status"], "failed")
        persisted = self.ledger(self.ROOM)
        self.assertEqual(persisted.data["tokens"], 0)
        self.assertEqual(persisted.data["token_threads"], {})
        self.assertIn("usage was not reported", persisted.reason())
        self.assertFalse(persisted.reserve("qa"))

    async def test_real_cancellation_without_usage_persists_interruption_and_halt(self):
        from factorykit.runtime import accounted_adapter_turn
        from factorykit.workflow_runtime import observed_turn
        watchdog, wrapped, inp = self.workflow()
        running = asyncio.Event()

        async def callback(inp):
            running.set()
            await asyncio.Event().wait()

        async def provider(admitted):
            return await accounted_adapter_turn(callback, admitted, wrapped)

        task = asyncio.create_task(observed_turn(provider, inp, wrapped, watchdog,
            actor_id=self.ACTOR, turn_id=wrapped.turn_id, deadline_at=wrapped.deadline_at))
        await running.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(wrapped.usage_observed)
        self.assertEqual(wrapped.terminal_status, "failed")
        # Cancellation remains an interruption while accounting blocks future admission.
        state = json.loads(watchdog.path.read_text())
        self.assertEqual(state["turns"]["workflow-turn"]["status"], "interrupted")
        self.assertEqual(state["turns"]["workflow-turn"]["reason_code"], "interrupted")
        persisted = self.ledger(self.ROOM)
        self.assertEqual(persisted.data["tokens"], 0)
        self.assertEqual(persisted.data["token_threads"], {})
        self.assertIn("usage was not reported", persisted.reason())
        self.assertFalse(persisted.reserve("qa"))

    async def test_late_usage_is_retained_without_clearing_missing_usage_halt(self):
        _, _, wrapped = await self.run_accounted_workflow(AsyncMock())
        original_reason = self.budget.reason()
        await self.emit_sdk_usage(wrapped)
        persisted = self.ledger(self.ROOM)
        self.assertEqual(persisted.data["tokens"], 60)
        self.assertEqual(persisted.reason(), original_reason)
        self.assertFalse(persisted.reserve("qa"))

    async def test_invalid_telemetry_cannot_satisfy_the_usage_guard(self):
        async def callback(inp):
            await inp.tools.send_event("malformed usage", "task", {"band_usage": {"input_tokens": True}})

        _, watchdog, wrapped = await self.run_accounted_workflow(callback)
        self.assertFalse(wrapped.usage_observed)
        self.assertEqual(json.loads(watchdog.path.read_text())["turns"]["workflow-turn"]["status"], "failed")
        self.assertEqual(self.budget.data["tokens"], 0)
        self.assertFalse(self.budget.reserve("qa"))

    async def test_codex_legacy_completion_does_not_require_alternate_usage(self):
        from factorykit.runtime import accounted_adapter_turn
        self.wrapped.harness = "codex"
        result = await accounted_adapter_turn(AsyncMock(return_value="completed"), None, self.wrapped)
        self.assertEqual(result, "completed")
        self.assertFalse(self.wrapped.usage_observed)
        self.assertIsNone(self.budget.reason())
        self.assertTrue(self.budget.reserve("qa"))


if __name__ == "__main__":
    unittest.main()
