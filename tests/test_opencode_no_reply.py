"""Real BAND MCP dispatch and native HTTP bridge; no server, provider, or BAND calls."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import httpx
from band.core.types import Emit
from band.integrations.mcp.engine import build_resolved_band_mcp_tool_registrations
from band.integrations.opencode import parse_opencode_event
from band.integrations.opencode.client import HttpOpencodeClient
from band.runtime.tools.agent import AgentTools

from factorykit.featherless import MODEL_IDS
from factorykit.featherless_guard import _Ledger, _policy
from factorykit.harnesses import _opencode_types, _GuardCallbackUsage
from tests.test_featherless_guard import models

ROOM = "00000000-0000-4000-8000-000000000001"
SESSION = "synthetic-session"


class NoReplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger_path = Path(self.directory.name).resolve() / "guard.json"
        self.ledger = _Ledger(self.ledger_path, _policy(models(), 25_000_000_000, 2_000_000, 21600))
        self.ledger.open()
        self.addCleanup(self.ledger.close)
        self.request_id = self.ledger.reserve(MODEL_IDS[0], 16)
        self.ledger.settle(self.request_id, 10, 3)
        self.abort_requests = []
        self.abort_handler = None

        async def respond(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, f"/session/{SESSION}/abort")
            self.abort_requests.append(request)
            return await self.abort_handler(request) if self.abort_handler else httpx.Response(200, json=True)

        self.client = HttpOpencodeClient(base_url="http://synthetic.invalid", directory="/synthetic/workspace",
                                         transport=httpx.MockTransport(respond))
        self.addAsyncCleanup(self.client.close)
        config_type, adapter_type = _opencode_types()
        self.adapter = adapter_type(config_type(base_url="http://synthetic.invalid", directory="/synthetic/workspace",
            provider_id="synthetic", model_id="synthetic", agent="factory", turn_timeout_s=None,
            approval_mode="auto_decline", question_mode="auto_reject", factory_request_ledger_path=self.ledger_path,
            factory_native_permissions=dict(read=True, write=True, bash=True, network=True),
            factory_http_password="synthetic-only"), emit=[Emit.USAGE], include_tools=["band_no_reply"])
        self.adapter._client = self.client
        self.tools = SimpleNamespace(room_id=ROOM, agent_id="synthetic-agent", terminal_status=None,
                                     send_message=AsyncMock(), send_failure=AsyncMock(), send_event=AsyncMock())
        self.tools.no_reply = MethodType(AgentTools.no_reply, self.tools)
        self.state = await self.adapter._get_or_create_room_state(ROOM)
        self.state.tools = self.tools
        self.state.session_id = SESSION
        self.adapter._room_by_session[SESSION] = ROOM
        self.turn = self.adapter._begin_turn(self.state, session_id=SESSION, client=self.client,
                                            tools=self.tools, sender_id="synthetic-user")
        self.registration = next(tool for tool in build_resolved_band_mcp_tool_registrations(
            get_tools=self.adapter._get_room_tools, tool_definitions=self.adapter._tool_definitions)
            if tool.name == "band_no_reply")
        self.tasks = []
        self.addAsyncCleanup(self.clean_tasks)

    async def clean_tasks(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        quiet = getattr(self.turn, "_factory_no_reply_task", None)
        if quiet is not None:
            if not quiet.done():
                quiet.cancel()
            await asyncio.gather(quiet, return_exceptions=True)

    def task(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        return task

    async def invoke(self):
        return await self.registration.execute({"chat_id": ROOM, "reason": "Synthetic quiet callback."})

    async def event(self, kind, **values):
        await self.adapter._handle_event(parse_opencode_event({"type": kind,
                                                              "properties": {"sessionID": SESSION, **values}}))

    async def usage(self, error=None):
        await self.event("message.updated", info={"id": "synthetic-assistant", "sessionID": SESSION,
            "role": "assistant", "tokens": {"input": 10, "output": 3}, **({"error": error} if error else {})})

    async def test_mcp_withholds_result_until_successful_abort_and_real_idle_reports_usage(self):
        entered, release = asyncio.Event(), asyncio.Event()
        native_stopped = False
        async def abort(_request):
            nonlocal native_stopped
            entered.set()
            await release.wait()
            native_stopped = True
            return httpx.Response(200, json=True)
        self.abort_handler = abort
        await self.usage()
        watcher = self.task(self.adapter._watch_turn_completion(self.state, ROOM, self.turn))
        callback = self.task(self.invoke())
        await entered.wait()
        self.assertFalse(callback.done())
        self.assertFalse(self.turn.turn_future.done())
        release.set()
        self.assertEqual(await callback, '{"status": "no_reply"}')
        self.assertTrue(native_stopped)
        self.assertFalse(watcher.done())  # HTTP acknowledgement never fabricates native idle.
        await self.event("session.idle")
        await watcher
        self.tools.send_message.assert_not_awaited()
        self.tools.send_failure.assert_not_awaited()
        self.tools.send_event.assert_awaited_once()
        self.assertEqual(self.tools.send_event.await_args.kwargs["metadata"]["band_usage"]["input_tokens"], 10)
        self.assertIsNone(self.state.turn)
        self.assertEqual(len(self.abort_requests), 1)

    async def test_streamed_tool_cannot_abort_before_durable_provider_settlement(self):
        inflight = self.ledger.reserve(MODEL_IDS[0], 16)
        before = self.ledger_path.read_bytes()
        callback = self.task(self.invoke())
        await asyncio.sleep(0.03)
        self.assertFalse(callback.done())
        self.assertEqual(self.abort_requests, [])
        self.assertEqual(self.ledger_path.read_bytes(), before)
        self.ledger.settle(inflight, 11, 2)
        settled = self.ledger_path.read_bytes()
        self.assertEqual(await callback, '{"status": "no_reply"}')
        self.assertEqual(len(self.abort_requests), 1)
        self.assertEqual(self.ledger_path.read_bytes(), settled)
        self.assertTrue(all(row["status"] == "settled" for row in self.ledger.data["requests"].values()))

    async def test_self_aborted_error_does_not_finish_before_idle_or_hide_usage(self):
        await self.invoke()
        await self.usage({"name": "MessageAbortedError", "data": {"message": "synthetic abort"}})
        await self.event("session.error", error={"name": "MessageAbortedError"})
        self.assertIsNone(self.turn.last_error_message)
        self.assertFalse(self.turn.turn_future.done())
        self.assertEqual(self.turn.usage_by_message["synthetic-assistant"].input_tokens, 10)
        await self.event("session.idle")
        self.assertTrue(self.turn.turn_future.done())
        await self.adapter._deliver_fallback_text(ROOM, self.turn)
        self.tools.send_message.assert_not_awaited()
        self.tools.send_failure.assert_not_awaited()

    async def test_idle_racing_abort_http_response_waits_for_both(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def abort(_request):
            entered.set()
            await release.wait()
            return httpx.Response(200)
        self.abort_handler = abort
        await self.usage()
        watcher = self.task(self.adapter._watch_turn_completion(self.state, ROOM, self.turn))
        callback = self.task(self.invoke())
        await entered.wait()
        await self.event("session.idle")
        await asyncio.sleep(0)
        self.assertFalse(watcher.done())
        self.tools.send_event.assert_not_awaited()
        release.set()
        await callback
        await watcher
        self.tools.send_failure.assert_not_awaited()
        self.tools.send_event.assert_awaited_once()

    async def test_mcp_transport_cancel_does_not_cancel_captured_native_abort(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def abort(_request):
            entered.set()
            await release.wait()
            return httpx.Response(200)
        self.abort_handler = abort
        callback = self.task(self.invoke())
        await entered.wait()
        callback.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await callback
        quiet = self.turn._factory_no_reply_task
        self.assertFalse(quiet.cancelled())
        release.set()
        await quiet
        self.assertTrue(self.turn._factory_no_reply_confirmed)
        self.assertFalse(self.turn.turn_future.done())
        self.assertEqual(len(self.abort_requests), 1)

    async def test_unrelated_provider_error_is_still_a_failure_after_quiet_abort(self):
        await self.invoke()
        await self.usage({"name": "APIError", "data": {"message": "synthetic provider failure"}})
        await self.adapter._deliver_fallback_text(ROOM, self.turn)
        self.assertEqual(self.tools.terminal_status, "failed")
        self.tools.send_failure.assert_awaited_once()
        self.assertIn("APIError", self.turn.last_error_message)

    async def test_unknown_usage_and_abort_failure_never_become_quiet_success(self):
        inflight = self.ledger.reserve(MODEL_IDS[0], 16)
        self.ledger.unknown(inflight)
        before = self.ledger_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "unknown provider usage"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.assertFalse(getattr(self.turn, "_factory_no_reply_confirmed", False))
        self.assertEqual(self.ledger_path.read_bytes(), before)
        self.assertEqual(self.tools.terminal_status, "failed")

    async def test_abort_http_failure_is_not_suppressed(self):
        async def abort(_request):
            return httpx.Response(503)
        self.abort_handler = abort
        with self.assertRaises(httpx.HTTPStatusError):
            await self.invoke()
        self.assertEqual(self.tools.terminal_status, "failed")
        self.assertFalse(getattr(self.turn, "_factory_no_reply_confirmed", False))
        self.assertEqual(self.turn.last_error_message, "OpenCode no_reply termination failed")

    async def test_failed_abort_watcher_reports_failure_and_captured_usage(self):
        async def abort(_request):
            return httpx.Response(503)
        self.abort_handler = abort
        self.tools.ledger = SimpleNamespace(stop=asyncio.Event())
        await self.usage()
        watcher = self.task(self.adapter._watch_turn_completion(self.state, ROOM, self.turn))
        with self.assertRaises(httpx.HTTPStatusError):
            await self.invoke()
        await watcher
        self.assertTrue(self.tools.ledger.stop.is_set())
        self.assertEqual(self.tools.terminal_status, "failed")
        self.tools.send_failure.assert_awaited_once()
        self.tools.send_message.assert_not_awaited()
        self.tools.send_event.assert_awaited_once()
        self.assertEqual(self.tools.send_event.await_args.kwargs["metadata"]["band_usage"]["input_tokens"], 10)
        self.assertFalse(getattr(self.turn, "_factory_no_reply_confirmed", False))
        self.assertIsNone(self.state.turn)

    async def test_abort_error_during_settlement_wait_is_not_self_requested(self):
        self.ledger.reserve(MODEL_IDS[0], 16)
        callback = self.task(self.invoke())
        await asyncio.sleep(0.02)
        self.assertFalse(getattr(self.turn, "_factory_no_reply_abort_requested", False))
        await self.usage({"name": "MessageAbortedError"})
        self.assertIn("MessageAbortedError", self.turn.last_error_message)
        await self.event("session.error", error={"name": "MessageAbortedError"})
        with self.assertRaisesRegex(ValueError, "exact active room turn"):
            await callback
        self.assertEqual(self.abort_requests, [])
        self.assertFalse(getattr(self.turn, "_factory_no_reply_confirmed", False))

    async def test_stale_context_and_turn_change_never_abort_successor(self):
        self.state.tools = SimpleNamespace()
        with self.assertRaisesRegex(ValueError, "exact active room turn"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.state.tools = self.tools
        async def change_turn(**_arguments):
            self.adapter._begin_turn(self.state, session_id=SESSION, client=self.client,
                                     tools=self.tools, sender_id="different-user")
            return {"status": "no_reply"}
        self.tools.no_reply = change_turn
        with self.assertRaisesRegex(ValueError, "turn changed"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.assertFalse(self.state.turn.turn_future.done())

    async def test_failed_underlying_tool_does_not_abort_or_claim_quiet(self):
        self.tools.no_reply = AsyncMock(side_effect=ValueError("synthetic tool rejection"))
        with self.assertRaisesRegex(ValueError, "tool rejection"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.assertFalse(hasattr(self.turn, "_factory_no_reply_task"))

    async def test_ordinary_messages_do_not_silence_unrequested_native_abort(self):
        await self.usage({"name": "MessageAbortedError"})
        self.assertIn("MessageAbortedError", self.turn.last_error_message)
        await self.event("session.error", error={"name": "MessageAbortedError"})
        self.assertTrue(self.turn.turn_future.done())

    def bind_observer(self):
        self.adapter._registered_client = self.client
        self.adapter._mcp_server_name = self.adapter._agent_mcp_server_name(self.tools.agent_id)
        self.original_forward = AsyncMock(return_value="forwarded")
        self.guard = SimpleNamespace(_ledger=self.ledger, _forward=self.original_forward)
        self.observer = _GuardCallbackUsage(self.guard)
        self.adapter.config = self.adapter.config.model_copy(update={"provider_id": "featherless",
            "model_id": MODEL_IDS[0], "factory_request_observer": self.observer})
        self.observer.bind(self.adapter, self.state, self.turn)
        return self.observer

    def callback_request(self, *, model=MODEL_IDS[0], names=None, prompt=17, output=4):
        key = self.ledger.reserve(model, 16)
        if names is None:
            names = [self.adapter._mcp_server_name + "_band_no_reply"]
        body = {"model": model, "tools": [{"type": "function", "function": {"name": name}} for name in names]}
        self.observer.observe(body, key)
        self.ledger.settle(key, prompt, output)
        return key

    async def test_quiet_usage_uses_only_exact_settled_main_ids_without_double_count(self):
        self.bind_observer()
        main = self.callback_request()
        self.callback_request(names=[], prompt=23, output=5)  # Auxiliary request.
        self.callback_request(names=["band_otheragent_band_no_reply"], prompt=31, output=6)
        await self.usage()  # Native partial counters must not be added again.
        before = self.ledger_path.read_bytes()
        await self.invoke()
        await self.event("session.idle")
        await self.adapter._emit_turn_usage(self.turn)
        self.tools.send_event.assert_awaited_once()
        usage = self.tools.send_event.await_args.kwargs["metadata"]["band_usage"]
        self.assertEqual((usage["input_tokens"], usage["output_tokens"]), (17, 4))
        self.assertEqual(self.turn._factory_no_reply_request_ids, (main,))
        self.assertEqual(self.ledger_path.read_bytes(), before)
        self.assertNotIn("factory_request_observer", self.adapter.config.model_dump())

    async def test_normal_native_usage_is_unchanged_with_observer(self):
        self.bind_observer()
        self.callback_request(prompt=29, output=8)
        await self.usage()
        await self.event("session.idle")
        await self.adapter._emit_turn_usage(self.turn)
        usage = self.tools.send_event.await_args.kwargs["metadata"]["band_usage"]
        self.assertEqual((usage["input_tokens"], usage["output_tokens"]), (10, 3))

    async def test_missing_callback_request_cannot_claim_usage_or_abort(self):
        self.bind_observer()
        self.callback_request(names=[])
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.assertFalse(getattr(self.turn, "_factory_no_reply_confirmed", False))
        self.tools.send_event.assert_not_awaited()

    async def test_wrong_model_and_mixed_namespaces_are_not_bound_usage(self):
        self.bind_observer()
        self.callback_request(model=MODEL_IDS[1])
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.observer.release(self.turn)
        self.observer.bind(self.adapter, self.state, self.turn)
        self.callback_request(names=[self.adapter._mcp_server_name + "_band_no_reply", "band_otheragent_band_no_reply"])
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            self.observer.request_ids(self.adapter, self.turn)

    async def test_ambiguous_active_rooms_never_assign_request(self):
        self.bind_observer()
        other = await self.adapter._get_or_create_room_state("different-room")
        other.tools = self.tools
        second = self.adapter._begin_turn(other, session_id="different-session", client=self.client,
                                          tools=self.tools, sender_id="different-user")
        self.callback_request()
        for turn in (self.turn, second):
            with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
                self.observer.request_ids(self.adapter, turn)
        self.assertEqual(self.abort_requests, [])

    async def test_successor_cannot_inherit_prior_callback_requests(self):
        self.bind_observer()
        first = self.callback_request()
        old = self.turn
        new = self.adapter._begin_turn(self.state, session_id=SESSION, client=self.client,
                                       tools=self.tools, sender_id="new-user")
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            self.observer.request_ids(self.adapter, old)
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            self.observer.request_ids(self.adapter, new)
        second = self.callback_request()
        self.assertEqual(self.observer.request_ids(self.adapter, new), (second,))
        self.assertNotIn(first, self.observer.request_ids(self.adapter, new))
        self.adapter._clear_turn_state(self.state, expected_turn=old)
        self.assertEqual(self.observer.request_ids(self.adapter, new), (second,))
        self.adapter._clear_turn_state(self.state, expected_turn=new)
        self.assertNotIn(id(new), self.observer.entries)

    async def test_captured_unknown_usage_does_not_abort_or_emit_estimates(self):
        self.bind_observer()
        key = self.ledger.reserve(MODEL_IDS[0], 16)
        self.observer.observe({"model": MODEL_IDS[0], "tools": [{"function": {"name": self.adapter._mcp_server_name + "_band_no_reply"}}]}, key)
        self.ledger.unknown(key)
        with self.assertRaisesRegex(ValueError, "unknown provider usage"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.tools.send_event.assert_not_awaited()

    async def test_forward_observer_calls_original_and_keeps_request_bytes(self):
        self.bind_observer()
        key = self.ledger.reserve(MODEL_IDS[0], 16)
        body = {"model": MODEL_IDS[0], "tools": [{"function": {"name": self.adapter._mcp_server_name + "_band_no_reply"}}]}
        before = self.ledger_path.read_bytes()
        self.assertEqual(await self.guard._forward(body, key, "synthetic-writer"), "forwarded")
        self.original_forward.assert_awaited_once_with(body, key, "synthetic-writer")
        self.assertEqual(self.ledger_path.read_bytes(), before)
        self.ledger.settle(key, 13, 2)
        self.assertEqual(self.observer.request_ids(self.adapter, self.turn), (key,))
        self.assertEqual(set(self.observer.entries[id(self.turn)]) & {"body", "prompt", "messages", "tools"}, set())

    async def test_same_model_other_actor_has_separate_exact_request_ids(self):
        self.bind_observer()
        other = type(self.adapter)(self.adapter.config, emit=[Emit.USAGE], include_tools=["band_no_reply"])
        other._client = other._registered_client = self.client
        tools = SimpleNamespace(agent_id="other-agent")
        other._mcp_server_name = other._agent_mcp_server_name(tools.agent_id)
        state = await other._get_or_create_room_state(ROOM)
        state.tools = tools
        turn = other._begin_turn(state, session_id="other-session", client=self.client,
                                 tools=tools, sender_id="other-user")
        key = self.callback_request(names=[other._mcp_server_name + "_band_no_reply"])
        self.assertEqual(self.observer.request_ids(other, turn), (key,))
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            self.observer.request_ids(self.adapter, self.turn)
        main = self.callback_request()
        self.assertEqual(self.observer.request_ids(self.adapter, self.turn), (main,))

    async def test_missing_captured_record_never_claims_usage(self):
        self.bind_observer()
        key = self.callback_request()
        del self.ledger.data["requests"][key]
        self.ledger._save()  # Deliberately incomplete synthetic fixture.
        with self.assertRaisesRegex(ValueError, "missing or unsettled"):
            await self.invoke()
        self.assertEqual(self.abort_requests, [])
        self.tools.send_event.assert_not_awaited()

    async def test_changed_actor_or_model_cannot_inherit_active_binding(self):
        self.bind_observer()
        self.callback_request()
        actor = self.tools.agent_id
        self.tools.agent_id = "changed-actor"
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            self.observer.request_ids(self.adapter, self.turn)
        self.tools.agent_id = actor
        self.adapter.config = self.adapter.config.model_copy(update={"model_id": MODEL_IDS[1]})
        with self.assertRaisesRegex(ValueError, "not bound to its exact callback"):
            self.observer.request_ids(self.adapter, self.turn)

    def test_unregistered_identity_namespace_cannot_bind(self):
        self.bind_observer()
        self.observer.release(self.turn)
        self.adapter._mcp_server_name = "band_staleidentity"
        with self.assertRaisesRegex(ValueError, "registered agent MCP identity"):
            self.observer.bind(self.adapter, self.state, self.turn)

    def test_operational_ledger_path_is_excluded_from_model_config(self):
        self.assertNotIn("factory_request_ledger_path", self.adapter.config.model_dump())


if __name__ == "__main__":
    unittest.main()
