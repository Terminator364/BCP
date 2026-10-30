"""BCP Universal Remote G4 — authenticated, user-authorized Windows command gateway.
Staging ONLY on 127.0.0.1:8910; never expose on LAN/Tailscale until reviewed.
Uses existing G2 TLS certificate + HMAC/nonce ledger. No admin elevation or silent UAC.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
LEGACY=Path(os.environ["LOCALAPPDATA"])/"BCP-USB-Rescue"
sys.path.insert(0,str(LEGACY/"windows"))
from bridge_agent import Bridge, compact  # existing HMAC, SQLite nonce anti-replay + audit

PORT=8910
MAX_BODY=128*1024
MAX_FILE=256*1024
MAX_LIST=100
MAX_PROCESS=80
TICKET_RE=re.compile(r"^[a-f0-9]{32}$")
ROOT_PRIVATE=ROOT/"private-state"
G4=ROOT_PRIVATE/"g4"
APPROVAL_KEY=G4/"approval-seal.key"
PENDING=G4/"pending"
BACKUPS=G4/"backups"
SENSITIVE={
    "private-state",".ssh",".aws",".gnupg",".kube",".git-credentials",
    "credentials","vault","login data","cookies","key4.db","signons.sqlite",
    "recovery keys","passwords","sam","security","system"
}
ENDPOINTS={
 "/v1/g4/capabilities":"capabilities",
 "/v1/g4/system":"system",
 "/v1/g4/files/list":"list",
 "/v1/g4/files/read":"read",
 "/v1/g4/processes":"processes",
 "/v1/g4/changes/prepare":"prepare",
 "/v1/g4/changes/status":"ticket_status",
 "/v1/g4/changes/commit":"commit",
 "/v1/g4/audit":"audit"
}

def utc():
    return datetime.now(timezone.utc).isoformat()

def ensure_private(path):
    path.mkdir(parents=True,exist_ok=True)
    if os.name=="nt":
        username=os.environ.get("USERNAME","")
        if username:
            subprocess.run(["icacls",str(path),"/inheritance:r","/grant:r",username+":(OI)(CI)F"],
                           timeout=10,check=True,capture_output=True)

def json_atomic(path,obj):
    temp=path.with_name(path.name+"."+secrets.token_hex(4)+".tmp")
    try:
        with temp.open("x",encoding="utf8") as out:
            json.dump(obj,out,ensure_ascii=False,separators=(",",":"))
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def spec_fingerprint(item):
    # Consent is tied to ticket identity, exact action and immutable spec.
    data={"id":item["id"],"kind":item["kind"],"expires":item["expires"],
          "spec":item["spec"]}
    raw=json.dumps(data,sort_keys=True,ensure_ascii=False,
                   separators=(",",":")).encode("utf8")
    return hashlib.sha256(raw).hexdigest()

def approval_seal(item,secret):
    if not isinstance(item.get("approved_at"),int):
        raise ValueError("INVALID_APPROVAL_TIME")
    material="|".join((item["id"],spec_fingerprint(item),
                        str(item["approved_at"]))).encode("ascii")
    return hmac.new(secret,material,hashlib.sha256).hexdigest()

def verified_approval(item,secret):
    if item.get("status")!="APPROVED":return False
    expected=item.get("approval_seal","")
    if not isinstance(expected,str) or not re.fullmatch(r"[0-9a-f]{64}",expected):
        return False
    if not isinstance(item.get("approved_at"),int):
        return False
    if not item["created"]<=item["approved_at"]<=item["expires"]:
        return False
    return hmac.compare_digest(expected,approval_seal(item,secret))

def safe_target(raw,create=False):
    if not isinstance(raw,str) or not (3<=len(raw)<=512) or "\x00" in raw:
        raise ValueError("BAD_ABSOLUTE_PATH")
    p=Path(raw)
    if not p.is_absolute():raise ValueError("ABSOLUTE_PATH_REQUIRED")
    resolved=p.resolve(strict=False)
    if any(part.casefold() in SENSITIVE for part in resolved.parts):
        raise ValueError("PROTECTED_PATH")
    if str(resolved).lower().startswith(str(ROOT_PRIVATE.resolve()).lower()):
        raise ValueError("PRIVATE_STATE_DENIED")
    if create and not resolved.parent.is_dir():raise ValueError("PARENT_NOT_FOUND")
    return resolved

class G4Bridge(Bridge):
    def __init__(self):
        ensure_private(G4);ensure_private(PENDING);ensure_private(BACKUPS)
        if not APPROVAL_KEY.is_file():
            with APPROVAL_KEY.open("xb") as fp:
                fp.write(secrets.token_bytes(32))
            if os.name=="nt":
                username=os.environ.get("USERNAME","")
                if username:
                    subprocess.run(["icacls",str(APPROVAL_KEY),"/inheritance:r",
                      "/grant:r",username+":F"],capture_output=True,check=True,timeout=10)
        self.approval_key=APPROVAL_KEY.read_bytes()
        if len(self.approval_key)!=32:raise RuntimeError("APPROVAL_KEY_INVALID")
        super().__init__(LEGACY/"private-state",ROOT/"G4-Staging-Workspace")
        self.ticket_lock=threading.RLock()
    def operate(self,action,payload):
        if not isinstance(payload,dict):raise ValueError("INVALID_PAYLOAD")
        if action=="capabilities":
            return {"schema":"BCP_G4_V1","phase":"STAGING_LOCALHOST_ONLY",
                    "authenticated":True,"user":os.environ.get("USERNAME"),
                    "read":["system","processes","files/list","files/read","audit"],
                    "mutations":["write_text","mkdir","run"],
                    "mutation_requires":"Windows_local_confirmation_and_HMAC_seal",
                    "elevation":False,"transport":"TLS_1_2_PLUS_HMAC"}
        if action=="system":
            home=Path.home()
            usage=shutil.disk_usage(home)
            return {"host":socket.gethostname(),"os":platform.system(),
                    "os_release":platform.release(),"architecture":platform.machine(),
                    "python":platform.python_version(),"user":os.environ.get("USERNAME"),
                    "home":str(home),"disk_home_free_bytes":usage.free,
                    "disk_home_total_bytes":usage.total,
                    "running_as_admin":False}
        if action=="list":
            p=safe_target(payload.get("path"))
            if not p.is_dir():raise ValueError("NOT_A_DIRECTORY")
            entries=[]
            for child in sorted(p.iterdir(),key=lambda x:x.name.casefold()):
                if len(entries)>=MAX_LIST:break
                try:
                    if any(segment.casefold() in SENSITIVE for segment in child.parts):
                        continue
                    stat=child.stat()
                    entries.append({"name":child.name,"kind":"dir" if child.is_dir() else "file",
                                    "bytes":stat.st_size if child.is_file() else None})
                except (OSError,ValueError):continue
            return {"path":str(p),"entries":entries,"limit":MAX_LIST}
        if action=="read":
            p=safe_target(payload.get("path"))
            if not p.is_file():raise ValueError("NOT_A_FILE")
            size=p.stat().st_size
            if size>MAX_FILE:raise ValueError("FILE_TOO_LARGE")
            raw=p.read_bytes()
            content=raw.decode("utf8")
            return {"path":str(p),"text":content,"bytes":len(raw),
                    "sha256":hashlib.sha256(raw).hexdigest()}
        if action=="processes":
            if platform.system()!="Windows":return {"items":[],"error":"WINDOWS_ONLY"}
            result=subprocess.run(["tasklist.exe","/FO","CSV","/NH"],capture_output=True,
                                  text=True,timeout=12,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if result.returncode!=0:raise ValueError("TASKLIST_FAILED")
            rows=list(csv.reader(io.StringIO(result.stdout)))
            return {"items":[{"name":x[0],"pid":x[1]} for x in rows[:MAX_PROCESS] if len(x)>=2],
                    "limit":MAX_PROCESS}
        if action=="audit":
            with self.db() as db:
                rows=db.execute("SELECT at,action,result FROM actions ORDER BY id DESC LIMIT 40").fetchall()
            return {"items":[{"unix":a,"operation":b,"result":c} for a,b,c in rows]}
        if action=="prepare":
            return self.prepare(payload)
        if action=="ticket_status":
            ticket=self.read_ticket(payload.get("ticket"))
            return {"ticket":ticket["id"],"kind":ticket["kind"],
                    "status":ticket["status"],"expires":ticket["expires"]}
        if action=="commit":
            return self.commit(payload)
        raise ValueError("UNKNOWN_CAPABILITY")
    def make_spec(self,payload):
        kind=payload.get("kind")
        if kind=="write_text":
            path=safe_target(payload.get("path"),create=True)
            txt=payload.get("text")
            if not isinstance(txt,str) or len(txt.encode("utf8"))>64*1024:
                raise ValueError("WRITE_CONTENT_INVALID")
            if path.is_dir():raise ValueError("PATH_IS_DIRECTORY")
            existing=path.read_bytes() if path.is_file() else None
            if existing is not None and len(existing)>MAX_FILE:raise ValueError("EXISTING_TOO_LARGE")
            expected=hashlib.sha256(existing).hexdigest() if existing is not None else None
            return {"kind":kind,"path":str(path),"text":txt,"expected":expected}
        if kind=="mkdir":
            path=safe_target(payload.get("path"),create=True)
            if path.exists():raise ValueError("ALREADY_EXISTS")
            return {"kind":kind,"path":str(path)}
        if kind=="run":
            exe=payload.get("exe")
            args=payload.get("args",[])
            if not isinstance(exe,str) or not isinstance(args,list) or len(args)>24 or any(
               not isinstance(a,str) or len(a)>350 or "\x00" in a for a in args):
                raise ValueError("BAD_COMMAND")
            if len(exe)>512 or "\x00" in exe:raise ValueError("BAD_EXECUTABLE")
            path=Path(exe)
            if not path.is_absolute() or not path.is_file():raise ValueError("EXECUTABLE_MUST_EXIST")
            return {"kind":kind,"exe":str(path.resolve()),"args":args}
        raise ValueError("UNSUPPORTED_CHANGE")
    def prepare(self,payload):
        spec=self.make_spec(payload)
        ident=secrets.token_hex(16)
        item={"id":ident,"kind":spec["kind"],"spec":spec,
              "created":int(time.time()),"expires":int(time.time())+300,
              "status":"PENDING","approved_at":None}
        with self.ticket_lock:
            json_atomic(PENDING/(ident+".json"),item)
        return {"ticket":ident,"kind":spec["kind"],
                "expires":item["expires"],"status":"PENDING",
                "approval":"Run BCP G4 Approval Center on signed-in Windows"}
    def read_ticket(self,ident):
        if not isinstance(ident,str) or not TICKET_RE.fullmatch(ident):
            raise ValueError("BAD_TICKET")
        file=PENDING/(ident+".json")
        if not file.is_file():raise ValueError("TICKET_NOT_FOUND")
        item=json.loads(file.read_text("utf8"))
        if item.get("id")!=ident:raise ValueError("TICKET_CORRUPT")
        return item
    def commit(self,payload):
        ident=payload.get("ticket")
        with self.ticket_lock:
            item=self.read_ticket(ident)
            if (not verified_approval(item,self.approval_key) or
                int(time.time())>item["expires"]):
                raise ValueError("LOCAL_APPROVAL_REQUIRED")
            item["status"]="EXECUTING"
            json_atomic(PENDING/(ident+".json"),item)
        try:
            spec=item["spec"]
            if spec["kind"]=="write_text":
                p=safe_target(spec["path"],create=True)
                raw=spec["text"].encode("utf8")
                prior=p.read_bytes() if p.is_file() else None
                oldhash=hashlib.sha256(prior).hexdigest() if prior is not None else None
                if oldhash!=spec["expected"]:raise ValueError("FILE_CHANGED_SINCE_APPROVAL")
                if prior is not None:
                    backup=BACKUPS/(ident+".bak")
                    with backup.open("xb") as b:b.write(prior)
                part=p.with_name("."+p.name+"."+ident+".tmp")
                try:
                    with part.open("xb") as f:f.write(raw)
                    os.replace(part,p)
                finally:
                    if part.exists():part.unlink()
                result={"path":str(p),"bytes":len(raw),
                        "sha256":hashlib.sha256(raw).hexdigest(),
                        "backup":ident+".bak" if prior is not None else None}
            elif spec["kind"]=="mkdir":
                p=safe_target(spec["path"],create=True)
                p.mkdir(exist_ok=False)
                result={"created":str(p)}
            elif spec["kind"]=="run":
                env={key:os.environ[key] for key in ("SystemRoot","WINDIR","PATH","TEMP","TMP","USERPROFILE")
                     if key in os.environ}
                proc=subprocess.run([spec["exe"],*spec["args"]],cwd=str(Path.home()),
                                    env=env,capture_output=True,timeout=15,
                                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                result={"returncode":proc.returncode,
                        "stdout":proc.stdout[:65536].decode("utf8","replace"),
                        "stderr":proc.stderr[:16384].decode("utf8","replace"),
                        "truncated":len(proc.stdout)>65536 or len(proc.stderr)>16384}
            else:raise ValueError("UNSUPPORTED_CHANGE")
            state="DONE"
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            result={"error":type(exc).__name__,"reason":str(exc)[:160]}
            state="FAILED"
        with self.ticket_lock:
            item["status"]=state
            item["finished"]=int(time.time())
            json_atomic(PENDING/(ident+".json"),item)
        self.record("g4_"+item["kind"],state,ident)
        return {"ticket":ident,"status":state,"result":result}

def factory(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version="BCP-G4-Staging/1"
        def log_message(self,*args):pass
        def reply(self,status,data,nonce=""):
            body=compact(data)
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("X-Bridge-Signature",bridge.sig(
                nonce+"\n"+str(status)+"\n"+hashlib.sha256(body).hexdigest()))
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if self.path!="/health":return self.reply(404,{"ok":False})
            return self.reply(200,{"ok":True,"stage":"G4_STAGING_LOCALHOST_ONLY"})
        def do_POST(self):
            action=ENDPOINTS.get(self.path)
            nonce=self.headers.get("X-Bridge-Nonce","")
            if not action:return self.reply(404,{"ok":False,"reason":"NOT_FOUND"},nonce)
            try:n=int(self.headers.get("Content-Length","-1"))
            except ValueError:n=-1
            if not 1<=n<=MAX_BODY:return self.reply(413,{"ok":False,"reason":"INVALID_SIZE"},nonce)
            body=self.rfile.read(n)
            err=bridge.authenticate("POST",self.path,self.headers.get("X-Bridge-Time"),
                                    nonce,self.headers.get("X-Bridge-Signature",""),body)
            if err:
                bridge.record("g4_"+action,"DENIED_"+err,nonce[:90])
                return self.reply(401,{"ok":False,"reason":"UNAUTHORIZED"},nonce)
            try:
                data=json.loads(body.decode("utf8"))
                result=bridge.operate(action,data)
                bridge.record("g4_"+action,"SUCCESS",nonce)
                return self.reply(200,{"ok":True,"result":result},nonce)
            except (ValueError,TypeError,UnicodeError,OSError) as exc:
                reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                bridge.record("g4_"+action,"REJECTED_"+reason[:90],nonce)
                return self.reply(400,{"ok":False,"reason":reason[:120]},nonce)
    return Handler

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--bind",default="127.0.0.1")
    ap.add_argument("--port",type=int,default=PORT)
    args=ap.parse_args()
    if args.bind not in ("127.0.0.1",):raise ValueError("G4_STAGING_LOOPBACK_ONLY")
    if not (8910<=args.port<=8919):raise ValueError("STAGING_PORT_REQUIRED")
    bridge=G4Bridge()
    cert=ROOT/"private-state"/"g2-server.crt"
    key=ROOT/"private-state"/"g2-server.key"
    if not cert.is_file() or not key.is_file():raise RuntimeError("G2_CERT_NOT_FOUND")
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert),str(key))
    server=ThreadingHTTPServer((args.bind,args.port),factory(bridge))
    server.daemon_threads=True
    server.socket=ctx.wrap_socket(server.socket,server_side=True)
    print("G4_STAGING_READY https://127.0.0.1:"+str(args.port)+" no_public_access no_automatic_admin",flush=True)
    try:server.serve_forever(poll_interval=.2)
    finally:server.server_close()

if __name__=="__main__":main()
