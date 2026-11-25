#!/usr/bin/env python3
"""Minimal OTLP/HTTP JSON receiver: stores what the agents export, verbatim."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import runlog


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("content-length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        if self.path == "/control/load":
            runlog.set_run(self.headers["x-run-id"])
        else:
            try:
                body = json.loads(raw)
            except ValueError:
                body = {"_undecoded_bytes": len(raw), "content_type": self.headers.get("content-type")}
            runlog.log("otel", {"path": self.path, "body": body})
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", "2")
        self.end_headers()
        self.wfile.write(b"{}")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 4318), Handler).serve_forever()
