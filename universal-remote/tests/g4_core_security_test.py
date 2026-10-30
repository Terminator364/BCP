"""G4 local-core security audit. Positive approvals are SYNTHETIC TEST ONLY.
No production user approval or G4 remote access is claimed.
"""
from pathlib import Path
import json,sys,time,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import g4_agent as g
b=g.G4Bridge()
checks={}
def check(n,fn):
    try:
        fn()
        checks[n]=True
    except Exception as e:
        checks[n]=type(e).__name__+":"+str(e)[:130]
def requires_rejection(n,fn):
    try:
        fn()
        checks[n]=False
    except (ValueError,OSError) as e:
        checks[n]=True
def must(condition,reason):
    if not condition:raise AssertionError(reason)
sandbox=g.ROOT/"G4-Staging-Workspace"
sandbox.mkdir(parents=True,exist_ok=True)
file=sandbox/"G4_SECURITY_BENCH.txt"
if file.exists():file.unlink()
tickets=[]
try:
    check("capabilities",lambda:must(b.operate("capabilities",{})["phase"]=="STAGING_LOCALHOST_ONLY","phase"))
    check("system",lambda:must(bool(b.operate("system",{})["host"]),"host"))
    check("processes",lambda:must("items" in b.operate("processes",{}),"process"))
    check("list_any_authorized_dir",lambda:must("entries" in b.operate("list",{"path":str(Path.home())}),"listing"))
    requires_rejection("sensitive_private_path_blocked",lambda:b.operate("read",{"path":str(g.APPROVAL_KEY)}))
    requires_rejection("relative_path_denied",lambda:b.operate("list",{"path":"../"}))
    requires_rejection("arbitrary_unknown_action_denied",lambda:b.operate("launch_admin",{}))
    requires_rejection("oversized_write_denied",lambda:b.operate("prepare",{"kind":"write_text","path":str(file),"text":"x"*66000}))
    ticket=b.operate("prepare",{"kind":"write_text","path":str(file),"text":"BCP G4 lab audit\n"})["ticket"]
    tickets.append(ticket)
    p=g.PENDING/(ticket+".json")
    requires_rejection("unapproved_mutation_denied",lambda:b.operate("commit",{"ticket":ticket}))
    item=json.loads(p.read_text("utf8"))
    item["status"]="APPROVED";item["approved_at"]=int(time.time())
    g.json_atomic(p,item)
    requires_rejection("forged_status_no_seal_denied",lambda:b.operate("commit",{"ticket":ticket}))
    item["approval_seal"]=g.approval_seal(item,b.approval_key)
    item["spec"]["text"]="TAMPER ATTEMPT"
    g.json_atomic(p,item)
    requires_rejection("modified_payload_after_seal_denied",lambda:b.operate("commit",{"ticket":ticket}))
    item["spec"]["text"]="BCP G4 lab audit\n"
    item["approval_seal"]=g.approval_seal(item,b.approval_key)
    g.json_atomic(p,item)
    check("synthetically_approved_write_lab",lambda:must(
        b.operate("commit",{"ticket":ticket})["status"]=="DONE" and
        file.read_text("utf8")=="BCP G4 lab audit\n","lab_write"))
    requires_rejection("used_ticket_replay_denied",lambda:b.operate("commit",{"ticket":ticket}))
    check("read_written_file_lab",lambda:must(
        b.operate("read",{"path":str(file)})["sha256"]==hashlib.sha256(file.read_bytes()).hexdigest(),"read"))
    t2=b.operate("prepare",{"kind":"write_text","path":str(file),"text":"Changed after preparing\n"})["ticket"]
    tickets.append(t2)
    v2=b.read_ticket(t2)
    v2["status"]="APPROVED";v2["approved_at"]=int(time.time())
    v2["approval_seal"]=g.approval_seal(v2,b.approval_key)
    g.json_atomic(g.PENDING/(t2+".json"),v2)
    file.write_text("Changed after preparing",encoding="utf8")
    check("file_changed_since_approval_denied",lambda:must(
        b.operate("commit",{"ticket":t2})["status"]=="FAILED","changed-file"))
    # Explicit denied and expired tickets do not run.
    t3=b.operate("prepare",{"kind":"mkdir","path":str(sandbox/"G4_SECURITY_BENCH_DIR")})["ticket"]
    tickets.append(t3)
    t3v=b.read_ticket(t3);t3v["status"]="DENIED";g.json_atomic(g.PENDING/(t3+".json"),t3v)
    requires_rejection("user_denial_respected",lambda:b.operate("commit",{"ticket":t3}))
    check("audit_available",lambda:must("items" in b.operate("audit",{}),"audit"))
finally:
    if file.exists():file.unlink()
    for ticket in tickets:
        p=g.PENDING/(ticket+".json")
        if p.exists():p.unlink()
print(json.dumps({"schema":"BCP_G4_APPROVAL_SECURITY_V1","checks":checks,
                  "passed":sum(v is True for v in checks.values()),
                  "total":len(checks),"PASS":all(v is True for v in checks.values()),
                  "real_windows_user_approval_tested":False},ensure_ascii=False,indent=2))
if not all(v is True for v in checks.values()):raise SystemExit(1)
