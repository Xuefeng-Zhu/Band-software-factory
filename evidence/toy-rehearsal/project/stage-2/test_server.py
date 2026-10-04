"""Real HTTP checks against fresh server subprocesses; no third-party packages."""

import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest


class CounterHTTPTests(unittest.TestCase):
    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def start(self, port=None):
        self.port = port or 8080
        env = os.environ.copy()
        env.pop("PORT", None)
        if port is not None:
            env["PORT"] = str(port)
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("server.py"))],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.stop, process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.assertIsNone(process.poll(), "Service exited during startup")
            try:
                if self.request("GET", "/health")[0] == 200:
                    return
            except OSError:
                time.sleep(0.02)
        self.fail("Service did not become healthy")

    @staticmethod
    def stop(process):
        process.terminate()
        process.wait(timeout=5)

    def assert_json(self, method, path, expected, body=None):
        status, headers, data = self.request(method, path, body)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(int(headers["Content-Length"]), len(data))
        self.assertEqual(json.loads(data), expected)
        return headers

    def test_page_and_local_assets(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.start(port)
        for path, content_type, expected in (
            ("/", "text/html", b'data-testid="counter-value"'),
            ("/app.js", "text/javascript", b"AbortController"),
            ("/style.css", "text/css", b"focus-visible"),
        ):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertTrue(headers["Content-Type"].startswith(content_type))
            self.assertIn(expected, body)
        self.assertEqual(self.request("GET", "/../server.py")[0], 404)
        self.assert_json("GET", "/counter", {"value": 0})

    def test_default_port_and_startup(self):
        self.start()
        self.assert_json("GET", "/health", {"status": "ok"})
        self.assert_json("GET", "/counter", {"value": 0})

    def test_custom_port_shared_state_repeated_resets_and_bad_bodies(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.start(port)
        self.assert_json("GET", "/counter", {"value": 0})
        for seed in (7, 0, 1_000_000, 37, 0):
            status, headers, body = self.request("POST", "/_test/reset", json.dumps({"value": seed}))
            self.assertEqual((status, body, headers["Content-Length"]), (204, b"", "0"))
            headers = self.assert_json("GET", "/counter", {"value": seed})
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assert_json("POST", "/counter/increment", {"value": seed + 1})
            self.assert_json("POST", "/counter/increment", {"value": seed + 2}, "{}")
            self.assert_json("GET", "/counter", {"value": seed + 2})
        for malformed in ("{", "[]", "null"):
            self.assertEqual(self.request("POST", "/counter/increment", malformed)[0], 400)
            self.assert_json("GET", "/counter", {"value": 2})
        self.assert_json("POST", "/counter/increment", {"value": 3}, "{}")


if __name__ == "__main__":
    unittest.main()
