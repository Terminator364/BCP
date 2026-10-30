"""BCP owner trust policy: durable, revocable, no arbitrary session/time/op quotas.

The owner profile is minted only by a locally approved Windows interaction.
This module does not elevate privileges or expose commands over the network.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time

CATEGORIES=frozenset(("files.read","files.write","commands","processes",
                      "desktop","services","install","automation"))
RISK={"files.read":"ordinary","files.write":"ordinary",
      "commands":"sensitive","processes":"ordinary","desktop":"sensitive",
      "services":"sensitive","install":"sensitive","automation":"ordinary"}
PROFILES={
 "observer":frozenset(("files.read","processes")),
 "operator":frozenset(("files.read","files.write","commands","processes",
                       "desktop","services","install","automation"))
}
DEVICE_RE=re.compile(r"^[a-f0-9]{64}$")

class TrustError(PermissionError):
    pass

def _mac(obj,key):
    canon={k:v for k,v in obj.items() if k!="signature"}
    data=json.dumps(canon,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hmac.new(key,data,hashlib.sha256).hexdigest()

def _atomic(file,obj):
    file.parent.mkdir(parents=True,exist_ok=True)
    tmp=file.with_name(file.name+"."+secrets.token_hex(8)+".tmp")
    try:
        with tmp.open("x",encoding="utf8") as stream:
            json.dump(obj,stream,ensure_ascii=False,sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,file)
    finally:
        if tmp.exists():tmp.unlink()

class OwnerTrust:
    def __init__(self, directory:Path, key:bytes):
        if len(key)!=32:raise ValueError("OWNER_KEY_LENGTH_INVALID")
        self.root=Path(directory)
        self.key=key
        # The caller must protect directory under the Windows user's ACL.
        # This class does not grant trust during initialization.
    def _path(self,device_hash):
        if not isinstance(device_hash,str) or not DEVICE_RE.fullmatch(device_hash):
            raise TrustError("DEVICE_ID_INVALID")
        return self.root/(device_hash+".json")
    def _verified(self,path):
        if not path.is_file():raise TrustError("DEVICE_NOT_TRUSTED")
        try:obj=json.loads(path.read_text("utf8"))
        except (ValueError,OSError) as e:raise TrustError("CORRUPTED_PROFILE") from e
        got=obj.get("signature")
        if not isinstance(got,str) or not hmac.compare_digest(got,_mac(obj,self.key)):
            raise TrustError("PROFILE_TAMPERED")
        return obj
    def enroll_local(self,device_hash,profile="operator",confirm_local=False,
                     high_risk_confirmation=True):
        """Only trusted local approval center invokes this, after explicit user click."""
        if confirm_local is not True:
            raise TrustError("LOCAL_WINDOWS_CONFIRMATION_REQUIRED")
        if profile not in PROFILES:
            raise ValueError("UNKNOWN_PROFILE")
        path=self._path(device_hash)
        now=int(time.time())
        obj={"schema":"BCP_OWNER_TRUST_V1","device":device_hash,
             "profile":profile,"categories":sorted(PROFILES[profile]),
             "enrolled_at":now,"revoked":False,
             "expiry":None,"operation_limit":None,
             "path_scope":None,"high_risk_confirmation":bool(high_risk_confirmation)}
        obj["signature"]=_mac(obj,self.key)
        _atomic(path,obj)
        return self.public_status(device_hash)
    def public_status(self,device_hash):
        try:obj=self._verified(self._path(device_hash))
        except TrustError:
            return {"trusted":False,"profile":None,"categories":[]}
        return {"trusted":not obj["revoked"],"profile":obj["profile"],
                "categories":obj["categories"],"path_scope":obj["path_scope"],
                "operation_limit":obj["operation_limit"],"expiry":obj["expiry"],
                "high_risk_confirmation":obj["high_risk_confirmation"]}
    def authorize(self,device_hash,category,approval_for_sensitive=False):
        if category not in CATEGORIES:
            raise TrustError("UNKNOWN_CAPABILITY")
        obj=self._verified(self._path(device_hash))
        if obj["revoked"]:raise TrustError("DEVICE_REVOKED")
        if category not in obj["categories"]:raise TrustError("CATEGORY_NOT_GRANTED")
        if obj["high_risk_confirmation"] and RISK[category]=="sensitive" and not approval_for_sensitive:
            raise TrustError("HIGH_RISK_CONFIRMATION_REQUIRED")
        return True
    def revoke_local(self,device_hash,confirm_local=False):
        if confirm_local is not True:raise TrustError("LOCAL_WINDOWS_CONFIRMATION_REQUIRED")
        p=self._path(device_hash)
        obj=self._verified(p)
        obj["revoked"]=True
        obj["signature"]=_mac(obj,self.key)
        _atomic(p,obj)
        return {"trusted":False,"revoked":True}

def key_fingerprint(pairing_secret_hex):
    if not isinstance(pairing_secret_hex,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",pairing_secret_hex):
        raise ValueError("PAIRING_SECRET_INVALID")
    return hashlib.sha256(bytes.fromhex(pairing_secret_hex)).hexdigest()
