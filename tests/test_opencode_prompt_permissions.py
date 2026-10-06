"""Maintained SDK prompt transport, with no OpenCode server or provider calls."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import httpx
from band.core.types import PlatformMessage
from band.integrations.opencode.client import HttpOpencodeClient

from factorykit.harnesses import _opencode_types


ROOM = "00000000-0000-4000-8000-000000000001"


def adapter(policy, **features):
    config_type, adapter_type = _opencode_types()
    return adapter_type(config_type(base_url="http://127.0.0.1:1", directory="/synthetic/workspace",
        provider_id="synthetic", model_id="synthetic", agent="factory",
        approval_mode="auto_decline", question_mode="auto_reject",
        factory_native_permissions=policy, factory_http_password="synthetic-only"), emit=[], **features)


class PromptPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_adapter_prompt_body_has_only_filtered_mcp_permissions(self):
        instance = adapter(dict(read=True, write=True, bash=True, network=True),
                           include_tools=["band_no_reply"], exclude_tools=["band_remove_participant"])
        requests = []

        def respond(request):
            requests.append(request)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/session/synthetic-session/prompt_async")
            return httpx.Response(204)

        client = HttpOpencodeClient(base_url="http://127.0.0.1:1", directory=instance.config.directory,
                                    transport=httpx.MockTransport(respond))
        instance._client = client
        instance._ensure_client_started = AsyncMock()  # No MCP server or event socket.
        instance._ensure_session = AsyncMock(return_value=("synthetic-session", False))

        async def finish(room_state, room_id, turn):
            turn.turn_future.set_result(None)
            turn.turn_release_future.set_result(None)

        instance._watch_turn_completion = finish
        tools = SimpleNamespace(send_failure=AsyncMock())
        message = PlatformMessage("synthetic-message", ROOM, "Synthetic transport check.", "synthetic-user",
                                  "user", "Synthetic", "message", {}, datetime.now(timezone.utc))
        try:
            # Real maintained on_message -> real HttpOpencodeClient -> MockTransport.
            await instance.on_message(message, tools, SimpleNamespace(replay_messages=[]), None, None,
                                      is_session_bootstrap=False, room_id=ROOM)
        finally:
            await client.close()
        tools.send_failure.assert_not_awaited()
        self.assertEqual(len(requests), 1)
        body = json.loads(requests[0].content)
        self.assertEqual(body["agent"], "factory")
        self.assertEqual(body["model"], {"providerID": "synthetic", "modelID": "synthetic"})
        self.assertEqual(body["tools"], instance._mcp_tool_visibility())
        self.assertTrue(body["tools"][f"{instance._mcp_server_name}_band_no_reply"])
        self.assertFalse(body["tools"][f"{instance.config.mcp_server_name}_*"])
        self.assertFalse(body["tools"][f"{instance._mcp_server_name}_*"])
        self.assertNotIn(f"{instance._mcp_server_name}_band_remove_participant", body["tools"])
        self.assertTrue(all(key.startswith(instance.config.mcp_server_name + "_") for key in body["tools"]))
        self.assertTrue({"*", "read", "edit", "write", "bash", "external_directory", "webfetch", "websearch"}.isdisjoint(body["tools"]))

    async def test_empty_tool_selection_never_overrides_native_policy(self):
        for enabled in (False, True):
            instance = adapter(dict(read=enabled, write=enabled, bash=enabled, network=enabled), include_tools=[])
            visibility = instance._mcp_tool_visibility()
            self.assertEqual(visibility, {f"{instance.config.mcp_server_name}_*": False,
                                          f"{instance._mcp_server_name}_*": False})
            self.assertEqual(instance._own_tool_names, set())
            self.assertIsNone(instance._client)
            self.assertIsNone(instance._mcp_backend)


if __name__ == "__main__":
    unittest.main()
