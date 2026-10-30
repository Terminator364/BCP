"""BCP G4 owner inventory over real G2 TLS/HMAC, sandbox-only synthetic profile."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
sys.path.insert(0,str(ROOT/"build-repo"/"universal-remote"/"windows"))
import g2_tls_bridge as g2
import g4_agent as g4
import g4_owner_gateway as gateway
import g4_owner_trust as trust

checks={}
def ok(label,value):
    checks[label]=bool(value)
    if not value:raise AssertionError(label)

pairing=(g2.LEGACY/"private-state/pairing-key.txt").read_text("utf8").strip().encode()
ctx=ssl.create_default_context(cafile=str(ROOT/"private-state/g2-server.crt"))
old_load=gateway.load_policy
old_id=gateway.identity_from_existing_pairing
root_sample=ROOT/"G4-Staging-Workspace"
root_sample.mkdir(exist_ok=True)

with tempfile.TemporaryDirectory(prefix="owner-tls-sandbox-",dir=str(root_sample)) as sandbox:
    base=Path(sandbox)
    target=base/"sample.txt"
    target.write_text("owner-read-over-tls",encoding="utf8")
    profiles=trust.OwnerTrust(base/"trust",secrets.token_bytes(32))
    device=hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    gateway.load_policy=lambda:profiles
    gateway.identity_from_existing_pairing=lambda:device
    bridge=g2.ReadOnlyBridge(g2.LEGACY/"private-state",g2.LEGACY/"workspace")
    server=ThreadingHTTPServer(("127.0.0.1",0),
             g2.friendly_handler_factory(bridge,lambda:g4.G4Bridge()))
    server.daemon_threads=True
    secure=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    secure.minimum_version=ssl.TLSVersion.TLSv1_2
    secure.load_cert_chain(str(ROOT/"private-state/g2-server.crt"),
                           str(ROOT/"private-state/g2-server.key"))
    server.socket=secure.wrap_socket(server.socket,server_side=True)
    loop=threading.Thread(target=server.serve_forever,daemon=True)
    loop.start()
    def query(path,payload,valid=True):
        body=json.dumps(payload,separators=(",",":")).encode()
        nonce=secrets.token_hex(16)
        ts=str(int(time.time()))
        msg=f"POST\n{path}\n{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()
        mac=hmac.new(pairing,msg,hashlib.sha256).hexdigest() if valid else "0"*64
        req=Request(f"https://127.0.0.1:{server.server_port}{path}",
            data=body,method="POST",headers={
             "X-Bridge-Nonce":nonce,"X-Bridge-Time":ts,"X-Bridge-Signature":mac,
             "Content-Type":"application/json"})
        try:
            with urlopen(req,timeout=10,context=ctx) as res:
                code=res.status; raw=res.read();hdr=res.headers
        except HTTPError as err:
            code=err.code;raw=err.read();hdr=err.headers
        expected=hmac.new(pairing,
            f"{nonce}\n{code}\n{hashlib.sha256(raw).hexdigest()}".encode(),
            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,hdr.get("X-Bridge-Signature","")):
            raise AssertionError("SERVER_HMAC_REPLY_MISSING")
        return code,json.loads(raw.decode("utf8"))
    try:
        rootpath="/v1/g4/universal/inventory"
        statuspath="/v1/g4/owner/status"
        code,r=query(statuspath,{})
        ok("unenrolled_status_denied_to_owner",code==200 and
           r["result"]["trusted"] is False)
        code,r=query(rootpath,{"action":"system.volumes","args":{}})
        ok("no_read_before_local_consent",code==400)
        code,r=query(rootpath,{"action":"system.volumes","args":{}},False)
        ok("invalid_hmac_rejected",code==401)
        code,r=query("/v1/g4/owner/activate",{"profile":"operator"})
        ok("no_remote_owner_activation_route",code==404)
        profiles.enroll_local(device,"operator",confirm_local=True)
        code,r=query(statuspath,{})
        ok("synthetic_owner_status",code==200 and
           r["result"]["trusted"] is True)
        code,r=query(rootpath,{"action":"system.volumes","args":{}})
        ok("inventory_drives_over_tls",code==200 and
            len(r["result"]["data"]["drives"])>=1)
        code,r=query(rootpath,{"action":"files.list",
                         "args":{"path":str(base),"page_size":10}})
        ok("owner_directory_over_tls",code==200 and
           any(v["name"]=="sample.txt" for v in r["result"]["data"]["items"]))
        code,r=query(rootpath,{"action":"files.read_chunk",
                          "args":{"path":str(target),"offset":0}})
        ok("owner_file_over_tls",code==200 and
           base64.b64decode(r["result"]["data"]["data_base64"])==
           b"owner-read-over-tls")
        code,r=query(rootpath,{"action":"files.read_chunk",
             "args":{"path":str(ROOT/"private-state"/"g2-server.key")}})
        ok("credential_exfiltration_blocked",code==400)
        code,r=query(rootpath,{"action":"commands.start",
                                 "args":{"cmd":"whoami"}})
        ok("network_owner_read_route_not_shell",code==400)
        code,r=query("/v1/status",{})
        ok("original_g2_preserved",code==200 and r.get("ok") is True)
        profiles.revoke_local(device,confirm_local=True)
        code,r=query(rootpath,{"action":"files.stat",
                                    "args":{"path":str(target)}})
        ok("revocation_immediate",code==400)
    finally:
        server.shutdown();server.server_close()
        loop.join(timeout=5)
        gateway.load_policy=old_load
        gateway.identity_from_existing_pairing=old_id
print(json.dumps({"schema":"BCP_G4_OWNER_TLS_HMAC_STAGING_V1",
                  "checks":checks,"passed":sum(checks.values()),
                  "PASS":all(checks.values()),
                  "real_owner_profile_created":False,
                  "listen_scope":"loopback ephemeral; not production"},indent=2))
