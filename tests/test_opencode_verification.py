"""OpenCode binary, route and private-state gates; no network or paid inference."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from factorykit import harnesses as h
from factorykit.common import FactoryError


def fixture(root):
    provider = {"id": "featherless", "npm": "@ai-sdk/openai-compatible",
                "base_url": "https://api.featherless.ai/v1", "api_key_env": "FACTORY_TEST_PROVIDER_TOKEN",
                "models": {"org/glm-a": {"limit": {"context": 131072, "output": 32768}},
                           "org/glm-b": {"limit": {"context": 262144, "output": 65536}}}}
    model = "featherless/org/glm-a"
    return {"runtime": {"harness": "opencode", "opencode_command": str(root / "opencode"),
                        "opencode_version": "1.18.34", "opencode_state_root": str(root / "runs/opencode"),
                        "opencode_provider": provider, "model": model, "sandbox": "native-policy",
                        "native_permissions": {"read": True, "write": True, "bash": False, "network": False}},
            "paths": {"runs": str(root / "runs"), "rehearsal": str(root), "result": str(root)},
            "budgets": {"billing_mode": "spend_cap", "turn_timeout_seconds": 600},
            "seats": [{"id": "pm", "harness": "OpenCode", "model": model, "reasoning_effort": None,
                       "git_name": "Factory PM", "git_email": "pm@factory.invalid"}]}


def responses(config, model=None):
    model = model or config["runtime"]["model"]
    provider_id, model_id = model.split("/", 1)
    permissions = h.opencode_permissions(config["runtime"]["native_permissions"])
    pin = config["runtime"]["opencode_provider"]
    effective = {"model": model, "small_model": model, "default_agent": "factory", "share": "disabled",
                 "enabled_providers": [provider_id], "permission": permissions,
                 "agent": {"factory": {"model": model, "permission": permissions}},
                 "provider": {provider_id: {"npm": pin["npm"], "options": {"baseURL": pin["base_url"],
                              "apiKey": "synthetic-credential-must-never-be-reported"}, "models": deepcopy(pin["models"])}}}
    agents = [{"name": "factory", "model": {"providerID": provider_id, "modelID": model_id}}]
    catalog = {"connected": [provider_id], "all": [{"id": provider_id, "options": {"baseURL": pin["base_url"]},
                "models": {upstream: {"id": upstream, "providerID": provider_id,
                           "api": {"id": upstream, "npm": pin["npm"], "url": ""},
                           "limit": deepcopy(metadata["limit"])} for upstream, metadata in pin["models"].items()}}]}
    return permissions, effective, agents, catalog


class OpenCodePinTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = fixture(self.root)

    def test_explicit_provider_requires_exact_models_and_positive_limits(self):
        self.assertEqual(h.validate_selection(self.config), [])
        mutations = [lambda c: c["runtime"]["opencode_provider"]["models"]["org/glm-a"]["limit"].update(context=0),
                     lambda c: c["runtime"]["opencode_provider"]["models"]["org/glm-a"].update(id="redirected"),
                     lambda c: c["runtime"]["opencode_provider"].update(base_url="https://user:secret@example.test/v1"),
                     lambda c: c["runtime"]["opencode_provider"]["models"]["org/glm-a"].update(options={"apiKey": "bad"}),
                     lambda c: c["seats"][0].update(model="other/org/glm-a"),
                     lambda c: c["seats"][0].update(model="featherless/unlisted"),
                     lambda c: c["runtime"].update(opencode_sha256="not-a-hash"),
                     lambda c: c["runtime"].update(opencode_version="latest")]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                config = deepcopy(self.config)
                mutate(config)
                self.assertTrue(h.validate_selection(config))

    def test_private_seat_state_persists_and_discovery_stays_separate(self):
        first = h._opencode_state(self.config, "judged-pm")
        marker = first["data"] / "session-marker"
        marker.write_text("preserved")
        self.assertEqual(h._opencode_state(self.config, "judged-pm"), first)
        self.assertEqual(marker.read_text(), "preserved")
        second = h._opencode_state(self.config, "judged-backend")
        rehearsal = h._opencode_state(self.config, "rehearsal-pm")
        discovery = h._opencode_state(self.config, None)
        next_discovery = h._opencode_state(self.config, None)
        for other in (second, rehearsal, discovery, next_discovery):
            self.assertNotEqual(other, first)
        self.assertNotEqual(discovery, next_discovery)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o700 for path in first.values()))

    def test_private_state_refuses_path_escape_symlinks_and_public_permissions(self):
        self.config["runtime"]["opencode_state_root"] = str(self.root / "outside")
        self.assertTrue(h.opencode_runtime_errors(self.config))
        self.config = fixture(self.root)
        paths = h._opencode_state(self.config, "judged-pm")
        paths["data"].rmdir()
        paths["data"].symlink_to(self.root)
        with self.assertRaisesRegex(FactoryError, "symlink"):
            h._opencode_state(self.config, "judged-pm")
        paths["data"].unlink()
        paths["cache"].chmod(0o755)
        with self.assertRaisesRegex(FactoryError, "owner-only"):
            h._opencode_state(self.config, "judged-pm")

    def test_isolated_config_contains_placeholder_not_credential_or_ambient_routes(self):
        paths = h._opencode_state(self.config, "judged-pm")
        environment = {"FACTORY_TEST_PROVIDER_TOKEN": "synthetic-provider-secret", "OPENAI_API_KEY": "unrelated-secret",
                       "OPENCODE_CONFIG": "/ambient/config", "OPENCODE_CONFIG_DIR": "/ambient/directory",
                       "OPENCODE_CONFIG_CONTENT": '{"model":"other/fallback"}', "HOME": "/unchanged/home", "PATH": "/tools"}
        with patch.dict(os.environ, environment, clear=True):
            env, permissions = h._opencode_environment(self.config, self.config["runtime"]["native_permissions"],
                                                       "featherless/org/glm-b", {"GIT_AUTHOR_NAME": "Factory PM"}, paths)
        generated = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(generated["model"], "featherless/org/glm-b")
        self.assertEqual(generated["small_model"], generated["model"])
        self.assertEqual(generated["agent"]["factory"]["model"], generated["model"])
        self.assertTrue(all(generated["agent"][name]["model"] == generated["model"] for name in ("title", "summary", "compaction")))
        self.assertEqual(generated["enabled_providers"], ["featherless"])
        self.assertEqual(generated["provider"]["featherless"]["options"]["apiKey"], "{env:FACTORY_TEST_PROVIDER_TOKEN}")
        self.assertEqual(generated["permission"], permissions)
        self.assertEqual(env["HOME"], "/unchanged/home")
        self.assertEqual(env["FACTORY_TEST_PROVIDER_TOKEN"], "synthetic-provider-secret")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "true")
        self.assertEqual(env["OPENCODE_DISABLE_EXTERNAL_SKILLS"], "true")
        self.assertEqual(Path(env["OPENCODE_CONFIG"]).stat().st_mode & 0o777, 0o600)
        self.assertNotIn("synthetic-provider-secret", Path(env["OPENCODE_CONFIG"]).read_text())
        self.assertNotIn("unrelated-secret", env["OPENCODE_CONFIG_CONTENT"])

    def binary(self):
        binary = Path(self.config["runtime"]["opencode_command"])
        binary.write_bytes(b"synthetic executable fixture")
        binary.chmod(0o700)
        self.config["runtime"]["opencode_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        return binary

    def test_binary_and_cli_version_are_verified_without_printing_raw_output(self):
        binary = self.binary()
        result = SimpleNamespace(returncode=0, stdout="1.18.34\n")
        with patch.object(h.subprocess, "run", return_value=result) as command:
            path, proof = h._verified_opencode_command(self.config, {"PATH": "/fixture"})
        self.assertEqual(path, str(binary.resolve()))
        self.assertEqual(proof["executable_sha256"], self.config["runtime"]["opencode_sha256"])
        self.assertEqual(command.call_args.args[0], [path, "--version"])
        result.stdout = "sensitive raw provider details"
        with patch.object(h.subprocess, "run", return_value=result), self.assertRaisesRegex(FactoryError, "CLI version differs") as failure:
            h._verified_opencode_command(self.config, {})
        self.assertNotIn(result.stdout, str(failure.exception))

    def test_changed_executable_is_rejected_before_version_probe(self):
        binary = self.binary()
        binary.write_bytes(b"modified")
        with patch.object(h.subprocess, "run") as command, self.assertRaisesRegex(FactoryError, "SHA-256 differs"):
            h._verified_opencode_command(self.config, {})
        command.assert_not_called()

    def test_update_during_version_probe_is_rejected_before_server_start(self):
        binary = self.binary()
        def replace(*args, **kwargs):
            binary.write_bytes(b"update raced version check")
            return SimpleNamespace(returncode=0, stdout="1.18.34")
        with patch.object(h.subprocess, "run", side_effect=replace), self.assertRaisesRegex(FactoryError, "changed during startup"):
            h._verified_opencode_command(self.config, {})


class OpenCodeResolvedRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = fixture(self.root)

    def client(self, payloads):
        def response(path):
            answer = Mock()
            answer.json.return_value = payloads[path]
            return answer
        return SimpleNamespace(get=AsyncMock(side_effect=response))

    async def test_server_verifies_version_routes_provider_and_limits_without_prompts(self):
        permissions, effective, agents, catalog = responses(self.config)
        client = self.client({"/global/health": {"healthy": True, "version": "1.18.34"},
                              "/config": effective, "/agent": agents, "/provider": catalog})
        proof = await h._verify_server(client, SimpleNamespace(returncode=None), permissions, self.config,
                                       "featherless/org/glm-a")
        self.assertEqual(proof["limits"], {"context": 131072, "output": 32768})
        self.assertEqual([call.args[0] for call in client.get.await_args_list], ["/global/health", "/config", "/agent", "/provider"])
        self.assertNotIn("synthetic-credential", json.dumps(proof))

    async def test_health_server_version_must_equal_cli_pin(self):
        client = self.client({"/global/health": {"healthy": True, "version": "1.18.33"}})
        with self.assertRaisesRegex(FactoryError, "health/version differs"):
            await h._verify_server(client, SimpleNamespace(returncode=None), {}, self.config, self.config["runtime"]["model"])
        client.get.assert_awaited_once_with("/global/health")

    def test_route_and_limit_tampering_fail_closed_without_sensitive_output(self):
        mutations = [lambda e, a, c: e.update(model="featherless/org/glm-b"),
                     lambda e, a, c: e.update(small_model="other/fallback"),
                     lambda e, a, c: e["agent"]["factory"].update(model="other/fallback"),
                     lambda e, a, c: e.update(enabled_providers=["featherless", "other"]),
                     lambda e, a, c: a[0]["model"].update(modelID="org/glm-b"),
                     lambda e, a, c: a.append({"name": "title", "model": {"providerID": "featherless", "modelID": "org/glm-b"}}),
                     lambda e, a, c: c["all"].append({"id": "other", "models": {}}),
                     lambda e, a, c: c.update(connected=[]),
                     lambda e, a, c: e["provider"]["featherless"]["options"].update(baseURL="https://different.invalid/v1"),
                     lambda e, a, c: c["all"][0]["options"].update(baseURL="https://different.invalid/v1"),
                     lambda e, a, c: c["all"][0]["models"]["org/glm-a"]["api"].update(npm="other-package"),
                     lambda e, a, c: c["all"][0]["models"]["org/glm-a"]["api"].update(id="redirected"),
                     lambda e, a, c: c["all"][0]["models"]["org/glm-a"]["api"].update(url="https://different.invalid/v1"),
                     lambda e, a, c: c["all"][0]["models"]["org/glm-a"]["limit"].update(context=0),
                     lambda e, a, c: e["provider"]["featherless"]["models"]["org/glm-a"]["limit"].update(output=1)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                _, effective, agents, catalog = responses(self.config)
                mutate(effective, agents, catalog)
                with self.assertRaises(FactoryError) as failure:
                    h._verify_opencode_routing(self.config, self.config["runtime"]["model"], effective, agents, catalog)
                self.assertNotIn("synthetic-credential", str(failure.exception))

    async def test_seats_use_own_main_small_model_and_stable_private_state_id(self):
        other = deepcopy(self.config["seats"][0])
        other.update(id="backend", model="featherless/org/glm-b", git_name="Factory Backend")
        self.config["seats"].append(other)
        observed = []
        @asynccontextmanager
        async def server(config, workspace, model, policy, env, *, state_id=None, guarded_route=None):
            observed.append((model, state_id, env["GIT_AUTHOR_NAME"]))
            yield {"url": "http://127.0.0.1:1234", "password": "synthetic"}, object()
        catalog = {"harness": "opencode", "models": [{"id": f"featherless/org/glm-{name}", "connected": True,
                    "supportedReasoningEfforts": []} for name in ("a", "b")]}
        with patch.object(h, "_opencode_server", server), patch.object(h, "_opencode_catalog", AsyncMock(return_value=catalog)):
            async with h.start_runtime(self.config, "judged", self.config["seats"]) as selected:
                self.assertEqual(set(selected["runtime"]["_opencode_endpoints"]), {"pm", "backend"})
        self.assertEqual(observed, [("featherless/org/glm-a", "judged-pm", "Factory PM"),
                                    ("featherless/org/glm-b", "judged-backend", "Factory Backend")])

    async def test_missing_credential_stops_before_server_or_state_creation(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(asyncio, "create_subprocess_exec") as spawn:
            with self.assertRaisesRegex(FactoryError, "environment variable is unset"):
                async with h._opencode_server(self.config, self.root, self.config["runtime"]["model"],
                                               self.config["runtime"]["native_permissions"], {}):
                    self.fail("Server unexpectedly started")
        spawn.assert_not_called()
        self.assertFalse(Path(self.config["runtime"]["opencode_state_root"]).exists())


class OpenCodeGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = fixture(self.root)
        self.config["budgets"].update(spend_cap_usd=25, max_total_tokens=2_000_000,
                                     overall_timeout_seconds=21600, turn_timeout_seconds=900)
        runs = self.root / "runs"
        runs.mkdir()
        self.metadata_path = runs / "provider-evidence.json"
        self.evidence = {"status": "PASS", "blockers": [], "api_origin": "https://api.featherless.ai",
                         "billing_attestation_verified_by_caller": True, "plan": {"id": "reviewed-plan"},
                         "credits": {"currency": "usd", "balance_nano_usd": 25_000_000_000,
                                     "reserved_nano_usd": 0, "available_nano_usd": 25_000_000_000}, "models": {}}
        for name, row in self.config["runtime"]["opencode_provider"]["models"].items():
            self.evidence["models"][name] = {"id": name, "status": "active", "tool_use": True,
                 "available_on_current_plan": True, "is_gated": False,
                 "effective_context_length": row["limit"]["context"],
                 "effective_max_completion_tokens": row["limit"]["output"],
                 "pricing": {"prompt": "0.000001", "completion": "0.000002", "image": "0", "request": "0"}}
        self.config["runtime"]["featherless_budget_guard"] = {
            "ledger": str(runs / "runtime/featherless-requests.json"), "model_metadata": str(self.metadata_path),
            "model_metadata_sha256": "", "approved_credit_nano_usd": 25_000_000_000,
            "max_total_tokens": 2_000_000, "overall_timeout_seconds": 21600, "request_timeout_seconds": 900}
        self.save_evidence()
        self.guard = SimpleNamespace(url="http://127.0.0.1:43210/v1", token="synthetic-local-guard-token",
                                     _forward=AsyncMock(),
                                     verification=lambda: {"enforcement": "request_reservations", "request_count": 0})
        self.route = h._OwnedFeatherlessRoute(self.guard)

    def save_evidence(self):
        self.metadata_path.write_text(json.dumps(self.evidence))
        self.config["runtime"]["featherless_budget_guard"]["model_metadata_sha256"] = hashlib.sha256(self.metadata_path.read_bytes()).hexdigest()

    def test_guard_limits_cannot_exceed_approved_budget_or_change_provider(self):
        self.assertEqual(h.opencode_runtime_errors(self.config), [])
        for key in ("approved_credit_nano_usd", "max_total_tokens", "overall_timeout_seconds", "request_timeout_seconds"):
            config = deepcopy(self.config)
            config["runtime"]["featherless_budget_guard"][key] += 1
            self.assertTrue(h.featherless_guard_errors(config), key)
        self.config["runtime"]["opencode_provider"]["base_url"] = "https://other.invalid/v1"
        self.assertTrue(h.featherless_guard_errors(self.config))

    def test_evidence_hash_attestation_inventory_limits_and_credit_fail_closed(self):
        self.assertEqual(h._featherless_metadata(self.config), self.evidence["models"])
        self.metadata_path.write_text("{}")
        with self.assertRaisesRegex(FactoryError, "SHA-256"):
            h._featherless_metadata(self.config)
        original = deepcopy(self.evidence)
        mutations = [lambda e: e.update(status="BLOCKED"), lambda e: e.update(billing_attestation_verified_by_caller=False),
                     lambda e: e["credits"].update(available_nano_usd=1), lambda e: e["models"].pop("org/glm-b"),
                     lambda e: e["models"]["org/glm-a"].update(effective_context_length=1),
                     lambda e: e["models"]["org/glm-a"].update(tool_use=False)]
        for mutate in mutations:
            self.evidence = deepcopy(original)
            mutate(self.evidence)
            self.save_evidence()
            with self.assertRaises(FactoryError):
                h._featherless_metadata(self.config)

    def test_metadata_symlinks_are_rejected_even_with_valid_hash(self):
        original = self.metadata_path.with_name("original.json")
        self.metadata_path.rename(original)
        self.metadata_path.symlink_to(original)
        with self.assertRaisesRegex(FactoryError, "symlink"):
            h._featherless_metadata(self.config)

    def test_only_owned_proxy_route_and_token_reach_child(self):
        policy = self.config["runtime"]["native_permissions"]
        state = h._opencode_state(self.config, "judged-pm")
        real_key = "synthetic-real-provider-key"
        with patch.dict(os.environ, {"FACTORY_TEST_PROVIDER_TOKEN": real_key, "UNUSUAL_ALIAS": real_key}, clear=True):
            environment, _ = h._opencode_environment(self.config, policy, self.config["runtime"]["model"],
                                                     {"FACTORY_TEST_PROVIDER_TOKEN": real_key}, state, guarded_route=self.route)
        self.assertNotIn(real_key, environment.values())
        self.assertNotIn("FACTORY_TEST_PROVIDER_TOKEN", environment)
        generated = json.loads(environment["OPENCODE_CONFIG_CONTENT"])
        options = generated["provider"]["featherless"]["options"]
        self.assertEqual(options, {"baseURL": self.guard.url, "apiKey": "{env:FACTORY_FEATHERLESS_GUARD_TOKEN}"})
        self.assertEqual(environment["FACTORY_FEATHERLESS_GUARD_TOKEN"], self.guard.token)
        self.assertNotIn(real_key, Path(environment["OPENCODE_CONFIG"]).read_text())
        self.assertNotIn(self.guard.token, Path(environment["OPENCODE_CONFIG"]).read_text())
        with self.assertRaisesRegex(FactoryError, "direct routing is forbidden"):
            h._opencode_environment(self.config, policy, self.config["runtime"]["model"], {}, state)

    def test_effective_guard_route_and_credential_are_verified_without_secret_output(self):
        _, effective, agents, catalog = responses(self.config)
        for row in (effective["provider"]["featherless"], catalog["all"][0]):
            row["options"].update(baseURL=self.guard.url, apiKey=self.guard.token)
        proof = h._verify_opencode_routing(self.config, self.config["runtime"]["model"], effective, agents, catalog,
                                           guarded_route=self.route)
        self.assertEqual(proof["base_url"], "https://api.featherless.ai/v1")
        self.assertEqual(proof["request_guard"]["enforcement"], "request_reservations")
        self.assertNotIn(self.guard.token, json.dumps(proof))
        catalog["all"][0]["options"]["apiKey"] = "wrong-key"
        with self.assertRaisesRegex(FactoryError, "credential must belong") as failure:
            h._verify_opencode_routing(self.config, self.config["runtime"]["model"], effective, agents, catalog,
                                       guarded_route=self.route)
        self.assertNotIn("wrong-key", str(failure.exception))
        catalog["all"][0]["options"].update(apiKey=self.guard.token, baseURL="https://api.featherless.ai/v1")
        with self.assertRaisesRegex(FactoryError, "endpoint/package"):
            h._verify_opencode_routing(self.config, self.config["runtime"]["model"], effective, agents, catalog,
                                       guarded_route=self.route)

    async def test_shared_guard_outlives_all_seat_servers_and_discovery_also_uses_it(self):
        sequence, seen_routes, guard_kwargs = [], [], []
        guard = self.guard
        class FakeGuard:
            def __init__(self, **kwargs):
                guard_kwargs.append(kwargs)
            async def __aenter__(self):
                sequence.append("guard-start")
                return guard
            async def __aexit__(self, *args):
                sequence.append("guard-stop")
        @asynccontextmanager
        async def server(config, workspace, model, policy, env, *, state_id=None, guarded_route=None):
            sequence.append("seat-start")
            seen_routes.append(guarded_route)
            try:
                yield {"url": "http://127.0.0.1:1234", "password": "synthetic"}, object()
            finally:
                sequence.append("seat-stop")
        other = deepcopy(self.config["seats"][0])
        other.update(id="backend", model="featherless/org/glm-b")
        self.config["seats"].append(other)
        catalog = {"harness": "opencode", "models": [{"id": f"featherless/org/glm-{name}", "connected": True,
                    "supportedReasoningEfforts": []} for name in ("a", "b")]}
        with patch.dict(sys.modules, {"factorykit.featherless_guard": SimpleNamespace(FeatherlessGuard=FakeGuard, GuardError=RuntimeError)}), \
             patch.dict(os.environ, {"FACTORY_TEST_PROVIDER_TOKEN": "synthetic-real-key"}), \
             patch.object(h, "_opencode_server", server), patch.object(h, "_opencode_catalog", AsyncMock(return_value=catalog)):
            async with h.start_runtime(self.config, "judged", self.config["seats"]):
                self.assertEqual(sequence, ["guard-start", "seat-start", "seat-start"])
            self.assertEqual(sequence, ["guard-start", "seat-start", "seat-start", "seat-stop", "seat-stop", "guard-stop"])
            self.assertIs(seen_routes[0], seen_routes[1])
            self.assertEqual(len(guard_kwargs), 1)
            self.assertEqual(guard_kwargs[0]["api_key"], "synthetic-real-key")
            await h.discover_models(self.config)
            self.assertEqual(sequence[-4:], ["guard-start", "seat-start", "seat-stop", "guard-stop"])
            self.assertEqual(len(guard_kwargs), 2)
            self.assertIsNot(seen_routes[-1], seen_routes[0])

    async def test_stopped_guard_prevents_any_seat_server_start(self):
        guard = self.guard
        guard.verification = lambda: {"stopped_reason": "provider request usage is unknown"}
        class FakeGuard:
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return guard
            async def __aexit__(self, *args):
                pass
        with patch.dict(sys.modules, {"factorykit.featherless_guard": SimpleNamespace(FeatherlessGuard=FakeGuard, GuardError=RuntimeError)}), \
             patch.dict(os.environ, {"FACTORY_TEST_PROVIDER_TOKEN": "synthetic-real-key"}), \
             patch.object(h, "_opencode_server") as server:
            with self.assertRaisesRegex(FactoryError, "persistently stopped"):
                async with h.start_runtime(self.config, "judged", self.config["seats"]):
                    self.fail("Stopped guard unexpectedly started runtime")
        server.assert_not_called()
