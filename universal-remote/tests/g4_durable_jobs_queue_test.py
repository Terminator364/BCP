"""BCP durable queue metadata test; does NOT execute any program."""
import json
import os
from pathlib import Path
import sys
import tempfile
from g4_durable_jobs import DurableJobs,JobError

checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)
def denied(name,callback):
    try:callback()
    except (JobError,ValueError):
        check(name,True)
    else:check(name,False)

with tempfile.TemporaryDirectory(prefix="bcp-job-queue-") as tmp:
    area=Path(tmp)
    queue=DurableJobs(area/"jobstate")
    denied("reject_relative_executable",lambda:queue.enqueue("python.exe",[]))
    denied("reject_invalid_workdir",lambda:queue.enqueue(sys.executable,[],cwd="relative"))
    denied("reject_unknown_dependency",lambda:queue.enqueue(sys.executable,[],depends=["0"*32]))
    jobs=[]
    for i in range(28):
        jobs.append(queue.enqueue(sys.executable,["--version"],cwd=str(area))["job_id"])
    check("over_twenty_jobs_no_quota",len(jobs)==28)
    check("pagination_works",len(queue.list(0,20)["jobs"])==20 and
          queue.list(0,20)["next_cursor"]==20)
    check("pagination_second_page",len(queue.list(20,20)["jobs"])==8)
    restored=DurableJobs(area/"jobstate")
    check("persistent_after_restart",restored.status(jobs[0])["state"]=="QUEUED")
    cancelled=restored.cancel(jobs[1])
    check("cancel_without_execution",cancelled["state"]=="CANCELED")
    check("others_remain_queued",restored.status(jobs[2])["state"]=="QUEUED")
    # Simulate interrupted supervision without executing any program.
    import sqlite3
    with sqlite3.connect(restored.dbfile) as db:
        db.execute("UPDATE jobs SET state='RUNNING' WHERE id=?",(jobs[3],))
    db.close()
    recovered=DurableJobs(area/"jobstate").recover()
    check("running_not_replayed",recovered["interrupted"]==1)
    check("interrupted_marked",restored.status(jobs[3])["state"]=="INTERRUPTED")
    check("other_jobs_preserved",restored.status(jobs[4])["state"]=="QUEUED")
    denied("unknown_job_rejected",lambda:queue.status("f"*32))
    check("zero_processes_executed",not list((area/"jobstate").glob("*.stdout")))
print(json.dumps({"schema":"BCP_G4_DURABLE_QUEUE_METADATA_TEST",
    "checks":checks,"passed":sum(checks.values()),"PASS":all(checks.values()),
    "executables_launched":0,"real_user_files_modified":False},indent=2))
