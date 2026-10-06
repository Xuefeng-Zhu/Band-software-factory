"""Pinned OpenCode path-pattern policy; no native execution or network."""
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from factorykit import harnesses as h
from factorykit.common import FactoryError
from tests import test_opencode_verification as routing


def decision(rules, value):
    """OpenCode documented '*'/'?' matching, last match wins (not fnmatch [])."""
    if isinstance(rules, str):
        return rules
    result = "deny"
    for pattern, action in rules.items():
        regex = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
        if re.fullmatch(regex, value):
            result = action
    return result


class ReadonlyInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.workspace = self.root / "output"; self.workspace.mkdir()
        (self.workspace / ".git").mkdir()
        self.config = routing.fixture(self.root)
        self.config["paths"].update(factory=str(self.root / "factory"), challenge=str(self.root / "challenge"))
        self.inputs = [self.root / name for name in ("factory/protocols", "factory/mandates", "challenge/toy/spec", "challenge/harness")]
        for root in self.inputs:
            root.mkdir(parents=True); (root / "source.md").write_text("public pinned input")
        self.policy = dict(read=True, write=True, bash=True, network=False)

    def permissions(self):
        return h.opencode_permissions(self.policy, self.workspace, h._opencode_input_roots(self.config))

    def relative(self, path):
        return os.path.relpath(path, h._opencode_worktree(self.workspace)).replace(os.sep, "/")

    def test_sources_readable_native_writes_stay_in_workspace_and_bash_unchanged(self):
        rules = self.permissions()
        for root in self.inputs:
            self.assertEqual(decision(rules["external_directory"], str(root / "*")), "allow")
            self.assertEqual(decision(rules["read"], self.relative(root / "source.md")), "allow")
            self.assertEqual(decision(rules["edit"], self.relative(root / "source.md")), "deny")
        self.assertEqual(decision(rules["edit"], "stage-1/server.py"), "allow")
        self.assertEqual(decision(rules["edit"], "../outside.txt"), "deny")
        self.assertEqual(rules["bash"], "allow")
        self.assertEqual(rules["webfetch"], "deny")

    def test_config_credentials_git_ledgers_and_neighbor_roots_not_granted(self):
        rules = self.permissions()
        for relative in ("factory/config/factory.yaml", "factory/.git/config", "factory/.venv/auth.json",
                         "private/band-agents.yaml", "runs/runtime/budget-session.json", "challenge/.git/config",
                         "factory/protocols-other/private.txt"):
            path = self.root / relative
            self.assertEqual(decision(rules["external_directory"], str(path.parent / "*")), "deny")
            self.assertEqual(decision(rules["read"], self.relative(path)), "deny")
            self.assertEqual(decision(rules["edit"], self.relative(path)), "deny")

    def test_scoped_mandates_allowed_without_attempt_config_or_private_siblings(self):
        parent = self.root / "runs/attempt/mandates"; parent.mkdir(parents=True)
        mandate = parent / "factory-pm.md"; mandate.write_text("generic mandate")
        self.config["seats"][0]["mandate"] = str(mandate)
        rules = self.permissions()
        self.assertEqual(decision(rules["read"], self.relative(mandate)), "allow")
        self.assertEqual(decision(rules["external_directory"], str(parent / "*")), "allow")
        self.assertEqual(decision(rules["external_directory"], str(parent.parent / "*")), "deny")

    def test_symlink_private_file_and_wildcard_input_roots_refused(self):
        target = self.inputs[0] / "escape.md"; target.symlink_to(self.root / "private.txt")
        with self.assertRaises(FactoryError): self.permissions()
        target.unlink(); target = self.inputs[0] / ".env.local"; target.write_text("not a real secret")
        with self.assertRaises(FactoryError): self.permissions()
        target.unlink()
        self.config["paths"]["factory"] = str(self.root / "unsafe*")
        (self.root / "unsafe*/protocols").mkdir(parents=True)
        with self.assertRaises(FactoryError): self.permissions()

    def test_global_non_git_and_nested_git_worktrees_scope_native_edit_patterns(self):
        (self.workspace / ".git").rmdir()
        self.assertEqual(h._opencode_worktree(self.workspace), Path("/"))
        rules = self.permissions()
        self.assertEqual(decision(rules["edit"], self.relative(self.workspace / "app.py")), "allow")
        self.assertEqual(decision(rules["edit"], self.relative(self.root / "private.txt")), "deny")
        (self.root / ".git").mkdir()
        rules = self.permissions()
        self.assertEqual(decision(rules["edit"], "output/app.py"), "allow")
        self.assertEqual(decision(rules["edit"], "factory/protocols/source.md"), "deny")

    def test_disabled_read_and_legacy_no_workspace_behavior_remain(self):
        legacy = h.opencode_permissions(self.policy)
        self.assertEqual(legacy["external_directory"], "deny")
        self.assertEqual(legacy["edit"], "allow")
        self.policy["read"] = False
        rules = self.permissions()
        self.assertEqual(decision(rules["read"], self.relative(self.inputs[0] / "source.md")), "deny")
        self.assertEqual(decision(rules["external_directory"], str(self.inputs[0] / "*")), "deny")

    async def test_generated_and_effective_native_workspace_binding(self):
        environment, rules = h._opencode_environment(self.config, self.policy, self.config["runtime"]["model"], {}, workspace=self.workspace)
        effective = json.loads(environment["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(effective["permission"], rules)
        self.assertEqual(effective["agent"]["factory"]["permission"], rules)
        _, _, agents, catalog = routing.responses(self.config)
        payloads = {"/global/health": {"healthy": True, "version": "1.18.34"}, "/config": effective,
                    "/agent": agents, "/provider": catalog,
                    "/path": {"directory": str(self.workspace), "worktree": str(self.workspace)}}
        def response(path):
            result = Mock(); result.json.return_value = payloads[path]; return result
        client = SimpleNamespace(get=AsyncMock(side_effect=response))
        await h._verify_server(client, SimpleNamespace(returncode=None), rules, self.config,
                               self.config["runtime"]["model"], workspace=self.workspace)
        payloads["/path"]["worktree"] = str(self.root)
        with self.assertRaisesRegex(FactoryError, "native paths differ"):
            await h._verify_server(client, SimpleNamespace(returncode=None), rules, self.config,
                                   self.config["runtime"]["model"], workspace=self.workspace)
