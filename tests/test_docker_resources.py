"""Mocked Docker CLI capacity/endpoint checks; no daemon or application runs."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from factorykit.common import FactoryError
from factorykit.validation import docker_resource_check, docker_resource_requirements, doctor


class DockerResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="docker resource ' path ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"paths": {"challenge": str(self.root)}, "runtime": {
            "approval_policy": "never", "sandbox": "workspace-write", "allow_network": False,
            "permission_profile": {"name": "resource-test", "domains": ["localhost"],
                                   "unix_sockets": ["/tmp/factory docker.sock"]},
            "docker_host": "unix:///tmp/factory docker.sock",
            "docker_resources": {"min_cpus": 2, "min_memory_mib": 3072}}}

    def response(self, **values):
        info = {"ServerVersion": "29.test", "NCPU": 4, "MemTotal": 4180443136}
        info.update(values)
        return {"exit_code": 0, "stdout": json.dumps(info), "stderr": ""}

    def test_one_gib_fails_corrected_four_gib_vm_passes(self):
        with patch("factorykit.validation.run_command", side_effect=[self.response(MemTotal=1024 ** 3), self.response()]):
            failed = docker_resource_check(self.config)
            passed = docker_resource_check(self.config)
        self.assertEqual(failed["status"], "FAIL")
        self.assertTrue(any("memory" in value for value in failed["errors"]))
        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(passed["observed"]["MemTotal"], 4180443136)
        self.assertIn("not free memory", passed["scope"])
        self.config["runtime"]["docker_resources"]["min_memory_mib"] = 4096
        with patch("factorykit.validation.run_command", return_value=self.response()):
            self.assertEqual(docker_resource_check(self.config)["status"], "FAIL")

    def test_cpu_and_memory_thresholds_are_independent_and_inclusive(self):
        for cpus, memory, status in [(1, 4 * 1024 ** 3, "FAIL"), (2, 3072 * 1024 ** 2, "PASS"),
                                     (2, 3072 * 1024 ** 2 - 1, "FAIL")]:
            with self.subTest(cpus=cpus, memory=memory), patch("factorykit.validation.run_command", return_value=self.response(NCPU=cpus, MemTotal=memory)):
                self.assertEqual(docker_resource_check(self.config)["status"], status)

    def test_explicit_endpoint_wins_over_environment_and_does_not_mutate_it(self):
        before = copy.deepcopy(self.config)
        with patch.dict(os.environ, {"DOCKER_HOST": "unix:///tmp/other.sock", "DOCKER_CONTEXT": "other"}), patch(
                "factorykit.validation.run_command", return_value=self.response()) as run:
            report = docker_resource_check(self.config)
            self.assertEqual(os.environ["DOCKER_CONTEXT"], "other")
            self.assertEqual(os.environ["DOCKER_HOST"], "unix:///tmp/other.sock")
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ["docker", "--host", "unix:///tmp/factory docker.sock", "info"])
        self.assertEqual(run.call_args.kwargs["env"]["DOCKER_HOST"], "unix:///tmp/factory docker.sock")
        self.assertEqual(run.call_args.kwargs["env"]["DOCKER_CONTEXT"], "")
        self.assertEqual(run.call_args.kwargs["timeout"], 15)
        self.assertNotIn("{{json .}}", argv)
        self.assertNotIn("env", report)
        self.assertEqual(report["endpoint"], self.config["runtime"]["docker_host"])
        self.assertEqual(self.config, before)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_without_explicit_endpoint_retains_cli_context_selection(self):
        self.config["runtime"].pop("docker_host")
        with patch.dict(os.environ, {"DOCKER_CONTEXT": "selected"}), patch("factorykit.validation.run_command", return_value=self.response()) as run:
            report = docker_resource_check(self.config)
        self.assertEqual(run.call_args.args[0][:2], ["docker", "info"])
        self.assertEqual(run.call_args.kwargs["env"]["DOCKER_CONTEXT"], "selected")
        self.assertIn("no configured docker_host", report["endpoint"])

    def test_invalid_explicit_endpoint_never_falls_back_or_probes(self):
        for host in (None, "", "tcp://unapproved:2375", "unix:///tmp/unapproved.sock"):
            with self.subTest(host=host), patch("factorykit.validation.run_command") as run:
                self.config["runtime"]["docker_host"] = host
                self.assertEqual(docker_resource_check(self.config)["status"], "FAIL")
                run.assert_not_called()

    def test_missing_malformed_or_unknown_resource_configuration_fails_closed(self):
        for limits in (None, {}, {"min_cpus": 2}, {"min_cpus": 2, "min_memory_mib": 3072, "typo": 1},
                       *({"min_cpus": value, "min_memory_mib": 3072} for value in (True, 0, -1, 2.0, "2", float("nan"))),
                       *({"min_cpus": 2, "min_memory_mib": value} for value in (False, 0, -1, "3072", float("inf")))):
            with self.subTest(limits=limits), patch("factorykit.validation.run_command") as run:
                self.config["runtime"]["docker_resources"] = limits
                with self.assertRaises(FactoryError):
                    docker_resource_requirements(self.config["runtime"])
                self.assertEqual(docker_resource_check(self.config)["status"], "FAIL")
                run.assert_not_called()
        self.config["runtime"].pop("docker_resources")
        self.assertEqual(docker_resource_check(self.config)["status"], "FAIL")

    def test_missing_or_malformed_daemon_fields_never_pass(self):
        invalid = ["29.4.0", "{broken", "null", "[]", "{}"]
        base = json.loads(self.response()["stdout"])
        for key in ("ServerVersion", "NCPU", "MemTotal"):
            missing = dict(base)
            missing.pop(key)
            invalid.append(json.dumps(missing))
            for value in (None, True, 0, -1, 1.5, ""):
                invalid.append(json.dumps(dict(base, **{key: value})))
        for output in invalid:
            with self.subTest(output=output), patch("factorykit.validation.run_command", return_value={"exit_code": 0, "stdout": output, "stderr": ""}):
                self.assertEqual(docker_resource_check(self.config)["status"], "FAIL")

    def test_unavailable_timeout_and_nonzero_results_retain_failure(self):
        for code in (1, 124, 126, 127):
            with self.subTest(code=code), patch("factorykit.validation.run_command", return_value={**self.response(), "exit_code": code}):
                report = docker_resource_check(self.config)
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["command"]["exit_code"], code)
        for error, code in [(FileNotFoundError(), 127), (subprocess.TimeoutExpired("docker", 15), 124)]:
            with self.subTest(error=type(error).__name__), patch("factorykit.common.subprocess.run", side_effect=error):
                report = docker_resource_check(self.config)
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["command"]["exit_code"], code)

    def test_doctor_uses_one_resource_aware_daemon_query(self):
        self.config.update(budgets={}, seats=[])
        self.config["paths"].update(factory=str(self.root), runs=str(self.root))
        self.config["runtime"].update(codex_command="/fixture/codex", harness_python="/fixture/python", browser_path=str(self.root))
        def fake(argv, *args, **kwargs):
            return self.response(MemTotal=1024 ** 3) if "info" in argv else {"exit_code": 0, "stdout": "fixture", "stderr": ""}
        with patch("factorykit.validation.run_command", side_effect=fake) as run:
            report = doctor(self.config)
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["docker_daemon"]["status"], "FAIL")
        self.assertEqual(report["status"], "FAIL")
        calls = [call for call in run.call_args_list if "info" in call.args[0]]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0][1:3], ["--host", self.config["runtime"]["docker_host"]])


if __name__ == "__main__":
    unittest.main()
