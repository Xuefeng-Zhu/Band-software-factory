"""Offline compact-index and targeted complete-record tool regressions."""
import json
import unittest

from band.integrations.mcp.engine import build_resolved_band_mcp_tool_registrations
from band.integrations.claude_sdk.tools import build_band_sdk_tools
from factorykit.common import FactoryError, canonical
from factorykit.task_board_adapters import Factory_Task_BoardInput, TaskBoardAdapterTools
from pydantic import ValidationError
from tests import test_task_board as fixtures


class TaskBoardReadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f = fixtures.TaskBoardTests(methodName="runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    async def test_default_index_is_small_and_target_is_complete_without_writes(self):
        item = self.f.item()
        item["requirements"] = ["complete source requirement " * 500]
        record = await self.f.publish(item)
        self.assertIn('Call factory_task_board with id="WORK-1"', record["band_payload"]["detail"])
        await self.f.ready("WORK-2")
        before = self.f.path.read_bytes()
        guard = self.f.wrapper()
        index = await guard.execute_tool_call_structured("factory_task_board", {})
        self.assertTrue(index.ok)
        self.assertEqual(index.value["view"], "index")
        row = index.value["items"][item["id"]]
        self.assertEqual((row["version"], row["owner"], row["state"], row["candidate_commit"], row["pending"]),
                         (1, item["owner"], "READY", None, None))
        self.assertNotIn("requirements", json.dumps(index.value))
        targeted = await guard.execute_tool_call_structured("factory_task_board", {"id": item["id"]})
        self.assertTrue(targeted.ok)
        self.assertEqual(set(targeted.value["items"]), {item["id"]})
        self.assertEqual(targeted.value["items"][item["id"]]["item"], item)
        self.assertEqual(targeted.value["items"][item["id"]]["band_payload"], record["band_payload"])
        full = self.f.board.snapshot()
        self.assertEqual(full["items"][item["id"]]["item"], item)
        self.assertLess(len(canonical(index.value)), len(canonical(full)) // 5)
        self.assertEqual(self.f.path.read_bytes(), before)
        self.assertEqual(self.f.mutations(), 2)

    async def test_pending_index_reports_uncertainty_and_id_retains_full_claim(self):
        await self.f.fail_create_after_remote_write(RuntimeError("response lost"))
        before = self.f.path.read_bytes()
        index = self.f.board.read()
        row = index["items"]["WORK-1"]
        self.assertEqual(row["version"], 0)
        self.assertIsNone(row["state"])
        self.assertEqual(row["owner"], "team/backend")
        self.assertEqual(row["pending"]["operation"], "create")
        self.assertEqual(row["pending"]["write_error"]["outcome"], "unknown")
        full = self.f.board.read("WORK-1")
        self.assertEqual(full["items"]["WORK-1"]["pending"]["item"], self.f.item())
        self.assertEqual(self.f.path.read_bytes(), before)
        self.assertEqual(self.f.mutations(), 1)

    async def test_read_arguments_are_id_only_and_never_fall_back_to_full_board(self):
        await self.f.ready()
        before = self.f.path.read_bytes()
        guard = self.f.wrapper()
        for invalid in ({"id": 1}, {"id": False}, {"id": []}, {"id": ""}, {"id": "MISSING"},
                        {"id": "WORK-1", "actor_id": fixtures.PM}, [], None):
            with self.subTest(arguments=invalid):
                response = await guard.execute_tool_call_structured("factory_task_board", invalid)
                self.assertFalse(response.ok)
        self.assertEqual(self.f.path.read_bytes(), before)

    async def test_actual_claude_and_opencode_mcp_support_optional_strict_id(self):
        await self.f.ready()
        router = TaskBoardAdapterTools(fixtures.ROOM, fixtures.PM)
        guard = self.f.wrapper()
        opencode = {tool.name: tool for tool in build_resolved_band_mcp_tool_registrations(
            tool_definitions=[], get_tools=lambda _: None, additional_tools=router.additional_tools)}
        claude = {tool.name: tool for tool in build_band_sdk_tools(tool_definitions=[],
            get_tools=lambda _: None, additional_tools=router.additional_tools)}
        with router.bind(guard):
            index = json.loads(await opencode["factory_task_board"].execute({"chat_id": fixtures.ROOM}))
            target = json.loads(await opencode["factory_task_board"].execute({"chat_id": fixtures.ROOM, "id": "WORK-1"}))
            claude_target = await claude["factory_task_board"].handler({"chat_id": fixtures.ROOM, "id": "WORK-1"})
        self.assertEqual(index["view"], "index")
        self.assertEqual(target["items"]["WORK-1"]["item"], self.f.item())
        self.assertEqual(json.loads(claude_target["content"][0]["text"])["items"]["WORK-1"]["item"], self.f.item())
        schema = Factory_Task_BoardInput.model_json_schema()
        self.assertIn("id", schema["properties"])
        self.assertNotIn("id", schema.get("required", []))
        for invalid in ({"id": 7}, {"id": True}, {"room_id": fixtures.ROOM}):
            with self.assertRaises(ValidationError):
                Factory_Task_BoardInput.model_validate(invalid)
        self.assertEqual(self.f.mutations(), 1)


if __name__ == "__main__":
    unittest.main()
