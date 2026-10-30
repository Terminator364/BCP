"""G4 RPC dispatch contract laboratory on ephemeral local storage only."""
import base64,hashlib
from pathlib import Path
import secrets
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g4_device_identity import DeviceRegistry
from g4_owner_trust import OwnerTrust
from g4_owner_transactions import owner_hash
from g4_owner_file_rpc import OwnerFileRpc,RpcError

checks={}
def ok(name,flag):
    checks[name]=bool(flag)
    if not flag:raise AssertionError(name)
def denied(name,call):
    try:call()
    except (PermissionError,ValueError):ok(name,True)
    else:raise AssertionError(name)

with tempfile.TemporaryDirectory(prefix="bcp-rpc-") as folder:
    root=Path(folder)
    reg=DeviceRegistry(root/"devices")
    own=OwnerTrust(root/"trust",secrets.token_bytes(32))
    a=secrets.token_hex(16); b=secrets.token_hex(16)
    for d,name in ((a,"Samsung A"),(b,"Samsung B")):
        challenge=reg.request_enrollment(d,secrets.token_hex(32),name)
        reg.approve_local(d,challenge["verification_code"],True)
        own.enroll_local(owner_hash(d),confirm_local=True)
    rpc=OwnerFileRpc(root/"transfer",own,reg)
    denied("no_legacy_id",lambda:rpc.dispatch(None,"begin",{"destination":str(root/"test.txt")}))
    denied("unknown_action",lambda:rpc.dispatch(a,"run",{"executable":"cmd.exe"}))
    denied("unknown_arguments",lambda:rpc.dispatch(a,"begin",{"destination":str(root/"test.txt"),"admin":True}))
    denied("missing_arguments",lambda:rpc.dispatch(a,"append",{"upload_id":"0"*32}))
    denied("invalid_object",lambda:rpc.dispatch(a,"begin",[]))
    test=root/"test.txt"
    tx=rpc.dispatch(a,"begin",{"destination":str(test)})["upload_id"]
    denied("cross_phone_status_denied",lambda:rpc.dispatch(b,"status",{"upload_id":tx}))
    denied("cross_phone_append_denied",lambda:rpc.dispatch(b,"append",{"upload_id":tx,"offset":0,"data_base64":"YQ=="}))
    ok("correct_device_upload",rpc.dispatch(a,"append",{"upload_id":tx,"offset":0,"data_base64":"YQ=="})["next_offset"]==1)
    ok("status_resumption",rpc.dispatch(a,"status",{"upload_id":tx})["offset"]==1)
    ok("commit_file",rpc.dispatch(a,"commit",{"upload_id":tx,"sha256":hashlib.sha256(b"a").hexdigest()})["status"]=="COMMITTED")
    ok("content_correct",test.read_bytes()==b"a")
    reg.revoke_local(a,True)
    denied("revoked_own_status_denied",lambda:rpc.dispatch(a,"status",{"upload_id":tx}))
    ok("separate_device_unaffected",rpc.dispatch(b,"begin",{"destination":str(root/"other.txt")})["next_offset"]==0)
print({"schema":"BCP_G4_OWNER_FILE_RPC_LAB","checks":checks,"passed":len(checks),
       "PASS":all(checks.values()),"endpoint_exposed":False,
       "user_files_modified":False})
