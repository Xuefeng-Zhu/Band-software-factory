"""Actual BAND MCP schema/dispatch checks, without servers, sockets or inference."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from pydantic import BaseModel

from band.adapters import OpencodeAdapter
from band.core.types import Capability
from band.integrations.mcp.engine import build_resolved_band_mcp_tool_registrations
from band.runtime.custom_tools import declares_turn_effect
from band.runtime.tools.registry import TOOL_DEFINITIONS, iter_tool_definitions
from band.runtime.tools.types import TurnEffect

from factorykit.harnesses import _opencode_types


ROOM = "00000000-0000-4000-8000-000000000001"
PEER = "00000000-0000-4000-8000-000000000002"
EXCLUDED = ("band_remove_participant", "band_create_chatroom", "band_lookup_peers",
            "band_create_task", "band_update_task", "band_set_board")


def adapter(**features):
    config_type, adapter_type = _opencode_types()
    config = config_type(base_url="http://127.0.0.1:1", directory="/tmp",
                         provider_id="offline", model_id="offline",
                         approval_mode="auto_decline", question_mode="auto_reject",
                         factory_native_permissions=dict(read=False, write=False, bash=False, network=False),
                         factory_http_password="offline-synthetic")
    return adapter_type(config, **features)


def registrations(instance, *, definitions=None):
    return {registration.name: registration for registration in build_resolved_band_mcp_tool_registrations(
        get_tools=instance._get_room_tools,
        tool_definitions=instance._tool_definitions if definitions is None else definitions,
        additional_tools=instance._custom_tools)}


class ToolPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_factory_exclusions_reach_actual_mcp_definitions_and_visibility(self):
        instance = adapter(capabilities=[Capability.TASKS], exclude_tools=EXCLUDED)
        self.assertIsInstance(instance, OpencodeAdapter)
        schema_names = set(registrations(instance))
        self.assertTrue({"band_get_participants", "band_add_participant", "band_no_reply"} <= schema_names)
        self.assertFalse(schema_names.intersection(EXCLUDED))
        self.assertEqual(schema_names, instance._own_tool_names)
        visibility = instance._mcp_tool_visibility()
        self.assertFalse(visibility[f"{instance._mcp_server_name}_*"])
        for name in EXCLUDED:
            self.assertNotIn(f"{instance._mcp_server_name}_{name}", visibility)
            self.assertFalse(instance._is_own_band_tool(f"{instance._mcp_server_name}_{name}"))
        for name in schema_names:
            self.assertTrue(visibility[f"{instance._mcp_server_name}_{name}"])
        self.assertIsNone(instance._client)
        self.assertIsNone(instance._mcp_backend)

    async def test_non_pm_add_is_not_advertised(self):
        instance = adapter(exclude_tools=[*EXCLUDED, "band_add_participant"])
        self.assertNotIn("band_add_participant", registrations(instance))

    async def test_include_category_and_exclude_compose_with_capabilities(self):
        instance = adapter(capabilities=[Capability.MEMORY], include_categories=["chat"],
                           include_tools=["band_no_reply", "band_get_participants", "band_store_memory"],
                           exclude_tools=["band_no_reply"])
        self.assertEqual(set(registrations(instance)), {"band_get_participants"})
        empty = adapter(include_tools=[])
        self.assertEqual(registrations(empty), {})
        self.assertFalse(empty._mcp_tool_visibility()[f"{empty._mcp_server_name}_*"])

    async def test_restricted_capability_rejects_stale_definition(self):
        instance = adapter(capabilities=[Capability.MEMORY])
        tools = SimpleNamespace(store_memory=AsyncMock())
        instance._rooms[ROOM] = SimpleNamespace(tools=tools)
        original = registrations(instance)["band_store_memory"]
        instance.apply_effective_features(replace(instance.features, capabilities=frozenset()))
        self.assertNotIn("band_store_memory", registrations(instance))
        # Execute the exact previously advertised SDK registration after negotiation.
        arguments = {"chat_id": ROOM, "content": "offline", "system": "working",
                     "type": "semantic", "segment": "agent", "thought": "offline", "scope": "agent"}
        with self.assertRaisesRegex(ValueError, "Factory tool policy denies"):
            await original.execute(arguments)
        tools.store_memory.assert_not_awaited()

    async def test_stale_excluded_registration_cannot_call_underlying_method(self):
        instance = adapter()
        tools = SimpleNamespace(add_participant=AsyncMock(return_value={"id": PEER}))
        instance._rooms[ROOM] = SimpleNamespace(tools=tools)
        original = registrations(instance)["band_add_participant"]
        retained_method = instance._get_room_tools(ROOM).add_participant
        instance.apply_effective_features(replace(instance.features, exclude_tools=("band_add_participant",)))
        with self.assertRaisesRegex(ValueError, "Factory tool policy denies"):
            await original.execute({"chat_id": ROOM, "identifier": PEER})
        with self.assertRaisesRegex(ValueError, "Factory tool policy denies"):
            await retained_method(identifier=PEER)
        tools.add_participant.assert_not_awaited()

    async def test_unknown_method_is_not_delegated(self):
        instance = adapter()
        tools = SimpleNamespace(unregistered_mutation=AsyncMock())
        instance._rooms[ROOM] = SimpleNamespace(tools=tools)
        definition = replace(TOOL_DEFINITIONS["band_no_reply"], method_name="unregistered_mutation")
        registration = registrations(instance, definitions=[definition])["band_no_reply"]
        with self.assertRaisesRegex(ValueError, "Factory tool policy denies"):
            await registration.execute({"chat_id": ROOM})
        tools.unregistered_mutation.assert_not_awaited()

    async def test_missing_room_cannot_resolve_tools(self):
        instance = adapter()
        self.assertIsNone(instance._get_room_tools(ROOM))
        with self.assertRaisesRegex(ValueError, "No tools available"):
            await registrations(instance)["band_no_reply"].execute({"chat_id": ROOM})

    async def test_authorization_hook_blocks_before_underlying_side_effect(self):
        instance = adapter()
        tools = SimpleNamespace(authorize_mcp_tool=Mock(side_effect=ValueError("offline policy block")),
                                no_reply=AsyncMock())
        instance._rooms[ROOM] = SimpleNamespace(tools=tools)
        with self.assertRaisesRegex(ValueError, "offline policy block"):
            await registrations(instance)["band_no_reply"].execute({"chat_id": ROOM, "reason": "fixture"})
        tools.authorize_mcp_tool.assert_called_once_with("band_no_reply", {"reason": "fixture"})
        tools.no_reply.assert_not_awaited()

    async def test_excluded_tool_cannot_reach_optional_authorization_hook(self):
        instance = adapter(exclude_tools=["band_add_participant"])
        tools = SimpleNamespace(authorize_mcp_tool=Mock(), add_participant=AsyncMock())
        instance._rooms[ROOM] = SimpleNamespace(tools=tools)
        registration = registrations(instance, definitions=[TOOL_DEFINITIONS["band_add_participant"]])["band_add_participant"]
        with self.assertRaisesRegex(ValueError, "Factory tool policy denies"):
            await registration.execute({"chat_id": ROOM, "identifier": PEER})
        tools.authorize_mcp_tool.assert_not_called()
        tools.add_participant.assert_not_awaited()

    async def test_pm_schema_uses_direct_roster_uuid_without_mutating_sdk_schema(self):
        original = TOOL_DEFINITIONS["band_add_participant"].input_model
        instance = adapter()
        registration = registrations(instance)["band_add_participant"]
        self.assertIn("PM only", registration.description)
        self.assertIn("band_get_participants", registration.description)
        self.assertIn("exact UUID", registration.description)
        self.assertNotIn("band_lookup_peers", registration.description)
        self.assertIn("band_lookup_peers", original.__doc__)
        self.assertIn("chat_id", registration.input_model.model_json_schema()["required"])
        self.assertIn("Exact UUID", registration.input_model.model_json_schema()["properties"]["identifier"]["description"])

    async def test_mcp_keeps_actual_runtime_pm_roster_guard(self):
        from factorykit.runtime import AuditedTools, GateError
        instance = adapter()
        native = SimpleNamespace(get_participants=AsyncMock(return_value=[]),
                                 add_participant=AsyncMock(return_value={"id": PEER}))
        ledger = SimpleNamespace(data={}, limits={"max_repairs": 2}, save=Mock())
        wrapped = AuditedTools(native, ledger, "pm", Path("/unused-offline"),
                               [{"agent_id": PEER, "handle": "@offline/reviewer", "display_name": "Reviewer"}])
        instance._rooms[ROOM] = SimpleNamespace(tools=wrapped)
        registration = registrations(instance)["band_add_participant"]
        result = await registration.execute({"chat_id": ROOM, "identifier": PEER})
        self.assertEqual(json.loads(result), {"id": PEER})
        native.add_participant.assert_awaited_once_with(PEER, role="member")
        self.assertEqual(ledger.data["membership_attempts"], {PEER: 1})
        with self.assertRaises(GateError):
            await registration.execute({"chat_id": ROOM, "identifier": PEER, "role": "owner"})
        with self.assertRaises(GateError):
            await registration.execute({"chat_id": ROOM, "identifier": "unconfigured"})
        self.assertEqual(native.add_participant.await_count, 1)

    async def test_mcp_rejects_forged_accounting_but_direct_adapter_telemetry_works(self):
        from factorykit.runtime import AuditedTools, GateError
        with tempfile.TemporaryDirectory() as root:
            audit = Path(root) / "audit.jsonl"
            native = SimpleNamespace(send_event=AsyncMock(return_value={"sent": True}))
            ledger = SimpleNamespace(record=Mock())
            wrapped = AuditedTools(native, ledger, "pm", audit, harness="opencode", turn_id="synthetic-turn")
            instance = adapter()
            instance._rooms[ROOM] = SimpleNamespace(tools=wrapped)
            registration = registrations(instance)["band_send_event"]
            usage = {"band_usage": {"input_tokens": 7, "output_tokens": 2}}
            for metadata in (usage, {"opencode_session_id": "synthetic-session"},
                             {"factory_turn_status": "completed"}):
                with self.subTest(metadata_key=next(iter(metadata))):
                    with self.assertRaisesRegex(GateError, "cannot forge"):
                        await registration.execute({"chat_id": ROOM, "content": "offline",
                                                    "message_type": "task", "metadata": metadata})
            ledger.record.assert_not_called()
            native.send_event.assert_not_awaited()
            self.assertFalse(wrapped.usage_observed)
            self.assertFalse(audit.exists())

            # This is the real adapter-facing method, outside the model MCP path.
            await wrapped.send_event("trusted adapter usage", "task", usage)
            ledger.record.assert_called_once_with("pm", usage, harness="opencode", turn_id="synthetic-turn")
            native.send_event.assert_awaited_once_with(content="trusted adapter usage", message_type="task", metadata=usage)
            self.assertTrue(wrapped.usage_observed)
            self.assertEqual(json.loads(audit.read_text())["metadata"], usage)

    async def test_custom_tool_filter_refresh_keeps_handler_semantics_and_effects(self):
        class FinishInput(BaseModel):
            """Finish an offline check."""

        calls = []

        @declares_turn_effect(TurnEffect.ACT)
        def finish():
            calls.append("called")
            return {"done": True}

        instance = adapter(additional_tools=[(FinishInput, finish)], include_tools=["finish"])
        first = registrations(instance)["finish"]
        self.assertEqual(json.loads(await first.execute({"chat_id": ROOM})), {"done": True})
        self.assertEqual(instance._custom_effects, {"finish": TurnEffect.ACT})
        instance.apply_effective_features(replace(instance.features, exclude_tools=("finish",)))
        self.assertEqual(registrations(instance), {})
        self.assertEqual(instance._custom_effects, {})
        with self.assertRaisesRegex(ValueError, "Factory tool policy denies"):
            await first.execute({"chat_id": ROOM})
        instance.apply_effective_features(replace(instance.features, exclude_tools=None))
        self.assertEqual(json.loads(await registrations(instance)["finish"].execute({"chat_id": ROOM})), {"done": True})
        self.assertEqual(calls, ["called", "called"])

    async def test_async_custom_input_validation_is_preserved(self):
        class InspectInput(BaseModel):
            count: int

        handler = AsyncMock(return_value={"inspected": True})
        instance = adapter(additional_tools=[(InspectInput, handler)], include_tools=["inspect"])
        registration = registrations(instance)["inspect"]
        await registration.execute({"chat_id": ROOM, "count": 3})
        self.assertIsInstance(handler.await_args.args[0], InspectInput)
        self.assertEqual(handler.await_args.args[0].count, 3)
        with self.assertRaises(ValueError):
            await registration.execute({"chat_id": ROOM, "count": "invalid"})
        self.assertEqual(handler.await_count, 1)

    async def test_custom_tools_without_known_category_are_omitted_by_category_filter(self):
        class InspectInput(BaseModel):
            pass

        instance = adapter(additional_tools=[(InspectInput, Mock())], include_categories=["chat"])
        self.assertNotIn("inspect", registrations(instance))

    async def test_pinned_sdk_agent_tool_methods_have_no_alias_bypass(self):
        definitions = iter_tool_definitions(capabilities=frozenset(Capability))
        self.assertEqual(len(definitions), len({definition.method_name for definition in definitions}))


if __name__ == "__main__":
    unittest.main()
