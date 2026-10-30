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
from g4_agent import G4Bridge  # isolated G4 capabilities, user authorization for writes
G4_READ={
    "/v1/g4/capabilities":"capabilities",
    "/v1/g4/system":"system",
    "/v1/g4/processes":"processes",
    "/v1/g4/files/list":"list",
    "/v1/g4/files/read":"read",
    "/v1/g4/audit":"audit",
    "/v1/g4/owner/status":"owner_status",
    "/v1/g4/universal/inventory":"owner_inventory",
    "/v1/g4/device/enroll/request":"device_enroll_request",
}
G4_APPROVED={
    "/v1/g4/changes/prepare":"prepare",
    "/v1/g4/changes/status":"ticket_status",
    "/v1/g4/changes/commit":"commit",
    "/v1/g4/session/use":"session_use",
    "/v1/g4/session/status":"session_status",
    "/v1/g4/session/revoke":"session_revoke",
}
G4_ENDPOINTS={**G4_READ,**G4_APPROVED}

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

pairing_lock = threading.Lock()
update_audit_lock = threading.Lock()
g4_init_lock = threading.Lock()
g4_instance = None

def get_g4():
    # Must ONLY be called after HMAC authentication and replay validation.
    global g4_instance
    if g4_instance is None:
        with g4_init_lock:
            if g4_instance is None:
                g4_instance = G4Bridge()
    return g4_instance

def g4_background_warmup():
    # Keep G2 serving status/updates/pairing while Windows ACL initialization
    # is slow on a 4 GB RAM machine. Never authorize any operation here.
    from datetime import datetime, timezone
    import json
    try:
        get_g4()
        status="READY"
    except Exception:
        status="FAILED"
    try:
        file=ROOT/"state"/"g4-startup-state.json"
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps({
            "utc":datetime.now(timezone.utc).isoformat(),
            "status":status,
            "capability":"G4_AGENT_INITIALIZATION_ONLY",
            "owner_profile_mutated":False
        }),encoding="utf8")
    except OSError:
        pass

def friendly_handler_factory(bridge,g4_provider=None):
    """Authenticated G2 with G4 read-only; no remote mutations without local approval."""
    base = handler_factory(bridge)
    class FriendlyHandler(base):
        def do_POST(self):
            from urllib.parse import urlsplit
            path=urlsplit(self.path).path
            if path in G4_ENDPOINTS and g4_provider is not None:
                import json
                nonce=self.headers.get("X-Bridge-Nonce","")
                try:
                    size=int(self.headers.get("Content-Length","-1"))
                    limit=80*1024 if path=="/v1/g4/changes/prepare" else 8192
                    if not (1<=size<=limit):
                        return self.response(413,{"ok":False,"reason":"G4_BODY_TOO_LARGE"},nonce)
                    body=self.rfile.read(size)
                    auth_error=bridge.authenticate("POST",path,
                        self.headers.get("X-Bridge-Time"),nonce,
                        self.headers.get("X-Bridge-Signature",""),body)
                    if auth_error:
                        bridge.record("g4_"+G4_ENDPOINTS[path],"DENIED",nonce[:80])
                        return self.response(401,{"ok":False,"reason":"UNAUTHORIZED"},nonce)
                    payload=json.loads(body.decode("utf8"))
                    if path=="/v1/g4/device/enroll/request":
                        # Legacy G2 authentication permits only an UNTRUSTED
                        # pending proposal; local Windows approval is mandatory.
                        from g4_device_identity import DeviceRegistry
                        registry=DeviceRegistry(ROOT/"private-state"/"g4"/"device-registry")
                        value=registry.request_enrollment(
                            payload.get("device_id"),payload.get("device_secret"),
                            payload.get("label"))
                    elif path=="/v1/g4/universal/inventory":
                        # A shared G2 key is never sufficient for owner access.
                        from g4_device_identity import DeviceRegistry,IdentityError
                        from g4_owner_gateway import inventory_query
                        registry=DeviceRegistry(ROOT/"private-state"/"g4"/"device-registry")
                        try:
                            device=registry.verify_request(
                                self.headers.get("X-BCP-Device",""),
                                "POST",path,
                                self.headers.get("X-BCP-Device-Time",""),
                                self.headers.get("X-BCP-Device-Nonce",""),
                                body,self.headers.get("X-BCP-Device-Signature",""))
                        except IdentityError:
                            return self.response(401,{"ok":False,
                                "reason":"INDIVIDUAL_DEVICE_AUTH_REQUIRED"},nonce)
                        value=inventory_query(payload,device_id=device)
                    elif path=="/v1/g4/owner/status":
                        from g4_owner_gateway import public_status
                        value=public_status()
                    else:
                        value=g4_provider().operate(G4_ENDPOINTS[path],payload)
                    if path=="/v1/g4/capabilities":
                        value={**value,"phase":"G4_PRODUCTION_LOCAL_WINDOWS_APPROVAL"}
                    bridge.record("g4_"+G4_ENDPOINTS[path],"SUCCESS",nonce)
                    return self.response(200,{"ok":True,"result":value},nonce)
                except (OSError,ValueError,UnicodeError,TypeError) as exc:
                    bridge.record("g4_"+G4_ENDPOINTS[path],"REJECTED",nonce[:80])
                    return self.response(400,{"ok":False,
                        "reason":str(exc)[:100] if isinstance(exc,ValueError)
                        else type(exc).__name__},nonce)
            if path=="/v1/phone-state":
                # Authenticated, privacy-minimal phone heartbeat; not a command channel.
                from datetime import datetime,timezone
                import json
                nonce=self.headers.get("X-Bridge-Nonce","")
                try:
                    n=int(self.headers.get("Content-Length","-1"))
                    if not (1<=n<=1024):raise ValueError("INVALID_LENGTH")
                    body=self.rfile.read(n)
                    auth_error=bridge.authenticate("POST",path,
                        self.headers.get("X-Bridge-Time"),nonce,
                        self.headers.get("X-Bridge-Signature",""),body)
                    if auth_error:
                        return self.response(401,{"ok":False,"reason":"UNAUTHORIZED"},nonce)
                    data=json.loads(body.decode("utf8"))
                    version=data.get("version_code")
                    connection=data.get("network")
                    update_state=data.get("update_state")
                    if (not isinstance(version,int) or isinstance(version,bool) or
                        not 1<=version<=100000 or
                        connection not in ("wifi","cellular","other","offline") or
                        update_state not in ("current","checking","pending","error","unknown")):
                        raise ValueError("INVALID_PHONE_STATE")
                    record={"utc":datetime.now(timezone.utc).isoformat(),
                            "version_code":version,"network":connection,
                            "update_state":update_state,
                            "app_visible":True}
                    where=ROOT/"state"/"g2-phone-status.json"
                    where.parent.mkdir(parents=True,exist_ok=True)
                    part=where.with_suffix(".part")
                    part.write_text(json.dumps(record,separators=(",",":")),encoding="utf8")
                    part.replace(where)
                    return self.response(200,{"ok":True,"received":True},nonce)
                except (OSError,ValueError,UnicodeDecodeError,TypeError,json.JSONDecodeError):
                    return self.response(400,{"ok":False,"reason":"INVALID_PHONE_STATE"},nonce)
            if path!="/pair/v1":
                return super().do_POST()
            # Trusted Tailscale Serve HTTPS reverse proxy; never expose on LAN HTTP.
            if (self.client_address[0] not in ("127.0.0.1", "::1") or
                self.headers.get("Host","").split(":")[0].lower()!="mbmpc.taild48ba2.ts.net"):
                return self.response(404, {"ok":False, "reason":"NOT_FOUND"})
            import json, hmac, hashlib, re
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not (1<=size<=256):raise ValueError("BAD_SIZE")
                request=json.loads(self.rfile.read(size))
                code=request.get("code","")
                if not isinstance(code,str) or not re.fullmatch(r"[0-9]{8}",code):
                    raise ValueError("BAD_PIN")
            except (ValueError,TypeError,UnicodeDecodeError,json.JSONDecodeError):
                return self.response(400,{"ok":False,"reason":"INVALID_REQUEST"})
            invite=ROOT/"private-state"/"pair-code.json"
            try:
                with pairing_lock:
                    state=json.loads(invite.read_text("utf8"))
                    import time
                    if state.get("used") or int(state.get("expires",0))<int(time.time()) or                        int(state.get("attempts",0))>=5:
                        return self.response(403,{"ok":False,"reason":"PAIRING_CODE_REJECTED"})
                    salt=bytes.fromhex(state["salt"])
                    expected=bytes.fromhex(state["digest"])
                    actual=hashlib.pbkdf2_hmac("sha256",code.encode(),salt,120000)
                    if not hmac.compare_digest(expected,actual):
                        state["attempts"]=int(state.get("attempts",0))+1
                        invite.write_text(json.dumps(state,separators=(",",":")),encoding="utf8")
                        return self.response(403,{"ok":False,"reason":"PAIRING_CODE_REJECTED"})
                    key=(LEGACY/"private-state"/"pairing-key.txt").read_text("utf8").strip()
                    if not re.fullmatch(r"[0-9a-fA-F]{64}",key):
                        raise ValueError("KEY_MISSING")
                    state["used"]=True
                    invite.write_text(json.dumps(state,separators=(",",":")),encoding="utf8")
                # Return key only over TLS with explicit no-store. Never log the key.
                data=json.dumps({"ok":True,"key":key},separators=(",",":")).encode("utf8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Cache-Control","no-store")
                self.send_header("Pragma","no-cache")
                self.send_header("X-Content-Type-Options","nosniff")
                self.send_header("Content-Length",str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (OSError,ValueError,KeyError,TypeError):
                return self.response(403,{"ok":False,"reason":"PAIRING_CODE_REJECTED"})

        def do_GET(self):
            # Accept Android browser-added paths, translation and cache-busting queries.
            # Never permit a GET to call a protected agent action.
            from urllib.parse import urlsplit
            from datetime import datetime, timezone
            import json
            request_path = urlsplit(self.path).path[:120]
            if request_path=="/updates/mode.json":
                # Four hours from latest local code edit/commit or stable release.
                # No manual toggle and no personal file contents disclosed.
                import time
                now=time.time()
                repo=ROOT/"build-repo"
                candidate_files=[
                    ROOT/"updates"/"stable.json",
                    repo/".git"/"refs"/"heads"/"feat"/"universal-remote-transport-20261030",
                    repo/"universal-remote"/"android-project"/"android"/"app"/"src"/"main"/"java"/"com"/"blessing"/"rescuebridge"/"MainActivity.java",
                    repo/"universal-remote"/"android-project"/"android"/"app"/"src"/"main"/"java"/"com"/"blessing"/"rescuebridge"/"BCPAutoUpdater.java"]
                last=max([x.stat().st_mtime for x in candidate_files if x.exists()] or [0])
                until=int(last)+4*3600
                dev=now<until
                result={"schema":"BCP_UPDATE_MODE_V1",
                        "mode":"development" if dev else "normal",
                        "poll_seconds":30 if dev else 900,
                        "active_until_epoch":until if dev else 0,
                        "foreground_only_fast":True}
                body=json.dumps(result,separators=(",",":")).encode("utf8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Content-Length",str(len(body)))
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Content-Type-Options","nosniff")
                self.end_headers()
                self.wfile.write(body)
                return
            if request_path in ("/updates/stable.json", "/updates/stable.apk"):
                # Private tailnet only. Recalculate SHA before each served APK.
                expected_host="mbmpc.taild48ba2.ts.net"
                if (self.client_address[0] not in ("127.0.0.1","::1") or
                    self.headers.get("Host","").split(":")[0].lower()!=expected_host):
                    return self.response(404, {"ok":False,"reason":"NOT_FOUND"})
                try:
                    # Counters for field diagnostics only; no IP, user agent,
                    # identifier, secret, URL query or request body retained.
                    event = {"utc":datetime.now(timezone.utc).isoformat(),
                             "path":request_path,
                             "client_kind":"android" if
                                "Dalvik" in self.headers.get("User-Agent","") else "other"}
                    audit=ROOT/"state"/"g2-update-checks.jsonl"
                    audit.parent.mkdir(parents=True,exist_ok=True)
                    with update_audit_lock:
                        if audit.exists() and audit.stat().st_size>65536:
                            audit.replace(audit.with_suffix(".old"))
                        with audit.open("a",encoding="utf8") as a:
                            a.write(json.dumps(event,separators=(",",":"))+"\n")
                except OSError:
                    pass
                try:
                    release = json.loads((ROOT/"updates"/"stable.json").read_text("utf-8"))
                    if (release.get("package")!="com.blessing.rescuebridge" or
                        release.get("channel")!="stable" or
                        not isinstance(release.get("versionCode"),int) or
                        release["versionCode"]<8 or
                        release.get("url")!="https://mbmpc.taild48ba2.ts.net/updates/stable.apk" or
                        not isinstance(release.get("size"),int) or
                        not (20000<release["size"]<30000000) or
                        not isinstance(release.get("sha256"),str) or
                        len(release["sha256"])!=64):
                        raise ValueError("Invalid release manifest")
                    apk=ROOT/"updates"/"stable.apk"
                    if apk.stat().st_size!=release["size"]:
                        raise ValueError("Update size mismatch")
                    import hashlib
                    h=hashlib.sha256()
                    with apk.open("rb") as stream:
                        for chunk in iter(lambda:stream.read(65536),b""):
                            h.update(chunk)
                    if h.hexdigest().lower()!=release["sha256"].lower():
                        raise ValueError("Update digest mismatch")
                except (OSError,ValueError,TypeError,KeyError):
                    return self.response(503, {"ok":False,"reason":"UPDATE_NOT_PUBLISHED"})
                if request_path=="/updates/stable.json":
                    # Only current verified release metadata; not stale cached data.
                    body=json.dumps(release,separators=(",",":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type","application/json; charset=utf-8")
                    self.send_header("Content-Length",str(len(body)))
                    self.send_header("Cache-Control","no-store")
                    self.send_header("X-Content-Type-Options","nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(200)
                self.send_header("Content-Type","application/vnd.android.package-archive")
                self.send_header("Content-Length",str(apk.stat().st_size))
                self.send_header("Cache-Control","no-store")
                self.send_header("X-Content-Type-Options","nosniff")
                self.end_headers()
                try:
                    with apk.open("rb") as stream:
                        for chunk in iter(lambda:stream.read(65536),b""):
                            self.wfile.write(chunk)
                except (BrokenPipeError,ConnectionResetError):
                    pass
                return
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
    # Prepare G4 asynchronously: preserve existing G2 on slow startup.
    # The warmup does not create an owner trust profile or execute actions.
    threading.Thread(target=g4_background_warmup,daemon=True,
                     name="BCP-G4-Warmup").start()
    servers = []
    for ip in binds:
        server = ThreadingHTTPServer((ip, args.port), friendly_handler_factory(bridge,get_g4))
        server.daemon_threads = True
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        servers.append(server)
    print("G2_TLS_READY=true", flush=True)
    print("G2_SHA256_FINGERPRINT=" + fingerprint, flush=True)
    print("G2_BINDINGS=" + ",".join(f"{ip}:{args.port}" for ip in binds), flush=True)
    print("G2_CAPABILITIES=G4_AUTHENTICATED_READ_AND_LOCAL_WINDOWS_APPROVED_CHANGES", flush=True)
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
