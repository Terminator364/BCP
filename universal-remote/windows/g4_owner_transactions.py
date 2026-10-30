"""BCP G4 owner-bound file transactions.

A narrowly-scoped staging adapter. It must only be called after the network
layer authenticates an individual device HMAC, not from legacy G2 pairing.
No HTTP route is installed by this module. No owner privilege is minted here.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

from g4_full_files import FileTransactions
from g4_owner_gateway import _guard_path
from g4_owner_trust import OwnerTrust,TrustError

HEX32=re.compile(r"^[0-9a-f]{32}$")

class TransactionAuthError(PermissionError):
    pass

def owner_hash(device_id):
    if not isinstance(device_id,str) or not HEX32.fullmatch(device_id):
        raise TransactionAuthError("DEVICE_ID_INVALID")
    return hashlib.sha256(("BCP_DEVICE_V1:"+device_id).encode("ascii")).hexdigest()

class OwnerFileService:
    def __init__(self,root:Path,policy:OwnerTrust,registry):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.fileengine=FileTransactions(self.root/"transactions")
        self.policy=policy
        self.registry=registry
        self.dbpath=self.root/"owner-transfers.sqlite"
        self.lock=threading.RLock()
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS ownership("
                       "transfer TEXT PRIMARY KEY, device TEXT NOT NULL,"
                       "created INTEGER NOT NULL)")
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.dbpath,timeout=15)
        try:
            db.execute("PRAGMA busy_timeout=15000")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def _authorize(self,device_id):
        ident=owner_hash(device_id)
        active=any(item["device_id"]==device_id and item["revoked"] is False
                   for item in self.registry.enrolled_public())
        if not active:
            raise TransactionAuthError("DEVICE_IDENTITY_NOT_ACTIVE")
        self.policy.authorize(ident,"files.write")
        return ident
    def _owner(self,device_id,transfer):
        self._authorize(device_id)
        if not isinstance(transfer,str) or not HEX32.fullmatch(transfer):
            raise TransactionAuthError("TRANSFER_ID_INVALID")
        with self._db() as db:
            row=db.execute("SELECT device FROM ownership WHERE transfer=?",
                           (transfer,)).fetchone()
        if row is None or row[0]!=device_id:
            raise TransactionAuthError("TRANSACTION_NOT_OWNED_BY_DEVICE")
    def begin(self,device_id,destination,overwrite=False,expected_old_sha=None):
        self._authorize(device_id)
        safe=_guard_path(destination)
        with self.lock:
            tx=self.fileengine.begin(str(safe),overwrite,expected_old_sha)
            try:
                with self._db() as db:
                    db.execute("INSERT INTO ownership VALUES(?,?,?)",
                               (tx["upload_id"],device_id,int(time.time())))
            except Exception:
                self.fileengine.abort(tx["upload_id"])
                raise
            return tx
    def append(self,device_id,transfer,offset,data_base64,chunk_sha256=None):
        with self.lock:
            self._owner(device_id,transfer)
            return self.fileengine.append(transfer,offset,data_base64,chunk_sha256)
    def status(self,device_id,transfer):
        with self.lock:
            self._owner(device_id,transfer)
            _,item=self.fileengine._metadata(transfer)
            return {"upload_id":transfer,"state":item["state"],
                    "offset":item["uploaded"],"path":item["destination"]}
    def commit(self,device_id,transfer,sha256):
        with self.lock:
            self._owner(device_id,transfer)
            _,record=self.fileengine._metadata(transfer)
            # Path guard is repeated to catch links/sensitive changes made
            # between begin and commit (OS-level ACLs remain authoritative).
            checked=_guard_path(record["destination"])
            if str(checked)!=str(Path(record["destination"])):
                raise TransactionAuthError("DESTINATION_PATH_CHANGED")
            return self.fileengine.commit(transfer,sha256)
    def abort(self,device_id,transfer):
        with self.lock:
            self._owner(device_id,transfer)
            return self.fileengine.abort(transfer)
