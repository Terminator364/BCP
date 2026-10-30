"""G4 owner-bound streamed file operations: two separately enrolled devices."""
import base64
import hashlib
from pathlib import Path
import secrets
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g4_device_identity import DeviceRegistry
from g4_owner_trust import OwnerTrust
from g4_owner_transactions import OwnerFileService,TransactionAuthError,owner_hash

checks={}
def ok(label,flag):
    checks[label]=bool(flag)
    if not flag:raise AssertionError(label)
def deny(label,fn):
    try:fn()
    except (PermissionError,ValueError):ok(label,True)
    else:raise AssertionError(label)

with tempfile.TemporaryDirectory(prefix="bcp-ownerfiles-") as temp:
    root=Path(temp)
    reg=DeviceRegistry(root/"device-state")
    owner=OwnerTrust(root/"trust",secrets.token_bytes(32))
    devices=[]
    for label in ("Samsung-A","Samsung-B"):
        ident=secrets.token_hex(16)
        enrollment=reg.request_enrollment(ident,secrets.token_hex(32),label)
        reg.approve_local(ident,enrollment["verification_code"],True)
        owner.enroll_local(owner_hash(ident),confirm_local=True,profile="operator")
        devices.append(ident)
    a,b=devices
    service=OwnerFileService(root/"transfer-state",owner,reg)
    dest=root/"transfered-test.txt"
    payload=b"BCP_OWNER_SEPARATED_"+bytes(range(256))*450
    started=service.begin(a,str(dest))
    tx=started["upload_id"]
    ok("owner_a_has_transaction",service.status(a,tx)["offset"]==0)
    deny("owner_b_cannot_inspect",lambda:service.status(b,tx))
    deny("owner_b_cannot_append",lambda:service.append(b,tx,0,base64.b64encode(b"wrong").decode()))
    deny("legacy_empty_device_denied",lambda:service.status(None,tx))
    offset=0
    for part in (payload[i:i+65536] for i in range(0,len(payload),65536)):
        ack=service.append(a,tx,offset,base64.b64encode(part).decode(),
                           hashlib.sha256(part).hexdigest())
        offset=ack["next_offset"]
    ok("streamed_file_crosses_chunk",offset==len(payload))
    restarted=OwnerFileService(root/"transfer-state",owner,reg)
    ok("owner_resumption_survives_restart",restarted.status(a,tx)["offset"]==len(payload))
    deny("wrong_owner_cannot_commit",lambda:restarted.commit(b,tx,hashlib.sha256(payload).hexdigest()))
    ok("owner_a_commits",restarted.commit(a,tx,hashlib.sha256(payload).hexdigest())["status"]=="COMMITTED")
    ok("correct_file_sha",hashlib.sha256(dest.read_bytes()).digest()==hashlib.sha256(payload).digest())
    deny("unauthorized_replay_refused",lambda:restarted.commit(a,tx,hashlib.sha256(payload).hexdigest()))
    queued=restarted.begin(a,str(root/"not_created.txt"))
    reg.revoke_local(a,True)
    deny("revoked_phone_cannot_append",lambda:restarted.append(a,queued["upload_id"],0,"YQ=="))
    deny("revoked_phone_cannot_commit",lambda:restarted.commit(a,queued["upload_id"],hashlib.sha256(b"").hexdigest()))
    ok("uncommitted_file_absent",not (root/"not_created.txt").exists())
    own_b=restarted.begin(b,str(root/"second_phone.txt"))
    restarted.append(b,own_b["upload_id"],0,"Yg==")
    restarted.commit(b,own_b["upload_id"],hashlib.sha256(b"b").hexdigest())
    ok("other_phone_remains_authorized",(root/"second_phone.txt").read_bytes()==b"b")
    from g4_owner_gateway import ROOT as BCP_ROOT
    deny("private_credential_denied",lambda:restarted.begin(b,str(BCP_ROOT/"private-state"/"g4"/"owner-hmac-key")))
print({"schema":"BCP_G4_OWNER_BOUND_FILES_LAB_V1","passed":len(checks),
       "checks":checks,"PASS":all(checks.values()),"real_owner_enrolled":False,
       "user_files_modified":False})
