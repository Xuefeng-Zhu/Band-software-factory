"""One process owns one shared, memory-only counter."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class CounterServer(ThreadingHTTPServer):
    request_queue_size = 128

    def __init__(self, address):
        self.value = 0
        self.lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def read_object(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0:
            raise ValueError("Negative content length")
        body = self.rfile.read(length)
        payload = json.loads(body) if body else {}
        if not isinstance(payload, dict):
            raise ValueError("Expected an object")
        return payload

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ok"})
        elif self.path == "/counter":
            with self.server.lock:
                value = self.server.value
            self.respond(200, {"value": value})
        else:
            self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in ("/counter/increment", "/_test/reset"):
            self.respond(404, {"error": "Not found"})
            return
        try:
            payload = self.read_object()
            if self.path == "/_test/reset":
                value = payload.get("value")
                if type(value) is not int or not 0 <= value <= 1_000_000:
                    raise ValueError("Invalid reset value")
        except (ValueError, UnicodeDecodeError):
            self.respond(400, {"error": "Invalid request body"})
            return
        if self.path == "/_test/reset":
            with self.server.lock:
                self.server.value = value
            self.respond(204)
        else:
            with self.server.lock:
                self.server.value += 1
                value = self.server.value
            self.respond(200, {"value": value})


if __name__ == "__main__":
    with CounterServer(("0.0.0.0", int(os.environ.get("PORT", "8080")))) as server:
        server.serve_forever()
