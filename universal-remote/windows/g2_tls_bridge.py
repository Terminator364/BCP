"""BCP Universal Remote G2 - authenticated TLS transport, safe read-only pilot.
Preserves original BCP USB Rescue bridge and pairing key; no command execution.
Wi-Fi LAN / Tailscale adapter IP only. All requests except /health require HMAC.
"""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(os.environ["LOCALAPPDATA"]) / "BCP-Universal-Remote"
LEGACY = Path(os.environ["LOCALAPPDATA"]) / "BCP-USB-Rescue"
sys.path.insert(0, str(LEGACY / "windows"))
from bridge_agent import Bridge, handler_factory  # noqa: E402

PORT = 8898
OPENSSL = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")

class ReadOnlyBridge(Bridge):
    """Reuse the existing HMAC + anti-replay + audit ledger."""
    def operate(self, action, payload):
        if action not in {"status", "diagnostics", "audit"}:
            raise ValueError("G2_READ_ONLY_UNTIL_AUTHENTICATED_APP_QA")
        return super().operate(action, payload)

def permitted(address: str) -> str:
    ip = ipaddress.ip_address(address)
    if ip.version != 4:
        raise ValueError("IPv4 only")
    if ip.is_loopback or ip in ipaddress.ip_network("192.168.0.0/16") or \
       ip in ipaddress.ip_network("10.0.0.0/8") or \
       ip in ipaddress.ip_network("172.16.0.0/12") or \
       ip in ipaddress.ip_network("100.64.0.0/10"):
        return str(ip)
    raise ValueError("Public network binding forbidden")

def certificate(bindings):
    state = ROOT / "private-state"
    state.mkdir(parents=True, exist_ok=True)
    cert, key = state / "g2-server.crt", state / "g2-server.key"
    if not cert.is_file() or not key.is_file():
        if cert.exists() or key.exists():
            raise RuntimeError("Partial certificate state: no silent key rotation")
        if not OPENSSL.exists():
            raise FileNotFoundError("Trusted OpenSSL binary missing")
        args = [str(OPENSSL), "req", "-x509", "-newkey", "rsa:3072",
                "-sha256", "-nodes", "-days", "365",
                "-subj", "/CN=BCP Universal MBMPC",
                "-addext", "subjectAltName=DNS:mbmpc," + ",".join("IP:" + ip for ip in bindings),
                "-keyout", str(key), "-out", str(cert)]
        subprocess.run(args, check=True, capture_output=True, timeout=45)
        # Restrict private-key file to the current Windows user.
        username = os.environ.get("USERNAME", "")
        if username:
            subprocess.run(["icacls", str(key), "/inheritance:r",
                            "/grant:r", username + ":F"],
                           check=True, capture_output=True, timeout=12)
    fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text("ascii"))).hexdigest()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert), str(key))
    return ctx, fingerprint

def friendly_handler_factory(bridge):
    """A GET is only a public health probe; all protected actions remain POST + HMAC."""
    base = handler_factory(bridge)
    class FriendlyHandler(base):
        def do_GET(self):
            # Accept Android browser-added paths, translation and cache-busting queries.
            # Never permit a GET to call a protected agent action.
            from urllib.parse import urlsplit
            from datetime import datetime, timezone
            import json
            request_path = urlsplit(self.path).path[:120]
            if request_path == "/download/BCP-Universal-G2.apk":
                # Signed APK only; never expose an arbitrary filesystem path.
                expected_host = "mbmpc.taild48ba2.ts.net"
                if self.client_address[0] not in ("127.0.0.1", "::1") or \
                   self.headers.get("Host", "").split(":")[0].lower() != expected_host:
                    return self.response(404, {"ok": False, "reason": "NOT_FOUND"})
                import hashlib
                apk = ROOT / "G2-build" / "BCP-Universal-G2-v0.5.0-SIGNED.apk"
                manifest = ROOT / "G2-build" / "G2_SIGNED_RELEASE_REPORT.json"
                try:
                    meta = json.loads(manifest.read_text("utf-8-sig"))
                    length = apk.stat().st_size
                    if not (meta.get("certificate_matches_R33") is True and
                            meta.get("version_code") == 7 and
                            meta.get("package") == "com.blessing.rescuebridge" and
                            25000 < length < 35000000):
                        raise ValueError("APK_NOT_VERIFIED")
                    sha = hashlib.sha256()
                    with apk.open("rb") as stream:
                        for chunk in iter(lambda:stream.read(65536), b""):
                            sha.update(chunk)
                    if sha.hexdigest().lower() != meta.get("sha256", "").lower():
                        raise ValueError("APK_HASH_MISMATCH")
                except (OSError, ValueError, KeyError, TypeError):
                    return self.response(503, {"ok": False, "reason": "SIGNED_APK_NOT_READY"})
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Disposition", 'attachment; filename="BCP-Universal-G2-v0.5.0.apk"')
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                try:
                    with apk.open("rb") as stream:
                        for chunk in iter(lambda:stream.read(65536), b""):
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            try:
                log_path = ROOT / "state" / "g2-browser-requests.jsonl"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                if log_path.exists() and log_path.stat().st_size > 65536:
                    log_path.replace(log_path.with_suffix(".old"))
                with log_path.open("a", encoding="utf8") as f:
                    f.write(json.dumps({"utc":datetime.now(timezone.utc).isoformat(),
                        "request_path":request_path}, ensure_ascii=False) + "\n")
            except OSError:
                pass
            return self.response(200, {"ok":True, "service":"BCP-UNIVERSAL-REMOTE",
                "stage":"G2-LAN-TAILSCALE", "marker":"G2_ROUTE_FIX_20261030_1609",
                "client_app_connected":False})
    return FriendlyHandler

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bind", action="append", default=[])
    p.add_argument("--port", type=int, default=PORT)
    args = p.parse_args()
    if not 1024 <= args.port <= 65535: p.error("Port out of range")
    binds = list(dict.fromkeys(permitted(x) for x in (args.bind or ["127.0.0.1"])))
    ctx, fingerprint = certificate(binds)
    bridge = ReadOnlyBridge(LEGACY / "private-state", LEGACY / "workspace")
    servers = []
    for ip in binds:
        server = ThreadingHTTPServer((ip, args.port), friendly_handler_factory(bridge))
        server.daemon_threads = True
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        servers.append(server)
    print("G2_TLS_READY=true", flush=True)
    print("G2_SHA256_FINGERPRINT=" + fingerprint, flush=True)
    print("G2_BINDINGS=" + ",".join(f"{ip}:{args.port}" for ip in binds), flush=True)
    print("G2_CAPABILITIES=AUTHENTICATED_STATUS_DIAGNOSTICS_AUDIT_ONLY", flush=True)
    try:
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
        for t in threads: t.start()
        for t in threads: t.join()
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers: s.shutdown(); s.server_close()

if __name__ == "__main__":
    main()
