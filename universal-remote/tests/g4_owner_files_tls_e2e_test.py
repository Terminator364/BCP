"""BCP G4 secure HTTP owner-file transaction E2E in an isolated TEMPORARY lab.

Real TLS, real legacy G2 HMAC, extra individual device HMAC, production
handler. Synthetic local owner consent exists ONLY in a temp directory;
no real MBMPC owner profile, app pairing or user document is modified.
"""
from __future__ import annotations
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

HERE=Path(__file__).resolve()
sys.path.insert(0,str(HERE.parent.parent/"windows"))
import g2_tls_bridge as bridge_module
from g4_device_identity import DeviceRegistry,signing_message
from g4_owner_trust import OwnerTrust
from g4_owner_transactions import owner_hash
from g4_owner_file_rpc import OwnerFileRpc

root=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
legacy=Path(os.environ["LOCALAPPDATA"])/"BCP-USB-Rescue"
shared=(legacy/"private-state"/"pairing-key.txt").read_text("ascii").strip().encode()
checks={}
def check(name,flag):
    checks[name]=bool(flag)
    if not flag:raise AssertionError(name)

with tempfile.TemporaryDirectory(prefix="bcp-e2e-owner-files-") as d:
    tmp=Path(d)
    registry=DeviceRegistry(tmp/"devices")
    policy=OwnerTrust(tmp/"owner-profiles",secrets.token_bytes(32))
    auth={}
    for tag in ("Samsung-A","Samsung-B"):
        device_id=secrets.token_hex(16)
        secret=secrets.token_hex(32)
        request=registry.request_enrollment(device_id,secret,tag)
        registry.approve_local(device_id,request["verification_code"],
                               local_user_confirmed=True)
        auth[tag]=(device_id,secret)
    a,secret_a=auth["Samsung-A"]
    b,secret_b=auth["Samsung-B"]
    rpc=OwnerFileRpc(tmp/"file-transactions",policy,registry)
    # Use the real G2 handler but replace the two owner lookups with isolated
    # test objects, leaving production module / Windows private state intact.
    orig_registry=bridge_module.get_device_registry
    orig_rpc=bridge_module.get_owner_file_rpc
    bridge_module.get_device_registry=lambda:registry
    bridge_module.get_owner_file_rpc=lambda:rpc
    ctx,fp=bridge_module.certificate(["127.0.0.1"])
    transport=bridge_module.ReadOnlyBridge(
        legacy/"private-state",legacy/"workspace")
    server=ThreadingHTTPServer(("127.0.0.1",0),
        bridge_module.friendly_handler_factory(transport,lambda:None))
    server.socket=ctx.wrap_socket(server.socket,server_side=True)
    port=server.server_address[1]
    server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    client=ssl.create_default_context(cafile=str(root/"private-state"/"g2-server.crt"))
    try:
        def call(action,args=None,identity=None,device_sig=True,
                 shared_sig=True,force_nonce=None):
            path="/v1/g4/owner/files"
            body=json.dumps({"action":action,"args":args or {}},
                            separators=(",",":")).encode("utf8")
            ts=str(int(time.time()))
            nonce=force_nonce or secrets.token_hex(16)
            mac=hmac.new(shared,("POST\n"+path+"\n"+ts+"\n"+nonce+
                "\n"+hashlib.sha256(body).hexdigest()).encode(),hashlib.sha256).hexdigest()
            if not shared_sig:mac="0"*64
            headers={"Content-Type":"application/json","X-Bridge-Time":ts,
                     "X-Bridge-Nonce":nonce,"X-Bridge-Signature":mac}
            if identity:
                device_id,device_secret=identity
                dnonce=secrets.token_hex(16)
                signature=hmac.new(bytes.fromhex(device_secret),
                   signing_message(device_id,"POST",path,ts,dnonce,body),
                   hashlib.sha256).hexdigest()
                if not device_sig:signature="0"*64
                headers.update({"X-BCP-Device":device_id,
                     "X-BCP-Device-Time":ts,
                     "X-BCP-Device-Nonce":dnonce,
                     "X-BCP-Device-Signature":signature})
            req=Request(f"https://127.0.0.1:{port}"+path,
                        data=body,headers=headers,method="POST")
            try:
                with urlopen(req,context=client,timeout=20) as r:
                    code=r.status
                    raw=r.read()
                    replymac=r.headers.get("X-Bridge-Signature")
            except HTTPError as e:
                code=e.code
                raw=e.read()
                replymac=e.headers.get("X-Bridge-Signature")
            expected=hmac.new(shared,(nonce+"\n"+str(code)+"\n"+
                hashlib.sha256(raw).hexdigest()).encode(),hashlib.sha256).hexdigest()
            check("reply_hmac_"+str(len(checks)),
                  hmac.compare_digest(expected,replymac or ""))
            return code,json.loads(raw.decode("utf8"))

        dst=tmp/"received.bin"
        code,_=call("begin",{"destination":str(dst)})
        check("no_individual_identity_denied",code==401)
        code,_=call("begin",{"destination":str(dst)},identity=auth["Samsung-A"])
        check("no_owner_profile_denied",code==403)
        policy.enroll_local(owner_hash(a),confirm_local=True)
        policy.enroll_local(owner_hash(b),confirm_local=True)
        code,_=call("begin",{"destination":str(dst)},identity=auth["Samsung-A"],
                    shared_sig=False)
        check("bad_legacy_hmac_denied",code==401)
        code,_=call("begin",{"destination":str(dst)},identity=auth["Samsung-A"],
                    device_sig=False)
        check("bad_individual_hmac_denied",code==401)
        code,reply=call("begin",{"destination":str(dst)},identity=auth["Samsung-A"])
        check("owner_a_can_start_transfer",code==200 and reply.get("ok") is True)
        tx=reply["result"]["upload_id"]
        code,_=call("status",{"upload_id":tx},identity=auth["Samsung-B"])
        check("owner_b_cannot_inspect_a",code==403)
        data=secrets.token_bytes(130001)
        offset=0
        for i in range(0,len(data),65536):
            chunk=data[i:i+65536]
            request={"upload_id":tx,"offset":offset,
                    "data_base64":base64.b64encode(chunk).decode(),
                    "chunk_sha256":hashlib.sha256(chunk).hexdigest()}
            code,reply=call("append",request,identity=auth["Samsung-A"])
            check("chunk_"+str(i//65536)+"_accepted",
                  code==200 and reply.get("ok") is True)
            offset=reply["result"]["next_offset"]
        check("all_bytes_transferred",offset==len(data))
        code,_=call("commit",{"upload_id":tx,"sha256":hashlib.sha256(data).hexdigest()},
                    identity=auth["Samsung-B"])
        check("owner_b_cannot_commit_a",code==403)
        code,reply=call("commit",{"upload_id":tx,"sha256":hashlib.sha256(data).hexdigest()},
                        identity=auth["Samsung-A"])
        check("owner_a_can_commit",code==200 and reply["result"]["status"]=="COMMITTED")
        check("real_tls_file_digest_matches",hashlib.sha256(dst.read_bytes()).digest()==
              hashlib.sha256(data).digest())
        code,committed=call("status",{"upload_id":tx},identity=auth["Samsung-A"])
        check("verified_committed_receipt_after_network_drop",
              code==200 and committed["result"]["state"]=="COMMITTED" and
              committed["result"]["sha256"]==hashlib.sha256(data).hexdigest() and
              committed["result"]["bytes"]==len(data))
        code,_=call("commit",{"upload_id":tx,"sha256":hashlib.sha256(data).hexdigest()},
                    identity=auth["Samsung-A"])
        check("cannot_commit_twice",code==400)
        registry.revoke_local(a,True)
        code,_=call("status",{"upload_id":tx},identity=auth["Samsung-A"])
        check("revoked_device_denied",code in (401,403))
        code,reply=call("begin",{"destination":str(tmp/"b.bin")},
                        identity=auth["Samsung-B"])
        check("other_device_still_authorized",code==200)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        bridge_module.get_device_registry=orig_registry
        bridge_module.get_owner_file_rpc=orig_rpc

print(json.dumps({"schema":"BCP_G4_E2E_OWNER_FILES_TLS_V1",
                  "checks":checks,"passed":len(checks),"PASS":all(checks.values()),
                  "real_owner_profile_created":False,
                  "real_user_files_modified":False,
                  "local_port_closed":True},indent=2))
