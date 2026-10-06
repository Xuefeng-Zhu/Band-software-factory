"""Offline proof at the maintained Claude SDK and OpenCode MCP entry points."""
from types import SimpleNamespace
import json
import unittest
from unittest.mock import AsyncMock

from band.core.exceptions import BandToolError
from band.integrations.claude_sdk.tools import build_band_sdk_tools
from band.integrations.mcp.engine import build_resolved_band_mcp_tool_registrations
from band.runtime.custom_tools import custom_tool_effects, get_custom_tool_name
from band.runtime.tools.schema import ToolCallOutcome
from band.runtime.tools.types import TurnEffect
from pydantic import ValidationError

from factorykit.common import FactoryError
from factorykit.task_board_adapters import Factory_Work_ItemInput, TaskBoardAdapterTools


ROOM = "00000000-0000-4000-8000-000000000001"
ACTOR = "00000000-0000-4000-8000-000000000002"
NAMES = {"factory_work_item", "factory_task_board", "factory_reconcile_task"}


class TaskBoardAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = TaskBoardAdapterTools(ROOM, ACTOR)
        self.wrapped = SimpleNamespace(actor_id=ACTOR, agent_id=ACTOR, room_id=ROOM,
            task_board=object(), board_window=lambda: 10,
            execute_tool_call_structured=AsyncMock(return_value=ToolCallOutcome(value={"ok": "board"}, ok=True)))

    def claude_tools(self):
        return {tool.name: tool for tool in build_band_sdk_tools(tool_definitions=[],
            get_tools=lambda _: None, additional_tools=self.router.additional_tools)}

    def opencode_tools(self):
        return {tool.name: tool for tool in build_resolved_band_mcp_tool_registrations(
            tool_definitions=[], get_tools=lambda _: None, additional_tools=self.router.additional_tools)}

    def test_names_and_effects_match_guarded_tools(self):
        definitions = self.router.additional_tools
        self.assertEqual({get_custom_tool_name(model) for model, _ in definitions}, NAMES)
        self.assertEqual(custom_tool_effects(definitions), dict.fromkeys(NAMES, TurnEffect.OBSERVE))
        definitions.clear()
        self.assertEqual(len(self.router.additional_tools), 3)

    def test_work_item_schema_and_strict_inputs(self):
        schema = Factory_Work_ItemInput.model_json_schema()
        self.assertIn("owner", schema["properties"]["item"]["properties"])
        self.assertIn("state", schema["properties"]["item"]["required"])
        for invalid in ({"item": {}, "expected_version": True},
                        {"item": {}, "expected_version": 0, "actor_id": ACTOR}):
            with self.assertRaises(ValidationError):
                Factory_Work_ItemInput.model_validate(invalid)

    async def test_claude_mcp_routes_to_current_structured_dispatcher(self):
        tools = self.claude_tools()
        self.assertEqual(set(tools), NAMES)
        with self.router.bind(self.wrapped):
            result = await tools["factory_work_item"].handler({"chat_id": ROOM,
                "item": {"id": "WORK-1"}, "expected_version": 0})
        self.assertFalse(result.get("is_error", False))
        self.wrapped.execute_tool_call_structured.assert_awaited_once_with("factory_work_item",
            {"item": {"id": "WORK-1"}, "expected_version": 0})

    async def test_opencode_mcp_routes_to_current_structured_dispatcher(self):
        tools = self.opencode_tools()
        self.assertEqual(set(tools), NAMES)
        with self.router.bind(self.wrapped):
            result = await tools["factory_reconcile_task"].execute({"chat_id": ROOM,
                "id": "WORK-1", "task_id": ROOM})
        self.assertEqual(json.loads(result), {"ok": "board"})
        self.wrapped.execute_tool_call_structured.assert_awaited_once_with("factory_reconcile_task",
            {"id": "WORK-1", "task_id": ROOM})

    async def test_unbound_and_released_turns_cannot_use_mcp_tools(self):
        tool = self.opencode_tools()["factory_task_board"]
        with self.assertRaises(BandToolError):
            await tool.execute({"chat_id": ROOM})
        with self.router.bind(self.wrapped):
            await tool.execute({"chat_id": ROOM})
        with self.assertRaises(BandToolError):
            await tool.execute({"chat_id": ROOM})
        self.assertEqual(self.wrapped.execute_tool_call_structured.await_count, 1)

    async def test_expired_or_stopped_turn_is_rechecked_at_dispatch(self):
        tool = self.opencode_tools()["factory_task_board"]
        with self.router.bind(self.wrapped):
            self.wrapped.board_window = lambda: 0
            with self.assertRaises(BandToolError):
                await tool.execute({"chat_id": ROOM})
        self.wrapped.execute_tool_call_structured.assert_not_awaited()

    def test_room_actor_and_concurrent_bindings_fail_closed(self):
        for field in ("room_id", "agent_id", "actor_id"):
            original = getattr(self.wrapped, field)
            setattr(self.wrapped, field, "different")
            with self.assertRaises(FactoryError):
                with self.router.bind(self.wrapped):
                    self.fail("Unexpected binding")
            setattr(self.wrapped, field, original)
        with self.router.bind(self.wrapped):
            with self.assertRaises(FactoryError):
                with self.router.bind(self.wrapped):
                    self.fail("Unexpected concurrent binding")

    async def test_failed_guard_is_mcp_error_not_success(self):
        self.wrapped.execute_tool_call_structured.return_value = ToolCallOutcome(
            value="Independent review required", ok=False, error_message="task_board_blocked")
        with self.router.bind(self.wrapped):
            with self.assertRaisesRegex(BandToolError, "Independent review"):
                await self.opencode_tools()["factory_task_board"].execute({"chat_id": ROOM})
            result = await self.claude_tools()["factory_task_board"].handler({"chat_id": ROOM})
        self.assertTrue(result["is_error"])

    async def test_router_instances_never_share_admitted_tools(self):
        other = TaskBoardAdapterTools(ROOM, ACTOR)
        registrations = build_resolved_band_mcp_tool_registrations(tool_definitions=[],
            get_tools=lambda _: None, additional_tools=other.additional_tools)
        board = next(t for t in registrations if t.name == "factory_task_board")
        with self.router.bind(self.wrapped):
            with self.assertRaises(BandToolError):
                await board.execute({"chat_id": ROOM})
        self.wrapped.execute_tool_call_structured.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
