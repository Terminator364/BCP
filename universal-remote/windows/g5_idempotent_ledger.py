"""BCP G5/G6 idempotency journal, local-only foundation.

Device authorization must be verified by the caller. This ledger never
executes commands; it records exactly-once *intent* and refuses blind replay
after interruption. Actual effects may need separate reconciliation.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

KEY=re.compile(r"^[0-9a-f]{32}$")
ACT=re.compile(r"^[a-z][a-z0-9._]{2,63}$")
STATES={"QUEUED","CLAIMED","DONE","FAILED","INTERRUPTED","CANCELED"}

class LedgerError(ValueError):
    pass

def _check_id(value):
    if not isinstance(value,str) or not KEY.fullmatch(value):
        raise LedgerError("INVALID_KEY")
    return value

class ActionLedger:
    def __init__(self,dbpath):
        self.path=Path(dbpath)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests(
                id TEXT PRIMARY KEY, device TEXT NOT NULL, operation TEXT NOT NULL,
                fingerprint TEXT NOT NULL, state TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL,
                result_digest TEXT)""")
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.path,timeout=12)
        try:
            db.execute("PRAGMA busy_timeout=12000")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def _fingerprint(self,action,arguments):
        try:
            canonical=json.dumps({"operation":action,"args":arguments},
                                 sort_keys=True,ensure_ascii=False,
                                 separators=(",",":"),allow_nan=False)
        except (TypeError,ValueError) as err:
            raise LedgerError("ARGS_NOT_SERIALIZABLE") from err
        if len(canonical.encode("utf8"))>300000:
            raise LedgerError("PER_REQUEST_PAYLOAD_TOO_LARGE")
        return hashlib.sha256(canonical.encode("utf8")).hexdigest()
    def offer(self,device,request_id,action,args):
        _check_id(device);_check_id(request_id)
        if not isinstance(action,str) or not ACT.fullmatch(action):
            raise LedgerError("ACTION_INVALID")
        fp=self._fingerprint(action,args)
        now=time.time()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("""SELECT device,operation,fingerprint,state
                           FROM requests WHERE id=?""",(request_id,)).fetchone()
            if row:
                if row[:3]!=(device,action,fp):
                    raise LedgerError("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST")
                return {"request_id":request_id,"state":row[3],"created":False}
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?)",
                (request_id,device,action,fp,"QUEUED",now,now,None))
            return {"request_id":request_id,"state":"QUEUED","created":True}
    def _row(self,db,device,request_id):
        _check_id(device);_check_id(request_id)
        row=db.execute("SELECT device,state,result_digest FROM requests WHERE id=?",
                       (request_id,)).fetchone()
        if row is None or row[0]!=device:raise LedgerError("REQUEST_NOT_OWNED")
        return row
    def claim(self,device,request_id):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,device,request_id)
            if row[1]!="QUEUED":raise LedgerError("REQUEST_NOT_CLAIMABLE")
            db.execute("UPDATE requests SET state='CLAIMED',updated=? WHERE id=?",
                       (time.time(),request_id))
            return {"request_id":request_id,"state":"CLAIMED"}
    def complete(self,device,request_id,success,result_sha256):
        if type(success)!=bool or not isinstance(result_sha256,str) or not re.fullmatch(r"[0-9a-f]{64}",result_sha256):
            raise LedgerError("INVALID_COMPLETION")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row=self._row(db,device,request_id)
            if row[1]!="CLAIMED":raise LedgerError("REQUEST_NOT_ACTIVE")
            state="DONE" if success else "FAILED"
            db.execute("UPDATE requests SET state=?,updated=?,result_digest=? WHERE id=?",
                       (state,time.time(),result_sha256,request_id))
            return {"request_id":request_id,"state":state}
    def status(self,device,request_id):
        with self._db() as db:
            row=self._row(db,device,request_id)
            return {"request_id":request_id,"state":row[1],
                    "result_sha256":row[2]}
    def recover(self):
        with self._db() as db:
            count=db.execute("UPDATE requests SET state='INTERRUPTED',updated=? "
                             "WHERE state='CLAIMED'",(time.time(),)).rowcount
        return {"interrupted":count,"blind_replays":0}
