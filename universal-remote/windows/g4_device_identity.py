"""BCP G4 per-device identity registry (v1).

G2 pairing authenticates transport only. An enrolled device has its own 256-bit
random credential, provisioned over authenticated private TLS and approved on
the signed-in Windows session after matching a six-digit confirmation code.

This library exposes NO remote grant operation. Only the local Windows UI may
call approve_local(). No legacy shared pairing token is a device identity.
"""
from __future__ import annotations
import hashlib
from contextlib import contextmanager
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import threading
import time

HEX32=re.compile(r"^[0-9a-f]{32}$")
HEX64=re.compile(r"^[0-9a-f]{64}$")
NONCE_RE=re.compile(r"^[0-9a-f]{32}$")
LABEL_RE=re.compile(r"^[\w .()_-]{1,45}$",re.UNICODE)
MAX_PENDING=3
PENDING_SECONDS=600
AUTH_WINDOW_SECONDS=90

class IdentityError(PermissionError):
    pass

def atomic_json(path,value):
    tmp=path.with_name(path.name+"."+secrets.token_hex(8)+".tmp")
    try:
        with tmp.open("x",encoding="utf-8") as stream:
            json.dump(value,stream,sort_keys=True,separators=(",",":"),ensure_ascii=False)
            stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def _private_dir(path):
    path.mkdir(parents=True,exist_ok=True)
    if os.name=="nt":
        user=os.environ.get("USERNAME")
        if not user:raise IdentityError("WINDOWS_USER_REQUIRED")
        result=subprocess.run(["icacls",str(path),"/inheritance:r",
            "/grant:r",user+":(OI)(CI)F"],capture_output=True,timeout=12)
        if result.returncode!=0:raise IdentityError("PRIVATE_DIRECTORY_ACL_FAILED")

def _private_file(path):
    if os.name=="nt":
        user=os.environ.get("USERNAME")
        result=subprocess.run(["icacls",str(path),"/inheritance:r",
            "/grant:r",user+":F"],capture_output=True,timeout=12)
        if result.returncode!=0:raise IdentityError("PRIVATE_FILE_ACL_FAILED")

def _check_device(device_id):
    if not isinstance(device_id,str) or not HEX32.fullmatch(device_id):
        raise IdentityError("DEVICE_ID_INVALID")
    return device_id

def _code(device_id,secret):
    raw=hashlib.sha256(b"BCP_ENROLL_V1\x00"+bytes.fromhex(device_id)+
                       bytes.fromhex(secret)).digest()
    return f"{int.from_bytes(raw[:8],'big')%1000000:06d}"

def signing_message(device_id,method,path,timestamp,nonce,body):
    return ("BCP_DEVICE_V1\n"+device_id+"\n"+method+"\n"+path+"\n"+
            str(timestamp)+"\n"+nonce+"\n"+
            hashlib.sha256(body).hexdigest()).encode("ascii")

class DeviceRegistry:
    def __init__(self,base:Path):
        self.root=Path(base)
        self.pending=self.root/"pending-devices"
        self.enrolled=self.root/"enrolled-devices"
        _private_dir(self.root)
        _private_dir(self.pending)
        _private_dir(self.enrolled)
        self.dbpath=self.root/"device-nonces.sqlite"
        self.lock=threading.RLock()
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS nonces (device TEXT NOT NULL,"
                       " nonce TEXT NOT NULL, seen INTEGER NOT NULL,"
                       " PRIMARY KEY(device,nonce))")
        _private_file(self.dbpath)

    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.dbpath,timeout=12)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _file(self,folder,device_id):
        return folder/(_check_device(device_id)+".json")

    def _read(self,file):
        try:
            value=json.loads(file.read_text(encoding="utf-8"))
        except (OSError,ValueError) as err:
            raise IdentityError("DEVICE_RECORD_UNAVAILABLE") from err
        if value.get("schema")!="BCP_DEVICE_IDENTITY_V1":
            raise IdentityError("DEVICE_RECORD_CORRUPTED")
        return value

    def _prune_pending(self,now):
        for path in self.pending.glob("*.json"):
            try:
                record=self._read(path)
                if record["expires"]<now:path.unlink()
            except (OSError,ValueError,IdentityError,KeyError):
                # Corrupted records never authorize, and are left for inspection.
                pass

    def request_enrollment(self,device_id,device_secret,label,now=None):
        """Called only after validated G2 HMAC/TLS, but creates NO authority."""
        _check_device(device_id)
        if not isinstance(device_secret,str) or not HEX64.fullmatch(device_secret):
            raise IdentityError("DEVICE_SECRET_INVALID")
        if not isinstance(label,str) or not LABEL_RE.fullmatch(label):
            raise IdentityError("DEVICE_LABEL_INVALID")
        now=int(time.time() if now is None else now)
        with self.lock:
            self._prune_pending(now)
            if self._file(self.enrolled,device_id).exists():
                active=self._read(self._file(self.enrolled,device_id))
                if active.get("revoked") is False and hmac.compare_digest(
                        active["secret"],device_secret):
                    return {"device_id":device_id,"label":active["label"],
                            "status":"ALREADY_ENROLLED","expires":None}
                raise IdentityError("DEVICE_ALREADY_REGISTERED_OR_REVOKED")
            pending=self._file(self.pending,device_id)
            if pending.exists():
                existing=self._read(pending)
                if (existing["expires"]>=now and
                    hmac.compare_digest(existing["secret"],device_secret)):
                    # Repeat request from the SAME handset: no duplicate
                    # error and no extension of the approval lifetime.
                    return {"device_id":device_id,"label":existing["label"],
                            "verification_code":_code(device_id,device_secret),
                            "status":"PENDING_WINDOWS_CONFIRMATION",
                            "expires":existing["expires"]}
                raise IdentityError("ENROLLMENT_CONFLICT")
            if len(list(self.pending.glob("*.json")))>=MAX_PENDING:
                raise IdentityError("TOO_MANY_PENDING_ENROLLMENTS")
            item={"schema":"BCP_DEVICE_IDENTITY_V1","device_id":device_id,
                  "secret":device_secret,"label":label,
                  "requested":now,"expires":now+PENDING_SECONDS,
                  "revoked":False,"approved_at":None}
            atomic_json(pending,item)
            _private_file(pending)
        # Code displayed on Android and compared with the Windows UI.
        return {"device_id":device_id,"label":label,
                "verification_code":_code(device_id,device_secret),
                "status":"PENDING_WINDOWS_CONFIRMATION",
                "expires":now+PENDING_SECONDS}

    def pending_public(self,now=None):
        now=int(time.time() if now is None else now)
        with self.lock:
            self._prune_pending(now)
            result=[]
            for file in self.pending.glob("*.json"):
                try:
                    item=self._read(file)
                    if item["expires"]>=now:
                        result.append({"device_id":item["device_id"],
                            "label":item["label"],"requested":item["requested"],
                            "expires":item["expires"]})
                except (IdentityError,KeyError,ValueError):pass
            return sorted(result,key=lambda x:x["requested"])

    def pending_code_local(self,device_id,now=None):
        """Local Windows GUI ONLY. Display alongside phone code for
        single affirmative click; never available from HTTP."""
        now=int(time.time() if now is None else now)
        with self.lock:
            entry=self._read(self._file(self.pending,device_id))
            if entry["expires"]<now:raise IdentityError("ENROLLMENT_EXPIRED")
            return _code(device_id,entry["secret"])

    def approve_local(self,device_id,typed_code,local_user_confirmed=False,now=None):
        if local_user_confirmed is not True:
            raise IdentityError("LOCAL_WINDOWS_APPROVAL_REQUIRED")
        _check_device(device_id)
        if not isinstance(typed_code,str) or not re.fullmatch(r"[0-9]{6}",typed_code):
            raise IdentityError("CONFIRMATION_CODE_INVALID")
        now=int(time.time() if now is None else now)
        with self.lock:
            pending=self._file(self.pending,device_id)
            entry=self._read(pending)
            if entry["expires"]<now:raise IdentityError("ENROLLMENT_EXPIRED")
            if not hmac.compare_digest(typed_code,_code(device_id,entry["secret"])):
                raise IdentityError("CONFIRMATION_CODE_MISMATCH")
            target=self._file(self.enrolled,device_id)
            if target.exists():raise IdentityError("DEVICE_ALREADY_REGISTERED")
            entry["approved_at"]=now
            entry["expires"]=None
            atomic_json(target,entry)
            _private_file(target)
            pending.unlink()
            return {"device_id":device_id,"label":entry["label"],
                    "status":"ENROLLED","owner_trust":"NOT_GRANTED"}

    def verify_request(self,device_id,method,path,timestamp,nonce,body,signature,now=None):
        """Individual HMAC independent of the shared legacy G2 HMAC."""
        _check_device(device_id)
        if method!="POST" or not isinstance(path,str) or not path.startswith("/v1/g4/"):
            raise IdentityError("METHOD_OR_PATH_INVALID")
        if not isinstance(timestamp,str) or not timestamp.isdecimal() or len(timestamp)>12:
            raise IdentityError("TIMESTAMP_INVALID")
        if not isinstance(nonce,str) or not NONCE_RE.fullmatch(nonce):
            raise IdentityError("NONCE_INVALID")
        if not isinstance(signature,str) or not HEX64.fullmatch(signature):
            raise IdentityError("SIGNATURE_INVALID")
        if not isinstance(body,bytes):raise IdentityError("BODY_INVALID")
        now=int(time.time() if now is None else now)
        if abs(int(timestamp)-now)>AUTH_WINDOW_SECONDS:
            raise IdentityError("REQUEST_EXPIRED")
        entry=self._read(self._file(self.enrolled,device_id))
        if entry["device_id"]!=device_id or entry.get("revoked") is not False:
            raise IdentityError("DEVICE_REVOKED")
        secret=bytes.fromhex(entry["secret"])
        material=signing_message(device_id,method,path,timestamp,nonce,body)
        expected=hmac.new(secret,material,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):
            raise IdentityError("DEVICE_SIGNATURE_INVALID")
        with self.lock, self._db() as db:
            db.execute("DELETE FROM nonces WHERE seen < ?",(now-AUTH_WINDOW_SECONDS*3,))
            try:
                db.execute("INSERT INTO nonces VALUES (?,?,?)",(device_id,nonce,now))
                db.commit()
            except sqlite3.IntegrityError as err:
                raise IdentityError("DEVICE_REPLAY_DENIED") from err
        return device_id

    def signed_for_test(self,device_id,path,body,nonce,timestamp):
        """Test helper: still requires a registered device, never a public endpoint."""
        entry=self._read(self._file(self.enrolled,device_id))
        return hmac.new(bytes.fromhex(entry["secret"]),
                        signing_message(device_id,"POST",path,timestamp,nonce,body),
                        hashlib.sha256).hexdigest()

    def revoke_local(self,device_id,local_user_confirmed=False):
        if local_user_confirmed is not True:
            raise IdentityError("LOCAL_WINDOWS_APPROVAL_REQUIRED")
        with self.lock:
            p=self._file(self.enrolled,device_id)
            entry=self._read(p)
            entry["revoked"]=True
            atomic_json(p,entry);_private_file(p)
            return {"device_id":device_id,"status":"REVOKED"}

    def enrolled_public(self):
        result=[]
        for p in self.enrolled.glob("*.json"):
            try:
                e=self._read(p)
                result.append({"device_id":e["device_id"],
                    "label":e["label"],"revoked":e["revoked"],
                    "approved_at":e["approved_at"]})
            except (IdentityError,KeyError):pass
        return result
