"""Command-construction tests only; no process or live permission evidence."""
from pathlib import Path
import runpy
import unittest


BUILD = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/permission_probe.py"))["build_command"]


class PermissionProbeTests(unittest.TestCase):
    def test_current_cli_default_preserves_narrow_profile_and_managed_policy(self):
        factory = Path("/workspace with ' quotes/factory")
        scratch = Path("/workspace with ' quotes/runs/disposable")
        command = BUILD(factory, scratch, factory / "scripts/permission_probe.py", "/python with spaces")
        self.assertEqual(command, [str(factory / "scripts/codex-local"), "sandbox", "--permission-profile", ":workspace", "--include-managed-config", "--cd", str(scratch), "--", "/python with spaces", str(factory / "scripts/permission_probe.py"), "--child", str(scratch)])
        self.assertNotIn("macos", command)
        self.assertFalse(any("network" in value or "danger-full-access" in value or "sandbox_mode" in value for value in command))

    def test_named_profile_overrides_are_literal_separate_arguments(self):
        override = 'permissions.probe={extends=":workspace",filesystem={":workspace_roots"={".git"="write"}}}'
        command = BUILD(Path("/factory"), Path("/runs/scratch"), Path("/probe.py"), "/python", "probe", [override, "features.network_proxy=true"])
        self.assertEqual(command[command.index("--permission-profile") + 1], "probe")
        self.assertEqual(command[command.index("-c"):command.index("--")], ["-c", override, "-c", "features.network_proxy=true"])
        self.assertIn("--include-managed-config", command)


if __name__ == "__main__":
    unittest.main()
