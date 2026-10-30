"""G4 owner file route negative authentication tests on a loopback-only G2 staging server.

Reads the local G2 pairing credential at runtime on the authorized PC only.
Never prints it, enrolls devices, activates owner, or writes user files.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import ssl
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen

p=argparse.ArgumentParser()
p.add_argument("--port",type=int,default=8912)
args=p.parse_args()
root=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
legacy=Path(os.environ["LOCALAPPDATA"])/"BCP-USB-Rescue"
shared=(legacy/"private-state"/"pairing-key.txt").read_text("ascii").strip().encode()
ctx=ssl.create_default_context(cafile=str(root/"private-state"/"g2-server.crt"))

checks={}
def check(name,flag):
    checks[name]=bool(flag)
    if not flag:raise AssertionError(name)

def query(path,body,device_headers=None):
    data=json.dumps(body,separators=(",",":")).encode("utf8")
    nonce=secrets.token_hex(16)
    time_header=str(int(time.time()))
    signature=hmac.new(shared,("POST\n"+path+"\n"+time_header+"\n"+
        nonce+"\n"+hashlib.sha256(data).hexdigest()).encode(),hashlib.sha256).hexdigest()
    headers={"Content-Type":"application/json","X-Bridge-Nonce":nonce,
             "X-Bridge-Time":time_header,"X-Bridge-Signature":signature}
    headers.update(device_headers or {})
    req=Request("https://127.0.0.1:"+str(args.port)+path,
                data=data,headers=headers,method="POST")
    try:
        with urlopen(req,context=ctx,timeout=15) as response:
            code=response.status
            reply=response.read()
            received=response.headers.get("X-Bridge-Signature")
    except HTTPError as err:
        code=err.code
        reply=err.read()
        received=err.headers.get("X-Bridge-Signature")
    expected=hmac.new(shared,(nonce+"\n"+str(code)+"\n"+
        hashlib.sha256(reply).hexdigest()).encode(),hashlib.sha256).hexdigest()
    check("response_hmac_"+str(len(checks)),hmac.compare_digest(expected,received or ""))
    return code,json.loads(reply.decode("utf8"))

code,obj=query("/v1/status",{})
check("legacy_g2_signed_status_ok",code==200 and obj.get("ok") is True)
code,obj=query("/v1/g4/owner/files",{"action":"begin","args":{"destination":str(root/"G4-Staging-Workspace"/"no-write.txt")}})
check("legacy_shared_key_cannot_start_owner_file",code==401)
headers={"X-BCP-Device":"a"*32,"X-BCP-Device-Time":str(int(time.time())),
         "X-BCP-Device-Nonce":secrets.token_hex(16),
         "X-BCP-Device-Signature":"0"*64}
code,obj=query("/v1/g4/owner/files",{"action":"begin","args":{"destination":str(root/"G4-Staging-Workspace"/"no-write.txt")}},headers)
check("unregistered_identity_cannot_write",code in (401,403))
code,obj=query("/v1/g4/universal/inventory",{"action":"system.volumes","args":{}})
check("legacy_shared_key_cannot_read_owner_inventory",code==401)
code,obj=query("/v1/g4/device/enroll/request",{})
check("malformed_individual_enrollment_denied",code in (400,403))
code,obj=query("/v1/g4/files/list",{"path":str(Path.home())})
check("existing_read_service_still_available",code==200)
print(json.dumps({"schema":"BCP_G4_OWNER_FILES_LOOPBACK_STAGING",
                  "checks":checks,"passed":len(checks),"PASS":all(checks.values()),
                  "real_owner_enrolled":False,"owner_files_written":0,
                  "remote_shell_exposed":False},indent=2))
