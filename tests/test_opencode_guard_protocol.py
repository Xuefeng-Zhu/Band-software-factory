"""Opt-in real OpenCode/BAND/guard protocol test with a fake provider only.

Set FACTORY_TEST_OPENCODE_COMMAND, FACTORY_TEST_OPENCODE_VERSION and
FACTORY_TEST_OPENCODE_SHA256 to an installed, approved executable. The real
child receives only a loopback guard token. Every upstream provider byte is
handled by httpx.MockTransport; no provider credentials or BAND client exist.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from factorykit import harnesses
from factorykit import featherless_guard as fg

ROOM = "00000000-0000-4000-8000-000000000001"
AGENT = "00000000-0000-4000-8000-000000000002"
MARKER = "factory-guard-native-tool-ok"


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield b"data: " + (chunk.encode() if isinstance(chunk, str) else json.dumps(chunk).encode()) + b"\n\n"


class Sink:
    def __init__(self):
        self.agent_id, self.room_id = AGENT, ROOM
        self.events, self.replies, self.failed = [], [], False

    async def send_event(self, content, message_type, metadata=None):
        self.events.append((content, message_type, metadata or {}))
        self.failed |= message_type == "error"

    async def send_message(self, content, mentions=None):
        self.replies.append(content)

    async def send_failure(self, failure):
        self.failed = True

    async def get_participants(self):
        return []

    async def execute_tool_call_structured(self, *args, **kwargs):
        raise AssertionError("Synthetic compatibility check cannot call BAND")


@unittest.skipUnless(os.environ.get("FACTORY_TEST_OPENCODE_COMMAND"), "opt-in pinned local OpenCode executable required")
class RealOpenCodeGuardProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        previous = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, previous)

    async def test_native_tool_round_trip_with_reasoning_and_exact_guard_accounting(self):
        from band.core.types import AgentInput, HistoryProvider, PlatformMessage
        command = os.environ["FACTORY_TEST_OPENCODE_COMMAND"]
        version = os.environ["FACTORY_TEST_OPENCODE_VERSION"]
        binary_hash = os.environ["FACTORY_TEST_OPENCODE_SHA256"]
        self.assertTrue(Path(command).is_absolute())
        with tempfile.TemporaryDirectory(prefix="factory-guard-protocol-") as temporary:
            root = Path(temporary).resolve()
            runs = root / "runs"
            runs.mkdir()
            models = {name: {"id": name, "status": "active", "tool_use": True,
                            "available_on_current_plan": True, "is_gated": False,
                            "effective_context_length": 32768, "effective_max_completion_tokens": 1024,
                            "pricing": {"prompt": "0.000001", "completion": "0.000002", "image": "0", "request": "0"}}
                      for name in fg.MODEL_IDS}
            metadata = runs / "metadata.json"
            metadata.write_text(json.dumps({"status": "PASS", "blockers": [], "api_origin": fg.API_ORIGIN,
                "billing_attestation_verified_by_caller": True, "plan": {"id": "synthetic-offline-test"},
                "credits": {"currency": "usd", "balance_nano_usd": 25_000_000_000,
                            "reserved_nano_usd": 0, "available_nano_usd": 25_000_000_000}, "models": models}))
            ledger_path = runs / "runtime/guard.json"
            model = "featherless/" + fg.MODEL_IDS[0]
            config = {"runtime": {"harness": "opencode", "model": model,
                "opencode_command": command, "opencode_version": version, "opencode_sha256": binary_hash,
                "opencode_state_root": str(runs / "opencode"), "sandbox": "native-policy",
                "native_permissions": {"read": True, "write": False, "bash": True, "network": False},
                "opencode_provider": {"id": "featherless", "npm": "@ai-sdk/openai-compatible",
                    "base_url": "https://api.featherless.ai/v1", "api_key_env": "FACTORY_TEST_SYNTHETIC_KEY",
                    "models": {name: {"limit": {"context": 32768, "output": 1024}} for name in models}},
                "featherless_budget_guard": {"ledger": str(ledger_path), "model_metadata": str(metadata),
                    "model_metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
                    "approved_credit_nano_usd": 25_000_000_000, "max_total_tokens": 2_000_000,
                    "overall_timeout_seconds": 21600, "request_timeout_seconds": 30}},
                "paths": {"runs": str(runs), "rehearsal": str(root), "result": str(root)},
                "budgets": {"billing_mode": "spend_cap", "spend_cap_usd": 25, "max_total_tokens": 2_000_000,
                            "overall_timeout_seconds": 21600, "turn_timeout_seconds": 45},
                "seats": [{"id": "probe", "agent_id": AGENT, "harness": "OpenCode", "model": model,
                           "reasoning_effort": None, "git_name": "Protocol Probe", "git_email": "probe@factory.invalid"}]}
            requests, admission_shapes = [], []
            request_validator = fg._request

            def capture_admission(body, approved):
                admission_shapes.append({"keys": sorted(body), "message_keys": [sorted(message) for message in body.get("messages", [])]})
                return request_validator(body, approved)

            def upstream(request):
                self.assertEqual(str(request.url), "https://api.featherless.ai/v1/chat/completions")
                body = json.loads(request.content)
                requests.append(body)
                saved = json.loads(ledger_path.read_text())
                self.assertTrue(any(record["status"] == "in_flight" for record in saved["requests"].values()))
                self.assertEqual(body["model"], fg.MODEL_IDS[0])
                self.assertEqual(body["max_tokens"], 1024)
                self.assertTrue(body["stream_options"]["include_usage"])
                tool_results = [item for item in body["messages"] if item.get("role") == "tool"]
                if not tool_results:
                    names = [item.get("function", {}).get("name") for item in body.get("tools", [])]
                    if "bash" in names:
                        delta = {"role": "assistant", "reasoning_content": "Synthetic reasoning; no model executed.",
                                 "tool_calls": [{"index": 0, "id": "call_protocol_probe", "type": "function",
                                     "function": {"name": "bash", "arguments": json.dumps({"command": "printf " + MARKER,
                                                                                          "description": "Print a fixed synthetic marker"})}}]}
                        finish = "tool_calls"
                    else:
                        # OpenCode's title helper is a separate guarded call.
                        delta, finish = {"role": "assistant", "content": "Synthetic protocol check"}, "stop"
                else:
                    self.assertTrue(any(MARKER in json.dumps(item.get("content")) for item in tool_results))
                    delta, finish = {"role": "assistant", "content": "Synthetic tool round trip completed."}, "stop"
                chunks = [{"id": "chatcmpl-protocol", "object": "chat.completion.chunk", "created": 1,
                           "model": fg.MODEL_IDS[0], "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                          {"id": "chatcmpl-protocol", "object": "chat.completion.chunk", "created": 1,
                           "model": fg.MODEL_IDS[0], "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                           "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}, "[DONE]"]
                return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=Stream(chunks))

            actual_guard = fg.FeatherlessGuard

            def guarded(**kwargs):
                return actual_guard(**kwargs, transport=httpx.MockTransport(upstream))

            environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
                           "FACTORY_TEST_SYNTHETIC_KEY": "synthetic-no-provider-access", "LANG": "en_US.UTF-8"}
            sink = Sink()
            with patch.dict(os.environ, environment, clear=True), patch.object(fg, "FeatherlessGuard", guarded), \
                 patch.object(fg, "_request", capture_admission):
                async with asyncio.timeout(60):
                    async with harnesses.start_runtime(config, "rehearsal", config["seats"]) as live:
                        seat = config["seats"][0]
                        adapter_config = harnesses.alternate_adapter_config(live, seat, "rehearsal", root, "Synthetic fixed-marker tool check.", {})
                        adapter = harnesses.adapter_class(live)(config=adapter_config, **harnesses.adapter_options(live))
                        try:
                            await adapter.on_started("Factory protocol test", "Local synthetic protocol test")
                            message = PlatformMessage(id="protocol-test", room_id=ROOM, content="Run the fixed synthetic tool check.",
                                sender_id="synthetic-human", sender_type="user", sender_name="Synthetic test",
                                message_type="message", metadata={}, created_at=datetime.now(timezone.utc))
                            await adapter.on_event(AgentInput(message, sink, HistoryProvider([]), None, None, True, ROOM))
                        finally:
                            await adapter.on_cleanup(ROOM)
            self.assertFalse(sink.failed, f"Synthetic request serialization failed; shapes={admission_shapes}")
            self.assertTrue(sink.replies)
            native = [(json.loads(content), kind) for content, kind, _ in sink.events if kind in ("tool_call", "tool_result")]
            calls = [value for value, kind in native if kind == "tool_call"]
            results = [value for value, kind in native if kind == "tool_result"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["name"], "bash")
            self.assertEqual(calls[0]["args"]["command"], "printf " + MARKER)
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0]["is_error"])
            self.assertIn(MARKER, str(results[0]["output"]))
            self.assertTrue(any(any(message.get("role") == "tool" for message in body["messages"]) for body in requests))
            self.assertTrue(any(any(isinstance(message.get("reasoning_content"), str)
                                    and message.get("tool_calls") for message in body["messages"]) for body in requests))
            saved = json.loads(ledger_path.read_text())
            self.assertEqual(len(saved["requests"]), len(requests))
            self.assertIsNone(saved["stopped_reason"])
            self.assertTrue(all(record["status"] == "settled" and record["prompt_tokens"] == 100
                                and record["completion_tokens"] == 20 for record in saved["requests"].values()))
