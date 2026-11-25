#!/usr/bin/env python3
"""Local-only sink standing in for an attacker's server (paste.lab.test:80).

It lives on the lab's internal Docker network and has no route anywhere else.
Its log is the reference record of what left the workstation: a real
investigator would never have this file.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import runlog


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _handle(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        if self.path == "/control/load":
            runlog.set_run(self.headers["x-run-id"])
        elif self.path != "/control/health":
            runlog.log("sink", {"method": self.command, "path": self.path, "client": self.client_address[0],
                                "user_agent": self.headers.get("user-agent"), "bytes": len(raw),
                                "body": raw.decode("latin-1")[:8192]})
        body = b"ok\n"
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = _handle


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
