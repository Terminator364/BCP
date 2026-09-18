from __future__ import annotations
import argparse, datetime as dt, hashlib, hmac, json, os, secrets, sqlite3, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
DB_PATH = STATE_DIR / "bcp.sqlite3"
TOKEN_PATH = STATE_DIR / "bcp_token.txt"
DB_LOCK = threading.RLock()

def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def ensure_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        token = secrets.token_urlsafe(32)
        TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
        try: os.chmod(TOKEN_PATH, 0o600)
        except OSError: pass
        print("[BCP] First-run bearer token:", token)
    else:
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    with sqlite3.connect(DB_PATH) as cx:
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=FULL")
        cx.execute("""CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id TEXT NOT NULL, revision INTEGER NOT NULL,
          event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, created_at TEXT NOT NULL,
          prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
          UNIQUE(project_id,idempotency_key), UNIQUE(project_id,revision))""")
        cx.execute("""CREATE TABLE IF NOT EXISTS heads(
          project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
          last_event_id INTEGER NOT NULL, last_event_hash TEXT NOT NULL,
          status TEXT NOT NULL, last_completed_action TEXT NOT NULL,
          next_action TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        cx.commit()
    return token

def connect():
    cx=sqlite3.connect(DB_PATH,timeout=15,isolation_level=None)
    cx.row_factory=sqlite3.Row
    return cx

def get_head(project_id):
    with connect() as cx:
        row=cx.execute("SELECT * FROM heads WHERE project_id=?",(project_id,)).fetchone()
        return dict(row) if row else None

def recent_events(project_id,limit=10):
    limit=max(1,min(int(limit),50))
    with connect() as cx:
        rows=cx.execute("SELECT * FROM events WHERE project_id=? ORDER BY revision DESC LIMIT ?",
                        (project_id,limit)).fetchall()
    out=[]
    for row in reversed(rows):
        d=dict(row); d["payload"]=json.loads(d.pop("payload_json")); out.append(d)
    return out

def commit_event(project_id,event_type,payload,idempotency_key):
    if not project_id or len(project_id)>128: raise ValueError("invalid project_id")
    if not idempotency_key or len(idempotency_key)>200: raise ValueError("invalid idempotency_key")
    created=utc_now()
    with DB_LOCK:
        cx=connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            old=cx.execute("SELECT * FROM events WHERE project_id=? AND idempotency_key=?",
                           (project_id,idempotency_key)).fetchone()
            if old:
                cx.execute("COMMIT")
                return {"result":"ALREADY_COMMITTED","project_id":project_id,
                        "revision":old["revision"],"event_id":old["id"],
                        "event_hash":old["event_hash"],"created_at":old["created_at"]}
            head=cx.execute("SELECT * FROM heads WHERE project_id=?",(project_id,)).fetchone()
            rev=(head["revision"]+1) if head else 1
            prev=head["last_event_hash"] if head else "GENESIS"
            envelope={"project_id":project_id,"revision":rev,"event_type":event_type,
                      "payload":payload,"idempotency_key":idempotency_key,
                      "created_at":created,"prev_hash":prev}
            event_hash=hashlib.sha256(canonical_json(envelope).encode()).hexdigest()
            cur=cx.execute("""INSERT INTO events(project_id,revision,event_type,payload_json,
              idempotency_key,created_at,prev_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)""",
              (project_id,rev,event_type,canonical_json(payload),idempotency_key,created,prev,event_hash))
            status=payload.get("status",head["status"] if head else "ACTIVE")
            done=payload.get("last_completed_action",head["last_completed_action"] if head else "")
            nxt=payload.get("next_action",head["next_action"] if head else "")
            cx.execute("""INSERT INTO heads(project_id,revision,last_event_id,last_event_hash,status,
              last_completed_action,next_action,updated_at) VALUES(?,?,?,?,?,?,?,?)
              ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision,
              last_event_id=excluded.last_event_id,last_event_hash=excluded.last_event_hash,
              status=excluded.status,last_completed_action=excluded.last_completed_action,
              next_action=excluded.next_action,updated_at=excluded.updated_at""",
              (project_id,rev,cur.lastrowid,event_hash,status,done,nxt,created))
            cx.execute("COMMIT")
            return {"result":"COMMITTED","project_id":project_id,"revision":rev,
                    "event_id":cur.lastrowid,"event_hash":event_hash,"created_at":created}
        except Exception:
            try: cx.execute("ROLLBACK")
            except Exception: pass
            raise
        finally: cx.close()

class Handler(BaseHTTPRequestHandler):
    def sendj(self,status,obj):
        data=json.dumps(obj,ensure_ascii=False,indent=2).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(data)
    def auth(self):
        a=self.headers.get("Authorization","")
        return a.startswith("Bearer ") and hmac.compare_digest(a[7:].strip(),self.server.bcp_token)
    def body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n<=0 or n>256000: raise ValueError("invalid body size")
        o=json.loads(self.rfile.read(n).decode())
        if not isinstance(o,dict): raise ValueError("JSON object required")
        return o
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/health": return self.sendj(200,{"ok":True,"service":"BCP PC Node","version":"0.1","time":utc_now()})
        if not self.auth(): return self.sendj(401,{"error":"unauthorized"})
        p=[x for x in path.split("/") if x]
        if len(p)==4 and p[:2]==["v1","projects"] and p[3]=="head":
            return self.sendj(200,{"project_id":p[2],"head":get_head(p[2])})
        if len(p)==4 and p[:2]==["v1","projects"] and p[3]=="resume":
            return self.sendj(200,{"project_id":p[2],"head":get_head(p[2]),"recent_events":recent_events(p[2])})
        self.sendj(404,{"error":"not_found"})
    def do_POST(self):
        path=urlparse(self.path).path
        if not self.auth(): return self.sendj(401,{"error":"unauthorized"})
        p=[x for x in path.split("/") if x]
        if len(p)==4 and p[:2]==["v1","projects"] and p[3]=="events":
            try:
                b=self.body(); payload=b.get("payload",{})
                if not isinstance(payload,dict): raise ValueError("payload must be object")
                idem=self.headers.get("Idempotency-Key") or b.get("idempotency_key")
                if not idem: raise ValueError("Idempotency-Key required")
                return self.sendj(200,commit_event(p[2],str(b.get("type","checkpoint")),payload,str(idem)))
            except Exception as e:
                return self.sendj(400,{"error":"bad_request","detail":str(e)})
        self.sendj(404,{"error":"not_found"})
    def log_message(self,fmt,*args): print("[BCP HTTP]",fmt%args)

def main():
    a=argparse.ArgumentParser(); a.add_argument("--bind",default="127.0.0.1"); a.add_argument("--port",type=int,default=8765)
    args=a.parse_args(); token=ensure_state()
    s=ThreadingHTTPServer((args.bind,args.port),Handler); s.bcp_token=token
    print(f"[BCP] listening on http://{args.bind}:{args.port}")
    try: s.serve_forever(poll_interval=.5)
    except KeyboardInterrupt: pass
    finally: s.server_close()

if __name__=="__main__": main()
