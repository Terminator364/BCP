from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    expected_token = "ci-test-token"
    status_code = 202

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        if self.path != "/v1/system/nexus/retry-auth":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        auth = self.headers.get("Authorization") or ""
        if auth != "Bearer " + self.expected_token or payload.get("confirm") is not True:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"unauthorized"}')
            return
        if self.status_code >= 400:
            self.send_response(self.status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"simulated_failure"}')
            return
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true,"result":"LAUNCHED","bundle_version":"0.2.6"}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", type=int, default=202)
    ns = ap.parse_args()
    Handler.status_code = ns.status
    server = ReuseHTTPServer(("127.0.0.1", 8765), Handler)
    print("MOCK_NEXUS_RETRY_SERVER_READY", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
