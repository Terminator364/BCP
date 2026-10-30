"""BCP owner-wide inventory: explicit permission, arbitrary volume paths, no arbitrary total limit."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import g4_owner_gateway as gateway
import g4_owner_trust as trust

checks={}
def check(name,flag):
    checks[name]=bool(flag)
    if not flag:raise AssertionError(name)
def denied(name,func):
    try:func()
    except (ValueError,PermissionError,OSError):
        check(name,True)
    else:check(name,False)

old_load=gateway.load_policy
device_id=secrets.token_hex(16)
def gw(payload):
    return gateway.inventory_query(payload,device_id=device_id)
sample=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"/"G4-Staging-Workspace"
sample.mkdir(parents=True,exist_ok=True)
try:
    denied("legacy_owner_route_denied",lambda:gateway.inventory_query(
        {"action":"system.volumes","args":{}}))
    with tempfile.TemporaryDirectory(prefix="g4-owner-unit-",dir=str(sample)) as tmp:
        root=Path(tmp)
        key=secrets.token_bytes(32)
        p=trust.OwnerTrust(root/"profiles",key)
        device=hashlib.sha256(("BCP_DEVICE_V1:"+device_id).encode('ascii')).hexdigest()
        gateway.load_policy=lambda:p
                denied("no_implicit_trust",lambda:gw(
            {"action":"system.volumes","args":{}}))
        p.enroll_local(device,profile="operator",confirm_local=True)
        volumes=gw({"action":"system.volumes","args":{}})
        check("win_drives_enumerated",len(volumes["data"]["drives"])>=1)
        a=root/"folder-A";b=root/"folder-B"
        a.mkdir();b.mkdir()
        for i in range(239):(a/("entry_%03d.txt"%i)).write_text("x")
        first=gw({"action":"files.list",
                     "args":{"path":str(a),"cursor":0,"page_size":128}})["data"]
        second=gw({"action":"files.list",
                     "args":{"path":str(a),"cursor":first["next_cursor"],"page_size":128}})["data"]
        check("multiple_pages_unrestricted_count",
              len(first["items"])+len(second["items"])==239)
        check("pagination_correct_end",second["next_cursor"] is None)
        payload=os.urandom(409601)
        file=b/"large.dat"
        file.write_bytes(payload)
        current=0
        data=bytearray()
        import base64
        while True:
            part=gw({"action":"files.read_chunk",
                "args":{"path":str(file),"offset":current}})["data"]
            data.extend(base64.b64decode(part["data_base64"]))
            if part["next_offset"] is None:break
            current=part["next_offset"]
        check("large_file_whole_no_total_limit",data==payload)
        dig=gw({"action":"files.digest",
                            "args":{"path":str(file)}})["data"]
        check("large_file_digest",dig["sha256"]==hashlib.sha256(payload).hexdigest())
        check("unrelated_directory_read",gw({
            "action":"files.stat","args":{"path":str(a)}})["data"]["directory"])
        denied("credential_private_state_blocked",lambda:gw(
            {"action":"files.list","args":{"path":str(gateway.ROOT/"private-state")}}))
        denied("credential_legacy_keys_blocked",lambda:gw(
            {"action":"files.read_chunk","args":{"path":str(gateway.LEGACY/"private-state"/"pairing-key.txt")}}))
        denied("private_key_suffix_blocked",lambda:gw(
            {"action":"files.read_chunk","args":{"path":str(b/"fake.pem")}}))
        denied("relative_paths_rejected",lambda:gw(
            {"action":"files.list","args":{"path":"relative"}}))
        denied("write_via_read_route_denied",lambda:gw(
            {"action":"files.write","args":{"path":str(file),"text":"bad"}}))
        denied("command_via_read_route_denied",lambda:gw(
            {"action":"commands.start","args":{"executable":"cmd.exe"}}))
        denied("unknown_shape_denied",lambda:gw(
            {"action":"system.volumes","device":"attacker"}))
        denied("bad_page_denied",lambda:gw(
            {"action":"files.list","args":{"path":str(a),"page_size":1000000}}))
        p.revoke_local(device,confirm_local=True)
        denied("revoked_denies_full_read",lambda:gw(
            {"action":"system.volumes","args":{}}))
finally:
    gateway.load_policy=old_load
print(json.dumps({"schema":"BCP_G4_OWNER_GENERAL_INVENTORY_TEST",
                  "checks":checks,"passed":sum(checks.values()),
                  "PASS":all(checks.values()),"production_owner_profile":False,
                  "no_user_files_opened":True},indent=2))
