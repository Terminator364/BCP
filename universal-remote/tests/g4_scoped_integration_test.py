"""BCP G4 integration verification. Synthetic approvals ONLY in isolated test workspace."""
import json,os,secrets,sys,tempfile,threading,time
from pathlib import Path
root=Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"
sys.path.insert(0,str(root))
import g4_agent as g
checks={}
def good(k,condition):
    checks[k]=bool(condition)
    if not condition:raise AssertionError(k)
def denied(k,fn):
    try:fn()
    except ValueError:good(k,True)
    else:good(k,False)
rootdir=root/"G4-Staging-Workspace"
rootdir.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="g4-session-integration-",dir=str(rootdir)) as tmp:
    scope=Path(tmp)/"allowed";scope.mkdir()
    tmp_pending=Path(tmp)/"pending";tmp_pending.mkdir()
    tmp_grants=Path(tmp)/"grants";tmp_grants.mkdir()
    origP,origG=g.PENDING,g.GRANTS
    g.PENDING,g.GRANTS=tmp_pending,tmp_grants
    logs=[]
    try:
        agent=object.__new__(g.G4Bridge)
        agent.approval_key=secrets.token_bytes(32)
        agent.ticket_lock=threading.RLock()
        agent.record=lambda *a:logs.append(a)
        spec={"kind":"grant_session","root":str(scope),
              "actions":["mkdir","write_text_new"],
              "duration_seconds":300,"max_operations":3,
              "max_total_bytes":100}
        prepared=agent.operate("prepare",spec)
        ticket=prepared["ticket"]
        good("prepared_only",prepared["status"]=="PENDING")
        good("not_issued_without_consent",not (tmp_grants/(ticket+".json")).exists())
        denied("commit_without_approval_denied",lambda:agent.operate("commit",{"ticket":ticket}))
        pending=tmp_pending/(ticket+".json")
        item=json.loads(pending.read_text("utf8"))
        item["status"]="APPROVED";item["approved_at"]=int(time.time())
        item["approval_seal"]=g.approval_seal(item,agent.approval_key)
        g.json_atomic(pending,item)
        grant=agent.operate("commit",{"ticket":ticket})
        good("grant_issued_after_local_style_approval",
             grant["status"]=="DONE" and grant["result"]["state"]=="ACTIVE")
        denied("old_approval_not_replayable",lambda:agent.operate("commit",{"ticket":ticket}))
        good("active_grant_details",
             agent.operate("session_status",{"grant_id":ticket})["operations_left"]==3)
        first=agent.operate("session_use",{"grant_id":ticket,"operation_id":secrets.token_hex(16),
              "kind":"write_text_new","path":str(scope/"test.md"),"text":"Hello G4"})
        good("write_under_scope_after_grant",first["status"]=="DONE" and
             (scope/"test.md").read_text("utf8")=="Hello G4")
        second=agent.operate("session_use",{"grant_id":ticket,"operation_id":secrets.token_hex(16),
              "kind":"mkdir","path":str(scope/"created")})
        good("mkdir_under_scope_after_grant",second["status"]=="DONE" and
             (scope/"created").is_dir())
        denied("cannot_write_outside_scope",lambda:agent.operate("session_use",{
             "grant_id":ticket,"operation_id":secrets.token_hex(16),
             "kind":"write_text_new","path":str(Path(tmp)/"escape.md"),"text":"No"}))
        denied("cannot_overwrite",lambda:agent.operate("session_use",{
             "grant_id":ticket,"operation_id":secrets.token_hex(16),
             "kind":"write_text_new","path":str(scope/"test.md"),"text":"No"}))
        denied("cannot_run",lambda:agent.operate("session_use",{
             "grant_id":ticket,"operation_id":secrets.token_hex(16),
             "kind":"run","path":str(scope/"exe.exe")}))
        revoke=agent.operate("session_revoke",{"grant_id":ticket})
        good("revoked",revoke["state"]=="REVOKED")
        denied("cannot_use_revoked_grant",lambda:agent.operate("session_use",{
             "grant_id":ticket,"operation_id":secrets.token_hex(16),
             "kind":"mkdir","path":str(scope/"should-not-exist")}))
        good("no_revoked_write",(scope/"should-not-exist").exists() is False)
        good("audit_includes_actions",len([v for v in logs if v[0].startswith("g4_session")])>=3)
    finally:
        g.PENDING,g.GRANTS=origP,origG
print(json.dumps({"schema":"BCP_G4_ISOLATED_SESSION_END2END","checks":checks,
                  "passed":sum(checks.values()),"PASS":all(checks.values()),
                  "real_approval":False,"production_grants_issued":False},indent=2))
