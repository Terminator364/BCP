"""BCP durable Windows task queue, independent of G2 server restarts.

Local worker only; caller must authenticate owner before enqueueing via future API.
No artificial total-operation count or 15-second job lifetime.
Concurrency is a machine-resource budget, NOT a capacity or ownership limit.
"""
from __future__ import annotations
import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import time

CHUNK=65536
ID=re.compile(r"^[a-f0-9]{32}$")
STATES=frozenset(("QUEUED","STARTING","RUNNING","DONE","FAILED",
                  "CANCELED","BLOCKED","INTERRUPTED"))

class JobError(ValueError):
    pass

class DurableJobs:
    def __init__(self,root):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.dbfile=self.root/"jobs.sqlite"
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, created REAL, updated REAL,
                executable TEXT, args_json TEXT, cwd TEXT, depends_json TEXT,
                state TEXT, pid INTEGER, returncode INTEGER,
                cancel_requested INTEGER NOT NULL DEFAULT 0)""")
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.dbfile,timeout=20)
        try:
            db.execute("PRAGMA busy_timeout=20000")
            db.execute("PRAGMA journal_mode=WAL")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def enqueue(self,executable,args=None,cwd=None,depends=None):
        p=Path(executable) if isinstance(executable,str) else None
        if p is None or not p.is_absolute() or not p.is_file():
            raise JobError("ABSOLUTE_EXISTING_EXECUTABLE_REQUIRED")
        args=args if args is not None else []
        if not isinstance(args,list) or any(not isinstance(x,str) or "\x00" in x for x in args):
            raise JobError("ARGUMENT_LIST_INVALID")
        wd=Path(cwd) if cwd else Path.home()
        if not wd.is_absolute() or not wd.is_dir():
            raise JobError("WORKING_DIRECTORY_INVALID")
        depends=depends if depends is not None else []
        if not isinstance(depends,list) or len(set(depends))!=len(depends) or any(
                not isinstance(x,str) or not ID.fullmatch(x) for x in depends):
            raise JobError("DEPENDENCIES_INVALID")
        ident=secrets.token_hex(16)
        now=time.time()
        with self._db() as db:
            for parent in depends:
                if db.execute("SELECT 1 FROM jobs WHERE id=?",(parent,)).fetchone() is None:
                    raise JobError("DEPENDENCY_NOT_FOUND")
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (ident,now,now,str(p),json.dumps(args),str(wd),
                 json.dumps(depends),"QUEUED",None,None,0))
        return {"job_id":ident,"state":"QUEUED","dependencies":depends}
    def recover(self):
        # A worker may have crashed while a child was running. Never rerun
        # such jobs blindly: duplicate execution may corrupt user files.
        with self._db() as db:
            count=db.execute("""UPDATE jobs SET state='INTERRUPTED',updated=?
                   WHERE state IN ('STARTING','RUNNING')""",(time.time(),)).rowcount
        return {"interrupted":count,"queued_preserved":True}
    def _claim(self):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            queued=db.execute("""SELECT id,executable,args_json,cwd,depends_json
                                  FROM jobs WHERE state='QUEUED'
                                  ORDER BY created ASC""").fetchall()
            for ident,exe,raw_args,cwd,dependencies in queued:
                parents=json.loads(dependencies)
                if parents:
                    values=[db.execute("SELECT state FROM jobs WHERE id=?",(p,)).fetchone()
                            for p in parents]
                    if any(v is None or v[0] in ("FAILED","CANCELED","BLOCKED","INTERRUPTED")
                           for v in values):
                        db.execute("UPDATE jobs SET state='BLOCKED',updated=? WHERE id=?",
                                   (time.time(),ident))
                        continue
                    if not all(v[0]=="DONE" for v in values):
                        continue
                db.execute("UPDATE jobs SET state='STARTING',updated=? WHERE id=?",
                           (time.time(),ident))
                return {"job_id":ident,"exe":exe,"args":json.loads(raw_args),"cwd":cwd}
        return None
    def _finish(self,ident,state,code=None,pid=None):
        with self._db() as db:
            db.execute("UPDATE jobs SET state=?,updated=?,returncode=?,pid=COALESCE(?,pid) WHERE id=?",
                       (state,time.time(),code,pid,ident))
    def execute_next(self):
        job=self._claim()
        if job is None:return {"executed":False}
        ident=job["job_id"]
        stdout=self.root/(ident+".stdout")
        stderr=self.root/(ident+".stderr")
        try:
            with stdout.open("xb") as out, stderr.open("xb") as err:
                flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
                proc=subprocess.Popen([job["exe"],*job["args"]],
                    cwd=job["cwd"],stdin=subprocess.DEVNULL,
                    stdout=out,stderr=err,close_fds=True,
                    creationflags=flags)
                with self._db() as db:
                    db.execute("UPDATE jobs SET state='RUNNING',pid=?,updated=? WHERE id=?",
                               (proc.pid,time.time(),ident))
                was_cancelled=False
                while proc.poll() is None:
                    time.sleep(.2)
                    with self._db() as db:
                        row=db.execute("SELECT cancel_requested FROM jobs WHERE id=?",
                                       (ident,)).fetchone()
                    if row and row[0]:
                        proc.terminate()
                        was_cancelled=True
                        try:proc.wait(timeout=4)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        break
                rc=proc.wait()
            final="CANCELED" if was_cancelled else ("DONE" if rc==0 else "FAILED")
            self._finish(ident,final,rc)
            return {"executed":True,"job_id":ident,"state":final,"returncode":rc}
        except (OSError,ValueError,subprocess.SubprocessError):
            self._finish(ident,"FAILED")
            return {"executed":True,"job_id":ident,"state":"FAILED"}
    def cancel(self,ident):
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            raise JobError("JOB_ID_INVALID")
        with self._db() as db:
            row=db.execute("SELECT state FROM jobs WHERE id=?",(ident,)).fetchone()
            if row is None:raise JobError("JOB_NOT_FOUND")
            state=row[0]
            if state=="QUEUED":
                db.execute("UPDATE jobs SET state='CANCELED',updated=? WHERE id=?",
                           (time.time(),ident))
                return {"job_id":ident,"state":"CANCELED"}
            if state in ("RUNNING","STARTING"):
                db.execute("UPDATE jobs SET cancel_requested=1,updated=? WHERE id=?",
                           (time.time(),ident))
                return {"job_id":ident,"state":"CANCELLATION_REQUESTED"}
            return {"job_id":ident,"state":state}
    def status(self,ident):
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            raise JobError("JOB_ID_INVALID")
        with self._db() as db:
            row=db.execute("""SELECT id,created,updated,state,pid,returncode,
                                   cancel_requested FROM jobs WHERE id=?""",
                           (ident,)).fetchone()
        if row is None:raise JobError("JOB_NOT_FOUND")
        names=("job_id","created","updated","state","pid","returncode","cancel_requested")
        return dict(zip(names,row))
    def list(self,cursor=0,page_size=50):
        if type(cursor)!=int or cursor<0 or type(page_size)!=int or not 1<=page_size<=100:
            raise JobError("PAGE_INVALID")
        with self._db() as db:
            rows=db.execute("""SELECT id,state,created,updated,returncode FROM jobs
                                ORDER BY created ASC LIMIT ? OFFSET ?""",
                            (page_size+1,cursor)).fetchall()
        return {"jobs":[dict(zip(("job_id","state","created","updated","returncode"),r))
                        for r in rows[:page_size]],
                "next_cursor":cursor+page_size if len(rows)>page_size else None}
    def output(self,ident,channel="stdout",offset=0,length=CHUNK):
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            raise JobError("JOB_ID_INVALID")
        self.status(ident)
        if channel not in ("stdout","stderr"):raise JobError("CHANNEL_INVALID")
        if type(offset)!=int or offset<0 or type(length)!=int or not 1<=length<=CHUNK:
            raise JobError("CHUNK_INVALID")
        path=self.root/(ident+"."+channel)
        if not path.is_file():
            return {"data_base64":"","size":0,"next_offset":None}
        import base64
        with path.open("rb") as stream:
            stream.seek(offset);part=stream.read(length)
            size=stream.seek(0,os.SEEK_END)
        return {"data_base64":base64.b64encode(part).decode("ascii"),
                "size":size,"next_offset":offset+len(part) if offset+len(part)<size else None}
    def supervisor(self,interval=1):
        self.recover()
        while True:
            result=self.execute_next()
            if not result["executed"]:time.sleep(interval)
