"""Profile construction tests; these do not assert host or seat readiness."""
import tomllib
import unittest

from factorykit.permissions import profile_arguments
from factorykit.common import FactoryError
from factorykit.validation import runtime_permission_arguments


def settings(arguments):
    return tomllib.loads("\n".join(arguments[1::2]))


class PermissionProfileTests(unittest.TestCase):
    def test_runtime_rejects_malformed_unknown_and_conflicting_fields(self):
        base = {"sandbox": "workspace-write", "allow_network": False, "approval_policy": "never"}
        profile = {"name": "factory-seat", "domains": ["pypi.org"]}
        self.assertEqual(runtime_permission_arguments(base), [])
        self.assertEqual(runtime_permission_arguments(dict(base, permission_profile=profile)), profile_arguments(**profile))
        for bad_profile in (None, "factory-seat", {}, dict(profile, network=True), dict(profile, domains=["*"])):
            with self.subTest(profile=bad_profile), self.assertRaises(FactoryError):
                runtime_permission_arguments(dict(base, permission_profile=bad_profile))
        for overrides in ({"sandbox": "danger-full-access"}, {"allow_network": True}, {"allow_network": "false"}, {"approval_policy": "on-request"}):
            with self.subTest(overrides=overrides), self.assertRaises(FactoryError):
                runtime_permission_arguments(dict(base, permission_profile=profile, **overrides))

    def test_profile_is_deterministic_exact_allowlist_without_legacy_override(self):
        actual = profile_arguments("factory-seat", ["pypi.org", "LOCALHOST", "127.0.0.1", "pypi.org"], allow_local_binding=True)
        self.assertEqual(actual, profile_arguments("factory-seat", ["127.0.0.1", "localhost", "pypi.org"], allow_local_binding=True))
        config = settings(actual)
        self.assertEqual(config["default_permissions"], "factory-seat")
        self.assertEqual(config["approval_policy"], "never")
        self.assertTrue(config["features"]["network_proxy"])
        self.assertEqual(config["permissions"]["factory-seat"], {
            "extends": ":workspace",
            "filesystem": {":workspace_roots": {".git": "write"}},
            "network": {"enabled": True, "allow_local_binding": True, "domains": {"127.0.0.1": "allow", "localhost": "allow", "pypi.org": "allow"}},
        })
        self.assertNotIn("sandbox_mode", config)

    def test_local_binding_and_sockets_require_explicit_input(self):
        network = settings(profile_arguments("factory-seat", ["pypi.org"]))["permissions"]["factory-seat"]["network"]
        self.assertFalse(network["allow_local_binding"])
        self.assertNotIn("unix_sockets", network)
        socket = "/tmp/factory 'quoted'/docker.sock"
        network = settings(profile_arguments("factory-seat", ["pypi.org"], unix_sockets=[socket]))["permissions"]["factory-seat"]["network"]
        self.assertEqual(network["unix_sockets"], {socket: "allow"})
        with self.assertRaises(ValueError):
            profile_arguments("factory-seat", ["pypi.org"], allow_local_binding=True)

    def test_rejects_broad_or_ambiguous_inputs(self):
        for name in (":full-access", "Factory", "a.b", "a\nother"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                profile_arguments(name, ["pypi.org"])
        for domains in ([], "pypi.org", ["*"], ["*.example.com"], ["https://pypi.org"], ["pypi.org:443"], ["pypi.org/path"], ["a@pypi.org"], ["a\nb"]):
            with self.subTest(domains=domains), self.assertRaises(ValueError):
                profile_arguments("factory-seat", domains)
        for path in ("docker.sock", "/tmp/*", "/tmp/../docker.sock", "/tmp//docker.sock", "/tmp/bad\nname"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                profile_arguments("factory-seat", ["pypi.org"], unix_sockets=[path])


if __name__ == "__main__":
    unittest.main()
