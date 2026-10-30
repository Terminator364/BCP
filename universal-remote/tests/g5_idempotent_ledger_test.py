"""G5 ledger duplicate, restart, cross-device and crash test."""
import hashlib,json
from pathlib import Path
import secrets,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g5_idempotent_ledger import ActionLedger,LedgerError

checks={}
def ok(name,result):
    checks[name]=bool(result)
    if not result:raise AssertionError(name)
def denied(name,fn):
    try:fn()
    except LedgerError:ok(name,True)
    else:raise AssertionError(name)
with tempfile.TemporaryDirectory(prefix="bcp-g5-ledger-") as root:
    db=Path(root)/"requests.sqlite"
    ledger=ActionLedger(db)
    a,b=secrets.token_hex(16),secrets.token_hex(16)
    rid=secrets.token_hex(16)
    first=ledger.offer(a,rid,"files.upload.begin",{"path":"test.txt","overwrite":False})
    ok("new_request_created",first["created"] and first["state"]=="QUEUED")
    again=ledger.offer(a,rid,"files.upload.begin",{"overwrite":False,"path":"test.txt"})
    ok("canonical_duplicate_reused",not again["created"])
    denied("same_key_other_arguments_rejected",lambda:ledger.offer(a,rid,"files.upload.begin",{"path":"secret"}))
    denied("same_key_other_phone_rejected",lambda:ledger.offer(b,rid,"files.upload.begin",{"path":"test.txt","overwrite":False}))
    denied("status_other_phone_denied",lambda:ledger.status(b,rid))
    denied("complete_before_claim_denied",lambda:ledger.complete(a,rid,True,"a"*64))
    ok("claim_once",ledger.claim(a,rid)["state"]=="CLAIMED")
    denied("claim_repeated_denied",lambda:ledger.claim(a,rid))
    resumed=ActionLedger(db)
    ok("restart_preserves_claim",resumed.status(a,rid)["state"]=="CLAIMED")
    ok("recovery_interrupts_inflight",resumed.recover()["interrupted"]==1)
    ok("no_blind_replay",resumed.status(a,rid)["state"]=="INTERRUPTED")
    denied("interrupted_not_reclaimed",lambda:resumed.claim(a,rid))
    ok("interrupted_duplicate_stays_interrupted",
       resumed.offer(a,rid,"files.upload.begin",{"path":"test.txt","overwrite":False})["state"]=="INTERRUPTED")
    complete=secrets.token_hex(16)
    resumed.offer(b,complete,"jobs.enqueue",{"cmd":"safe_test"})
    resumed.claim(b,complete)
    ok("completion_persisted",resumed.complete(b,complete,True,hashlib.sha256(b"ok").hexdigest())["state"]=="DONE")
    ok("result_sha_persisted",ActionLedger(db).status(b,complete)["result_sha256"]==hashlib.sha256(b"ok").hexdigest())
    denied("finished_not_reclaimed",lambda:resumed.claim(b,complete))
    denied("invalid_device",lambda:resumed.offer("shared-key",secrets.token_hex(16),"jobs.enqueue",{}))
    denied("invalid_action",lambda:resumed.offer(a,secrets.token_hex(16),"shell;rm",{}))
    denied("non_json_args",lambda:resumed.offer(a,secrets.token_hex(16),"files.list",{"x":{1,2}}))
    many=[]
    for i in range(35):
        many.append(resumed.offer(a,secrets.token_hex(16),"files.read",{"page":i}))
    ok("no_twenty_operation_cap",len(many)==35)
    ok("safe_data_minimal",b"test.txt" not in db.read_bytes())
print(json.dumps({"schema":"BCP_G5_IDEMPOTENCY_LAB","passed":len(checks),
                  "checks":checks,"PASS":all(checks.values()),
                  "external_connections":0,"real_PC_commands":0},indent=2))
