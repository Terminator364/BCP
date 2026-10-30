"""Additional G4 constrained Windows execution and approval-seal tests.
All approvals in this script are SYNTHETIC LAB SIMULATIONS, not user consent.
"""
from pathlib import Path
import json,os,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import g4_agent as g
b=g.G4Bridge()
checks={}
base=g.ROOT/"G4-Staging-Workspace"
base.mkdir(parents=True,exist_ok=True)
directory=base/"G4_SECURITY_SECOND_PASS"
target=base/"G4_SECURITY_SECOND_PASS_NOTE.txt"
tickets=[]
backups=[]
def require(bol,label):
    if not bol:raise AssertionError(label)
def verify(name,fn):
    try:fn();checks[name]=True
    except Exception as exc:checks[name]=str(exc)[:120]
def rejected(name,fn):
    try:fn();checks[name]=False
    except (ValueError,OSError):checks[name]=True
def prepare(spec):
    ident=b.operate("prepare",spec)["ticket"]
    tickets.append(ident)
    return ident
def approve_for_lab(ticket):
    p=g.PENDING/(ticket+".json")
    item=b.read_ticket(ticket)
    item["status"]="APPROVED"
    item["approved_at"]=int(time.time())
    item["approval_seal"]=g.approval_seal(item,b.approval_key)
    g.json_atomic(p,item)
try:
    rejected("invalid_exe_not_absolute",lambda:b.operate("prepare",{"kind":"run","exe":"whoami.exe","args":[]}))
    rejected("invalid_exe_missing",lambda:b.operate("prepare",{"kind":"run","exe":"C:\\Windows\\System32\\nonexistent-BCP-7878.exe","args":[]}))
    rejected("invalid_args_type",lambda:b.operate("prepare",{"kind":"run","exe":r"C:\Windows\System32\whoami.exe","args":"-all"}))
    rejected("write_to_private_key_refused",lambda:b.operate("prepare",{"kind":"write_text","path":str(g.APPROVAL_KEY),"text":"bad"}))
    rejected("mkdir_private_dir_refused",lambda:b.operate("prepare",{"kind":"mkdir","path":str(g.G4/"denied-folder")}))
    ticket=prepare({"kind":"mkdir","path":str(directory)})
    rejected("mkdir_before_approval_denied",lambda:b.operate("commit",{"ticket":ticket}))
    approve_for_lab(ticket)
    verify("mkdir_synthetic_local_approval_lab",lambda:require(
        b.operate("commit",{"ticket":ticket})["status"]=="DONE" and directory.is_dir(),"mkdir"))
    ticket=prepare({"kind":"write_text","path":str(target),"text":"first\n"})
    approve_for_lab(ticket)
    verify("write_synthetic_local_approval_lab",lambda:require(
        b.operate("commit",{"ticket":ticket})["status"]=="DONE" and target.read_text("utf8")=="first\n","write"))
    ticket=prepare({"kind":"write_text","path":str(target),"text":"second\n"})
    approve_for_lab(ticket)
    def backup_test():
        reply=b.operate("commit",{"ticket":ticket})
        require(reply["status"]=="DONE","backup mutation")
        name=reply["result"]["backup"]
        backup=g.BACKUPS/name
        backups.append(backup)
        require(backup.read_text("utf8")=="first\n","backup content")
        require(target.read_text("utf8")=="second\n","updated content")
    verify("backups_protect_previous_content_lab",backup_test)
    ticket=prepare({"kind":"run","exe":r"C:\Windows\System32\whoami.exe","args":[]})
    rejected("command_before_approval_denied",lambda:b.operate("commit",{"ticket":ticket}))
    approve_for_lab(ticket)
    verify("approved_windows_command_lab",lambda:require(
        b.operate("commit",{"ticket":ticket})["result"]["returncode"]==0,"whoami"))
    ticket=prepare({"kind":"mkdir","path":str(base/"G4_EXPIRED_MUST_NOT_EXIST")})
    item=b.read_ticket(ticket)
    item["created"]=int(time.time())-500
    item["expires"]=int(time.time())-10
    item["approved_at"]=int(time.time())-60
    item["status"]="APPROVED"
    item["approval_seal"]=g.approval_seal(item,b.approval_key)
    g.json_atomic(g.PENDING/(ticket+".json"),item)
    rejected("expired_approved_ticket_denied",lambda:b.operate("commit",{"ticket":ticket}))
    ticket=prepare({"kind":"mkdir","path":str(base/"G4_CHANGED_MUST_NOT_EXIST")})
    approve_for_lab(ticket)
    item=b.read_ticket(ticket)
    item["spec"]["path"]=str(base/"G4_MALICIOUS_CHANGED_DIR")
    g.json_atomic(g.PENDING/(ticket+".json"),item)
    rejected("altered_approved_spec_denied",lambda:b.operate("commit",{"ticket":ticket}))
finally:
    if target.exists():target.unlink()
    if directory.exists():directory.rmdir()
    for t in tickets:
        file=g.PENDING/(t+".json")
        if file.exists():file.unlink()
    for f in backups:
        if f.exists():f.unlink()
print(json.dumps({"schema":"BCP_G4_ADDITIONAL_SECURITY","checks":checks,
   "passed":sum(v is True for v in checks.values()),"total":len(checks),
   "PASS":all(v is True for v in checks.values()),
   "approval_mode":"SIMULATED_LAB_ONLY","admin_elevation":False},indent=2))
if not all(v is True for v in checks.values()):raise SystemExit(1)
