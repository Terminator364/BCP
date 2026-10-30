"""BCP G4 local scoped-session tests; ephemeral key, no real user grant created."""
from pathlib import Path
import json,os,secrets,sys,tempfile,time,threading
sys.path.insert(0,str(Path(os.environ["LOCALAPPDATA"])/"BCP-Universal-Remote"))
import g4_scoped_sessions as s
import g4_agent as g

checks={}
def ck(name,condition):
    checks[name]=bool(condition)
    if not condition:raise AssertionError(name)
def denied(name,fn):
    try:fn()
    except ValueError:ck(name,True)
    else:ck(name,False)

root=g.ROOT/"G4-Staging-Workspace"
root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="scope-unit-",dir=str(root)) as work:
    base=Path(work)
    scope=base/"approved-scope"
    scope.mkdir()
    secret=secrets.token_bytes(32)
    grantdir=base/"private-test-grants"
    def spec(**kwargs):
        params={"kind":"grant_session","root":str(scope),"actions":["mkdir","write_text_new"],
                "duration_seconds":300,"max_operations":3,"max_total_bytes":30}
        params.update(kwargs)
        return s.make_grant_spec(params,g.safe_target)
    denied("reject_home_scope",lambda:s.make_grant_spec({"kind":"grant_session",
        "root":str(Path.home()),"actions":["mkdir"]},g.safe_target))
    denied("reject_outside_home",lambda:s.make_grant_spec({"kind":"grant_session",
        "root":"C:\\Windows","actions":["mkdir"]},g.safe_target))
    denied("reject_unsafe_run",lambda:spec(actions=["run"]))
    denied("reject_unsafe_delete",lambda:spec(actions=["delete"]))
    denied("reject_long_permission",lambda:spec(duration_seconds=3600))
    denied("reject_many_operations",lambda:spec(max_operations=50))
    denied("reject_excess_bytes",lambda:spec(max_total_bytes=1000000))
    approved=spec()
    ck("valid_scoped_spec",approved["actions"]==["mkdir","write_text_new"])
    ident=secrets.token_hex(16)
    result=s.issue(ident,approved,secret,grantdir,g.json_atomic)
    ck("grant_is_active",result["state"]=="ACTIVE")
    denied("prevent_duplicate_grant",lambda:s.issue(ident,approved,secret,grantdir,g.json_atomic))
    def change(path,kind,txt=None,uid=None):
        payload={"grant_id":ident,"operation_id":uid or secrets.token_hex(16),
                 "kind":kind,"path":str(path)}
        if txt is not None:payload["text"]=txt
        return s.apply(payload,secret,grantdir,g.json_atomic,g.safe_target,
                       lambda *args:None)
    denied("reject_run_under_scope",lambda:change(scope/"a.exe","run"))
    denied("reject_escape",lambda:change(base/"escape.txt","write_text_new","x"))
    denied("reject_dotdot",lambda:change(scope/".."/"escape.txt","write_text_new","x"))
    denied("reject_executable_file",lambda:change(scope/"bad.ps1","write_text_new","x"))
    denied("reject_invalid_opid",lambda:s.apply({"grant_id":ident,"operation_id":"X",
        "kind":"mkdir","path":str(scope/"dir")},secret,grantdir,g.json_atomic,g.safe_target,lambda *a:None))
    uid=secrets.token_hex(16)
    response=change(scope/"hello.txt","write_text_new","hello",uid)
    ck("first_write_exact",response["status"]=="DONE" and (scope/"hello.txt").read_text()=="hello")
    denied("reject_operation_replay",lambda:change(scope/"another.txt","write_text_new","x",uid))
    denied("deny_overwrite",lambda:change(scope/"hello.txt","write_text_new","other"))
    res=change(scope/"fresh-folder","mkdir")
    ck("create_directory",res["status"]=="DONE" and (scope/"fresh-folder").is_dir())
    res=change(scope/"final.md","write_text_new","1234")
    ck("third_operation",res["remaining"]==0)
    denied("operation_quota",lambda:change(scope/"fourth.md","write_text_new","x"))
    ck("quota_never_exceeded",s.status(ident,secret,grantdir)["operations_left"]==0)
    denied("tamper_mac",lambda:(
      (grantdir/(ident+".json")).write_text(json.dumps({"id":ident,"state":"ACTIVE","mac":"0"*64})),
      s.status(ident,secret,grantdir)))
    # Use separate lab grant for expiry and revocation.
    for suffix,force in (("exp",True),("rev",False)):
        extra=secrets.token_hex(16)
        s.issue(extra,approved,secret,grantdir,g.json_atomic)
        file=grantdir/(extra+".json")
        if force:
            state=json.loads(file.read_text())
            state["expires"]=int(time.time())-10
            g.json_atomic(file,{**state,"mac":s._signed(state,secret)})
            denied("expiry_denied",lambda:s.apply({
              "grant_id":extra,"operation_id":secrets.token_hex(16),"kind":"mkdir",
              "path":str(scope/"expired")},secret,grantdir,g.json_atomic,g.safe_target,lambda *a:None))
        else:
            ack=s.revoke(extra,secret,grantdir,g.json_atomic)
            ck("explicit_revocation",ack["state"]=="REVOKED")
            denied("revoked_denied",lambda:s.apply({
              "grant_id":extra,"operation_id":secrets.token_hex(16),"kind":"mkdir",
              "path":str(scope/"revoked")},secret,grantdir,g.json_atomic,g.safe_target,lambda *a:None))
    # A reparse point must not escape the approved scope.
    external=base/"other"
    external.mkdir()
    link=scope/"junction"
    try:
        os.symlink(str(external),str(link),target_is_directory=True)
    except (OSError,NotImplementedError):
        checks["reparse_escape_denied"]=None
    else:
        denied("reparse_escape_denied",lambda:s._path_check(
           str(link/"out.txt"),str(scope),"write_text_new",g.safe_target))
    # Create a private lock; the system must fail closed under competing writers.
    fresh=secrets.token_hex(16)
    s.issue(fresh,approved,secret,grantdir,g.json_atomic)
    busy=grantdir/(fresh+".lock")
    busy.touch(exist_ok=False)
    denied("concurrent_lock_denied",lambda:s.apply({
        "grant_id":fresh,"operation_id":secrets.token_hex(16),
        "kind":"mkdir","path":str(scope/"busy")},secret,grantdir,g.json_atomic,g.safe_target,lambda *a:None))
    busy.unlink()

print(json.dumps({"schema":"BCP_G4_SCOPED_UNIT_V1","checks":checks,
                 "passed":sum(x is True for x in checks.values()),
                 "skipped":sum(x is None for x in checks.values()),
                 "failed":[k for k,v in checks.items() if v is False],
                 "all_pass":all(x is not False for x in checks.values()),
                 "real_approval_created":False},indent=2))
