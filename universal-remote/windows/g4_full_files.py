"""BCP Universal Windows files engine (local-only until owner-device security gate).

Streamed reads/writes with no total byte cap. Fixed chunk size is a RAM safeguard.
Preserve originals with recovery; require explicit replacement intent. No UAC bypass.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time

ID=re.compile(r"^[0-9a-f]{32}$")
CHUNK=65536

class FileOperationError(ValueError):
    pass

def digest(file):
    h=hashlib.sha256()
    with Path(file).open("rb") as f:
        for data in iter(lambda:f.read(CHUNK),b""):
            h.update(data)
    return h.hexdigest()

def _path(raw):
    if not isinstance(raw,str) or not raw or "\x00" in raw:
        raise FileOperationError("INVALID_PATH")
    p=Path(raw)
    if not p.is_absolute():
        raise FileOperationError("ABSOLUTE_PATH_REQUIRED")
    return p

def _atom(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+secrets.token_hex(8)+".tmp")
    try:
        with tmp.open("x",encoding="utf8") as stream:
            json.dump(obj,stream,ensure_ascii=False,sort_keys=True)
            stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

class FileTransactions:
    def __init__(self,state):
        self.state=Path(state)
        self.tasks=self.state/"files"/"uploads"
        self.recovery=self.state/"files"/"recovery"
        self.tasks.mkdir(parents=True,exist_ok=True)
        self.recovery.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
    def _metadata(self,ident):
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            raise FileOperationError("INVALID_TRANSACTION")
        file=self.tasks/(ident+".json")
        if not file.exists():
            raise FileOperationError("TRANSACTION_NOT_FOUND")
        m=json.loads(file.read_text("utf8"))
        if m.get("id")!=ident:
            raise FileOperationError("TRANSACTION_CORRUPTED")
        return file,m
    def begin(self,destination,overwrite=False,expected_old_sha=None):
        dest=_path(destination)
        if not dest.parent.is_dir():
            raise FileOperationError("PARENT_NOT_FOUND")
        if dest.is_dir():
            raise FileOperationError("DESTINATION_IS_DIRECTORY")
        if type(overwrite)!=bool:
            raise FileOperationError("OVERWRITE_BOOL_REQUIRED")
        if dest.exists() and not overwrite:
            raise FileOperationError("DESTINATION_EXISTS")
        old=None
        if dest.exists():
            old=digest(dest)
            if not isinstance(expected_old_sha,str) or expected_old_sha.lower()!=old:
                raise FileOperationError("OLD_SHA256_MISMATCH")
        elif overwrite and expected_old_sha is not None:
            raise FileOperationError("OLD_FILE_MISSING")
        ident=secrets.token_hex(16)
        stage=dest.parent/("."+dest.name+"."+ident+".bcp-part")
        with stage.open("xb") as f:
            f.flush();os.fsync(f.fileno())
        record={"schema":"BCP_WINDOWS_UPLOAD_V1","id":ident,"destination":str(dest),
                "stage":str(stage),"overwrite":overwrite,"expected_old_sha":old,
                "uploaded":0,"created":int(time.time()),"state":"RECEIVING"}
        _atom(self.tasks/(ident+".json"),record)
        return {"upload_id":ident,"next_offset":0,"destination":str(dest)}
    def append(self,ident,offset,data_base64,chunk_sha256=None):
        with self.lock:
            file,m=self._metadata(ident)
            if m.get("state")!="RECEIVING":
                raise FileOperationError("UPLOAD_NOT_ACTIVE")
            if type(offset)!=int or offset<0 or offset!=m["uploaded"]:
                raise FileOperationError("OFFSET_MISMATCH")
            if not isinstance(data_base64,str) or len(data_base64)>CHUNK*2:
                raise FileOperationError("CHUNK_INVALID")
            try:data=base64.b64decode(data_base64,validate=True)
            except (ValueError,TypeError) as e:
                raise FileOperationError("CHUNK_BASE64_INVALID") from e
            if len(data)>CHUNK:
                raise FileOperationError("CHUNK_TOO_LARGE")
            if chunk_sha256 is not None and hashlib.sha256(data).hexdigest()!=chunk_sha256:
                raise FileOperationError("CHUNK_HASH_MISMATCH")
            stage=Path(m["stage"])
            if not stage.is_file() or stage.stat().st_size!=offset:
                raise FileOperationError("STAGE_CHANGED")
            with stage.open("r+b") as f:
                f.seek(offset);f.write(data);f.flush();os.fsync(f.fileno())
            m["uploaded"]+=len(data)
            _atom(file,m)
            return {"upload_id":ident,"next_offset":m["uploaded"],
                    "chunk_bytes":len(data)}
    def commit(self,ident,expected_final_sha256):
        if not isinstance(expected_final_sha256,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",expected_final_sha256):
            raise FileOperationError("FINAL_SHA_REQUIRED")
        with self.lock:
            file,m=self._metadata(ident)
            if m.get("state")!="RECEIVING":
                raise FileOperationError("UPLOAD_NOT_ACTIVE")
            stage=Path(m["stage"]);dest=_path(m["destination"])
            if not stage.is_file() or stage.stat().st_size!=m["uploaded"]:
                raise FileOperationError("STAGE_CHANGED")
            if digest(stage)!=expected_final_sha256.lower():
                raise FileOperationError("FINAL_SHA_MISMATCH")
            backup=None
            if dest.exists():
                if not m["overwrite"] or digest(dest)!=m["expected_old_sha"]:
                    raise FileOperationError("OLD_FILE_CHANGED")
                backup=self.recovery/(ident+".bak")
                with dest.open("rb") as src,backup.open("xb") as dst:
                    shutil.copyfileobj(src,dst,CHUNK)
                    dst.flush();os.fsync(dst.fileno())
            elif m["expected_old_sha"] is not None:
                raise FileOperationError("OLD_FILE_DISAPPEARED")
            # Keep a recoverable journal before changing the destination.
            m["state"]="COMMITTING";m["result_sha256"]=expected_final_sha256.lower()
            m["recovery"]=str(backup) if backup else None
            _atom(file,m)
            # IMPORTANT: for a new file, Windows os.rename fails if another
            # writer created the same destination during this upload. Do NOT
            # use os.replace here: it would overwrite without permission.
            if m["overwrite"]:
                os.replace(stage,dest)
            else:
                if dest.exists():
                    raise FileOperationError("DESTINATION_CREATED_CONCURRENTLY")
                os.rename(stage,dest)
            m["state"]="COMMITTED"
            _atom(file,m)
            return {"status":"COMMITTED","path":str(dest),
                    "bytes":m["uploaded"],"sha256":m["result_sha256"],
                    "recoverable_original":bool(backup)}
    def abort(self,ident):
        with self.lock:
            file,m=self._metadata(ident)
            if m["state"]!="RECEIVING":
                raise FileOperationError("UPLOAD_NOT_ACTIVE")
            stage=Path(m["stage"])
            if stage.exists():stage.unlink()
            m["state"]="ABORTED"
            _atom(file,m)
            return {"status":"ABORTED"}
    def quarantine(self,source):
        with self.lock:
            src=_path(source)
            if not src.exists():
                raise FileOperationError("SOURCE_NOT_FOUND")
            ident=secrets.token_hex(16)
            target=self.recovery/(ident+"_"+src.name)
            if target.exists():raise FileOperationError("RECOVERY_COLLISION")
            # Journal the intention before moving any user data. A power loss
            # must not leave an unindexed recovered document.
            entry=self.recovery/(ident+".json")
            data={"id":ident,"origin":str(src),"recovery_path":str(target),
                  "state":"PREPARING","created":int(time.time())}
            _atom(entry,data)
            try:
                shutil.move(str(src),str(target))
            except Exception:
                data["state"]="RECOVERY_REQUIRED" if target.exists() else "FAILED"
                _atom(entry,data)
                raise
            data["state"]="QUARANTINED"
            _atom(entry,data)
            return {"recovery_id":ident,"recoverable":True,"origin":str(src)}
    def restore(self,ident):
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            raise FileOperationError("INVALID_RECOVERY_ID")
        with self.lock:
            state=self.recovery/(ident+".json")
            if not state.exists():raise FileOperationError("RECOVERY_NOT_FOUND")
            m=json.loads(state.read_text("utf8"))
            if m.get("state")!="QUARANTINED":
                raise FileOperationError("RECOVERY_ALREADY_USED")
            origin=_path(m["origin"])
            source=Path(m["recovery_path"])
            if origin.exists() or not source.exists() or not origin.parent.is_dir():
                raise FileOperationError("RESTORE_PATH_CONFLICT")
            shutil.move(str(source),str(origin))
            m["state"]="RESTORED";_atom(state,m)
            return {"status":"RESTORED","path":str(origin)}
