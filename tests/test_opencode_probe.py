"""Probe safety and schema drift checks; no server, BAND or provider calls."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from factorykit.common import FactoryError
from factorykit.opencode_probe import (PROBE_ENV, live_request_guard, main, request_contract,
                                      synthetic_credentials, validate_schema)


class NoInferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sdk_prompt_is_rejected_before_transport(self):
        from band.integrations.opencode.client import HttpOpencodeClient
        requests, transported = [], []
        def respond(request):
            transported.append(request)
            return httpx.Response(200, json={})
        client = HttpOpencodeClient(base_url="http://127.0.0.1:1234", transport=httpx.MockTransport(respond))
        client._client.event_hooks["request"] = [live_request_guard(requests)]
        try:
            with self.assertRaisesRegex(FactoryError, "allowlist"):
                await client.prompt_async("ses_probe", parts=[{"type": "text", "text": "must not send"}])
            self.assertEqual(transported, [])
            self.assertEqual(requests, [])
            await client.create_session(title="Empty session")
            await client.get_session("ses_probe")
            await client.abort_session("ses_probe")
            await client.health()
            self.assertEqual(len(transported), 4)
        finally:
            await client.close()

    async def test_remote_hosts_shell_and_other_mutations_are_rejected(self):
        guard = live_request_guard([])
        for method, url in (("GET", "https://provider.invalid/global/health"),
                            ("POST", "http://127.0.0.1/session/ses_probe/shell"),
                            ("POST", "http://127.0.0.1/session/ses_probe/message"),
                            ("POST", "http://127.0.0.1/api/session/ses_probe/prompt"),
                            ("POST", "http://127.0.0.1/global/upgrade")):
            with self.subTest(url=url), self.assertRaisesRegex(FactoryError, "allowlist"):
                await guard(httpx.Request(method, url))


class SchemaAndOutputTests(unittest.TestCase):
    def test_sdk_permission_route_removal_and_enum_drift_fail(self):
        doc = {"paths": {"/session/{sessionID}/permissions/{permissionID}": {"post": {
            "requestBody": {"content": {"application/json": {"schema": {"type": "object",
                "properties": {"response": {"enum": ["reject"]}}, "required": ["response"]}}}}}}}}
        request = httpx.Request("POST", "http://127.0.0.1/session/ses_probe/permissions/per_probe", json={"response": "reject"})
        self.assertEqual(request_contract(doc, request)["path"], "/session/{sessionID}/permissions/{permissionID}")
        changed = copy.deepcopy(doc)
        changed["paths"]["/session/{sessionID}/permissions/{permissionID}"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["response"]["enum"] = ["deny"]
        with self.assertRaisesRegex(FactoryError, "body schema"):
            request_contract(changed, request)
        with self.assertRaisesRegex(FactoryError, "missing POST route"):
            request_contract({"paths": {}}, request)

    def test_external_schema_reference_is_never_fetched(self):
        with self.assertRaisesRegex(FactoryError, "external schema reference"):
            validate_schema({}, {"$ref": "https://provider.invalid/schema"}, {}, "fixture")

    def test_synthetic_environment_restores_prior_value(self):
        with patch.dict(os.environ, {PROBE_ENV: "prior-synthetic-value"}):
            with synthetic_credentials():
                self.assertEqual(os.environ[PROBE_ENV], "synthetic-no-provider-access")
            self.assertEqual(os.environ[PROBE_ENV], "prior-synthetic-value")

    def test_existing_evidence_is_not_overwritten_or_probed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.json"
            output.write_text("original")
            with patch("factorykit.opencode_probe.probe") as probe:
                with self.assertRaisesRegex(FactoryError, "new output path"):
                    main(["--command", "/tools/opencode", "--version", "1.18.34", "--sha256", "a" * 64,
                          "--output", str(output)])
                probe.assert_not_called()
            self.assertEqual(output.read_text(), "original")
