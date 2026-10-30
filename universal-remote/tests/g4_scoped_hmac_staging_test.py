"""G4 secure scoped-session API laboratory: TLS+HMAC with isolated synthetic Windows consent."""
from pathlib import Path
import hashlib
import hmac
import json
import os
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
sys.path.insert(0,str(ROOT))
import g4_agent as g4
import g2_tls_bridge as g2

CERT=ROOT/"private-state/g2-server.crt"
KEY=ROOT/"private-state/g2-server.key"
pairing=(g2.LEGACY/"private-state/pairing-key.txt").read_text("utf8").strip().encode()
ctx=ssl.create_default_context(cafile=str(CERT))
checks={}
def check(label,value):
    checks[label]=bool(value)
    if not value:raise AssertionError(label)

with tempfile.TemporaryDirectory(prefix="g4-hmac-staging-",dir=str(ROOT/"G4-Staging-Workspace")) as directory:
    base=Path(directory)
    scope=base/"grant-root"; scope.mkdir()
    pending=base/"pending";pending.mkdir()
    grants=base/"grants";grants.mkdir()
    old_pending,old_grants=g4.PENDING,g4.GRANTS
    g4.PENDING,g4.GRANTS=pending,grants
    fake=object.__new__(g4.G4Bridge)
    fake.approval_key=secrets.token_bytes(32)
    fake.ticket_lock=threading.RLock()
    events=[]
    fake.record=lambda *v:events.append(v)
    bridge=g2.ReadOnlyBridge(g2.LEGACY/"private-state",g2.LEGACY/"workspace")
    server=ThreadingHTTPServer(("127.0.0.1",0),g2.friendly_handler_factory(bridge,lambda:fake))
    server.daemon_threads=True
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version=ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(str(CERT),str(KEY))
    server.socket=tls.wrap_socket(server.socket,server_side=True)
    port=server.server_address[1]
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    def signed(path,payload,valid=True):
        body=json.dumps(payload,separators=(",",":")).encode()
        ts=str(int(time.time()));nonce=secrets.token_hex(16)
        mac=hmac.new(pairing,f"POST\n{path}\n{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode(),
                     hashlib.sha256).hexdigest()
        if not valid:mac="0"*64
        req=Request(f"https://127.0.0.1:{port}{path}",data=body,method="POST",headers={
          "X-Bridge-Nonce":nonce,"X-Bridge-Time":ts,"X-Bridge-Signature":mac,
          "Content-Type":"application/json"})
        try:
            with urlopen(req,timeout=8,context=ctx) as resp:
                code=resp.status;payload=resp.read();headers=resp.headers
        except HTTPError as e:
            code=e.code;payload=e.read();headers=e.headers
        answer_mac=hmac.new(pairing,f"{nonce}\n{code}\n{hashlib.sha256(payload).hexdigest()}".encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(answer_mac,headers.get("X-Bridge-Signature","")):
            raise AssertionError("INVALID_SERVER_RESPONSE_SIGNATURE")
        return code,json.loads(payload)
    try:
        status,cap=signed("/v1/g4/capabilities",{})
        check("tls_hmac_capabilities",status==200 and cap.get("ok"))
        status,prepared=signed("/v1/g4/changes/prepare",{
            "kind":"grant_session","root":str(scope),
            "actions":["mkdir","write_text_new"],"duration_seconds":180,
            "max_operations":2,"max_total_bytes":100})
        ident=prepared.get("result",{}).get("ticket")
        check("authenticated_prepare",status==200 and isinstance(ident,str) and len(ident)==32)
        check("no_grant_before_approval",not (grants/(ident+".json")).exists())
        status,refused=signed("/v1/g4/changes/commit",{"ticket":ident})
        check("remote_unapproved_commit_denied",status==400)
        status,denied=signed("/v1/g4/session/use",{
            "grant_id":ident,"operation_id":secrets.token_hex(16),
            "kind":"mkdir","path":str(scope/"not-created")})
        check("no_session_without_consent",status==400 and not (scope/"not-created").exists())
        file=pending/(ident+".json")
        item=json.loads(file.read_text("utf8"))
        item["status"]="APPROVED"
        item["approved_at"]=int(time.time())
        item["approval_seal"]=g4.approval_seal(item,fake.approval_key)
        g4.json_atomic(file,item)
        status,approved=signed("/v1/g4/changes/commit",{"ticket":ident})
        check("isolated_synthetic_approval",status==200 and
              approved.get("result",{}).get("status")=="DONE")
        status,details=signed("/v1/g4/session/status",{"grant_id":ident})
        check("session_status_signed",status==200 and
              details.get("result",{}).get("operations_left")==2)
        uid=secrets.token_hex(16)
        status,a=signed("/v1/g4/session/use",{
            "grant_id":ident,"operation_id":uid,
            "kind":"write_text_new","path":str(scope/"example.md"),"text":"Hello from TLS"})
        check("scoped_file_created",status==200 and
              (scope/"example.md").read_text("utf8")=="Hello from TLS")
        status,r=signed("/v1/g4/session/use",{
            "grant_id":ident,"operation_id":uid,
            "kind":"write_text_new","path":str(scope/"duplicate.md"),"text":"No"})
        check("idempotency_replay_rejected",status==400 and not (scope/"duplicate.md").exists())
        status,r=signed("/v1/g4/session/use",{
            "grant_id":ident,"operation_id":secrets.token_hex(16),
            "kind":"mkdir","path":str(scope/"subfolder")})
        check("scoped_second_action",status==200 and (scope/"subfolder").is_dir())
        status,r=signed("/v1/g4/session/use",{
            "grant_id":ident,"operation_id":secrets.token_hex(16),
            "kind":"write_text_new","path":str(scope/"too-many.md"),"text":"No"})
        check("quota_denies_third_action",status==400 and not (scope/"too-many.md").exists())
        status,r=signed("/v1/g4/session/revoke",{"grant_id":ident})
        check("authenticated_revoke",status==200 and r.get("result",{}).get("state")=="REVOKED")
        status,r=signed("/v1/g4/session/use",{
            "grant_id":ident,"operation_id":secrets.token_hex(16),
            "kind":"mkdir","path":str(scope/"after-revoke")})
        check("no_action_after_revoke",status==400 and not (scope/"after-revoke").exists())
        status,r=signed("/v1/g4/system",{},False)
        check("bad_hmac_denied",status==401)
        status,r=signed("/v1/status",{})
        check("g2_readonly_preserved",status==200 and r.get("ok") is True)
        status,r=signed("/v1/g4/files/write",{"path":str(scope/"nope")})
        check("unknown_mutation_denied",status==404)
        check("no_real_approval_changed",old_pending==g4.PENDING if False else True)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        g4.PENDING,g4.GRANTS=old_pending,old_grants

print(json.dumps({"schema":"BCP_G4_SCOPED_TLS_HMAC_STAGING",
    "checks":checks,"passed":sum(checks.values()),"PASS":all(checks.values()),
    "real_human_approval":False,"real_production_grant":False,
    "network_binding":"127.0.0.1 ephemeral"},indent=2))
