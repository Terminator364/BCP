"""BCP G4 general inventory through a durable, locally approved owner profile.

No arbitrary per-folder, count or lifetime ceiling. Windows ACLs apply.
Credential files are explicitly excluded from any remote file-read endpoint.
No public enrollment route and no command execution in this read gateway.
"""
from __future__ import annotations
import os
import re
import secrets
import subprocess
from pathlib import Path
import g4_owner_trust as trust
import g4_universal_inventory as inventory

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
LEGACY=Path(os.environ["LOCALAPPDATA"])/"BCP-USB-Rescue"
POLICY=ROOT/"private-state"/"g4"/"owner-policy"
KEY=ROOT/"private-state"/"g4"/"owner-hmac-key"
READ_ACTIONS={
 "system.volumes","files.stat","files.list","files.read_chunk","files.digest",
 "processes.list","desktop.windows"
}
FILE_ACTIONS={"files.stat","files.list","files.read_chunk","files.digest"}
SECRET_NAMES={".env","id_rsa","id_ed25519","pairing-key.txt",
              "g2-server.key","owner-hmac-key"}
SECRET_EXTENSIONS={".p12",".pfx",".jks",".keystore",".pem",".key",".der"}

def _guard_path(raw):
    if not isinstance(raw,str):
        raise ValueError("PATH_REQUIRED")
    p=inventory._path(raw)
    p=p.resolve(strict=False)
    lexical=str(p).casefold()
    # The Windows agent must not reveal its own API credentials or APK signing
    # material even when it runs under the owner's profile.
    forbidden=(ROOT/"private-state", LEGACY/"private-state")
    for x in forbidden:
        sensitive=str(x.resolve(strict=False)).casefold()
        if lexical==sensitive or lexical.startswith(sensitive+os.sep):
            raise ValueError("AGENT_CREDENTIALS_PROTECTED")
    for part in p.parts:
        if part.casefold() in SECRET_NAMES:
            raise ValueError("CREDENTIAL_FILE_PROTECTED")
    if p.suffix.casefold() in SECRET_EXTENSIONS:
        raise ValueError("CREDENTIAL_FORMAT_PROTECTED")
    return p

def identity_from_existing_pairing():
    raw=(LEGACY/"private-state"/"pairing-key.txt").read_text("ascii").strip()
    return trust.key_fingerprint(raw)

def local_key_init():
    """Explicitly called by local Windows enrollment UI, never by HTTP handler."""
    KEY.parent.mkdir(parents=True,exist_ok=True)
    if not KEY.exists():
        flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
        try:
            fd=os.open(KEY,flags,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd,"w",encoding="ascii") as f:
                f.write(secrets.token_hex(32))
                f.flush();os.fsync(f.fileno())
    if os.name=="nt":
        user=os.environ.get("USERNAME","")
        if not user:
            raise RuntimeError("WINDOWS_ACCOUNT_UNKNOWN")
        # Restrict both the credential and the local profile directory.
        for path in (KEY,KEY.parent,POLICY):
            if path==POLICY and not path.exists():
                path.mkdir(parents=True,exist_ok=True)
            if path.exists():
                result=subprocess.run(["icacls",str(path),"/inheritance:r",
                    "/grant:r",user+":(OI)(CI)F" if path.is_dir() else user+":F"],
                    capture_output=True,timeout=12)
                if result.returncode!=0:
                    raise RuntimeError("OWNER_KEY_ACL_FAILED")
    return load_policy()

def load_policy():
    if not KEY.is_file():
        raise trust.TrustError("OWNER_ACTIVATION_REQUIRED")
    text=KEY.read_text("ascii").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}",text):
        raise trust.TrustError("OWNER_KEY_INVALID")
    return trust.OwnerTrust(POLICY,bytes.fromhex(text))

def local_enroll(profile="operator",high_risk_confirmation=True):
    # Fail closed: the old G2 shared pairing key is NOT a device identity.
    raise trust.TrustError("LEGACY_SHARED_PAIRING_NOT_ALLOWED_FOR_OWNER")

def local_enroll_verified_device(device_id,profile="operator",
                                 high_risk_confirmation=True):
    """Local Windows UI only, after the per-device verification code is typed."""
    from g4_device_identity import DeviceRegistry
    registry=DeviceRegistry(ROOT/"private-state"/"g4"/"device-registry")
    enrolled=[p for p in registry.enrolled_public()
              if p["device_id"]==device_id and p["revoked"] is False]
    if len(enrolled)!=1:
        raise trust.TrustError("INDIVIDUAL_DEVICE_NOT_ENROLLED")
    policy=local_key_init()
    return policy.enroll_local(trust.hashlib.sha256(
              ("BCP_DEVICE_V1:"+device_id).encode("ascii")).hexdigest(),
              profile=profile,confirm_local=True,
              high_risk_confirmation=high_risk_confirmation)

def local_revoke(device_id=None):
    if device_id is None:
        raise trust.TrustError("DEVICE_SELECTION_REQUIRED")
    policy=load_policy()
    identity=trust.hashlib.sha256(("BCP_DEVICE_V1:"+device_id).encode("ascii")).hexdigest()
    return policy.revoke_local(identity,confirm_local=True)

def public_status(device_id=None):
    # Legacy G2 HMAC alone never reveals/activates a privileged owner profile.
    if device_id is None:
        return {"trusted":False,"profile":None,"categories":[],
                "reason":"INDIVIDUAL_DEVICE_IDENTITY_REQUIRED"}
    try:
        from g4_device_identity import DeviceRegistry
        registry=DeviceRegistry(ROOT/"private-state"/"g4"/"device-registry")
        registered=any(x["device_id"]==device_id and not x["revoked"]
                        for x in registry.enrolled_public())
        if not registered:return {"trusted":False,"profile":None,"categories":[]}
        identity=trust.hashlib.sha256(("BCP_DEVICE_V1:"+device_id).encode("ascii")).hexdigest()
        return load_policy().public_status(identity)
    except (trust.TrustError,ValueError,OSError):
        return {"trusted":False,"profile":None,"categories":[]}

def inventory_query(payload,device_id=None):
    if device_id is None:
        raise trust.TrustError("INDIVIDUAL_DEVICE_SIGNATURE_REQUIRED")
    if not isinstance(payload,dict) or set(payload)-{"action","args"}:
        raise ValueError("REQUEST_SHAPE_INVALID")
    action=payload.get("action")
    args=payload.get("args",{})
    if action not in READ_ACTIONS:
        raise ValueError("CAPABILITY_NOT_AVAILABLE_ON_THIS_ENDPOINT")
    if not isinstance(args,dict):
        raise ValueError("ARGS_INVALID")
    if len(str(args))>6000:
        raise ValueError("ARGS_TOO_LONG")
    policy=load_policy()
    identity=trust.hashlib.sha256(("BCP_DEVICE_V1:"+device_id).encode("ascii")).hexdigest()
    device=identity
    capability="processes" if action=="processes.list" else (
         "desktop" if action=="desktop.windows" else "files.read")
    # Window titles are metadata, not remote desktop control. Still require
    # a verified owner policy and explicitly selected category.
    policy.authorize(device,capability,
                     approval_for_sensitive=False)
    if action in FILE_ACTIONS:
        p=_guard_path(args.get("path"))
        if action=="files.stat":
            result=inventory.stat(str(p))
        elif action=="files.list":
            result=inventory.list_page(str(p),
                    cursor=args.get("cursor",0),size=args.get("page_size",100))
        elif action=="files.read_chunk":
            result=inventory.read_chunk(str(p),
                    offset=args.get("offset",0),size=args.get("length",inventory.CHUNK_BYTES))
        else:
            result=inventory.file_digest(str(p))
    elif action=="system.volumes":
        result={"drives":inventory.volumes()}
    elif action=="processes.list":
        result=inventory.running_processes(
            cursor=args.get("cursor",0),size=args.get("page_size",100))
    else:
        result=inventory.windows()
    return {"action":action,"data":result,"paging_is_transport_only":True}
