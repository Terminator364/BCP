"""BCP G4 durable jobs real subprocess lifecycle, temporary sandbox only."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g4_durable_jobs import DurableJobs, JobError, CHUNK

checks={}
def ok(name,condition):
    checks[name]=bool(condition)
    if not condition:raise AssertionError(name)
def wait_state(engine,ident,states,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=engine.status(ident)["state"]
        if value in states:return value
        time.sleep(.05)
    raise AssertionError("TIMEOUT_"+str(states))

with tempfile.TemporaryDirectory(prefix="bcp-g4-real-jobs-",ignore_cleanup_errors=True) as d:
    root=Path(d);jobs=DurableJobs(root/"jobs")
    job=jobs.enqueue(sys.executable,["-c","import sys; print('BCP_JOB_OK');sys.stderr.write('BCP_ERR_OK\\n')"],cwd=str(root))["job_id"]
    result=jobs.execute_next()
    ok("executes_real_child",result["executed"] and result["state"]=="DONE")
    ok("correct_job_return",result["job_id"]==job and result["returncode"]==0)
    stdout=jobs.output(job)
    ok("stdout_collected",b"BCP_JOB_OK" in base64.b64decode(stdout["data_base64"]))
    ok("stderr_collected",b"BCP_ERR_OK" in base64.b64decode(jobs.output(job,"stderr")["data_base64"]))
    failed=jobs.enqueue(sys.executable,["-c","import sys;sys.exit(7)"],cwd=str(root))["job_id"]
    no=jobs.execute_next()
    ok("nonzero_exit_is_failed",no["state"]=="FAILED" and jobs.status(failed)["returncode"]==7)
    parent=jobs.enqueue(sys.executable,["-c","print('FIRST')"],cwd=str(root))["job_id"]
    child=jobs.enqueue(sys.executable,["-c","print('SECOND')"],cwd=str(root),depends=[parent])["job_id"]
    ok("parent_runs_before_dependency",jobs.execute_next()["job_id"]==parent)
    ok("dependent_runs_after_parent_done",jobs.execute_next()["job_id"]==child and jobs.status(child)["state"]=="DONE")
    cancelled=jobs.enqueue(sys.executable,["-c","print('SHOULD_NOT_RUN')"],cwd=str(root))["job_id"]
    jobs.cancel(cancelled)
    ok("queued_cancellation",jobs.status(cancelled)["state"]=="CANCELED")
    blocked=jobs.enqueue(sys.executable,["-c","print('NEVER')"],cwd=str(root),depends=[failed])["job_id"]
    ok("failed_dependency_not_executed",jobs.execute_next()["executed"] is False)
    ok("failed_dependency_blocked",jobs.status(blocked)["state"]=="BLOCKED")
    outputJob=jobs.enqueue(sys.executable,["-c","import os;os.write(1,b'x'*140001)"],cwd=str(root))["job_id"]
    ok("large_stream_job_completed",jobs.execute_next()["state"]=="DONE")
    chunk1=jobs.output(outputJob,length=CHUNK)
    chunk2=jobs.output(outputJob,offset=chunk1["next_offset"],length=CHUNK)
    chunk3=jobs.output(outputJob,offset=chunk2["next_offset"],length=CHUNK)
    ok("output_chunks_no_truncation",sum(len(base64.b64decode(c["data_base64"])) for c in (chunk1,chunk2,chunk3))==140001)
    ok("output_stream_paged",chunk1["next_offset"]==CHUNK and chunk3["next_offset"] is None)
    sleeping=jobs.enqueue(sys.executable,["-c","import time;time.sleep(20)"],cwd=str(root))["job_id"]
    result_holder=[]
    thread=threading.Thread(target=lambda:result_holder.append(jobs.execute_next()),daemon=True)
    thread.start()
    ok("child_reached_running",wait_state(jobs,sleeping,("RUNNING",))=="RUNNING")
    ok("cancel_running_requested",jobs.cancel(sleeping)["state"]=="CANCELLATION_REQUESTED")
    thread.join(9)
    ok("cancel_running_terminated",not thread.is_alive() and jobs.status(sleeping)["state"]=="CANCELED")
    ok("cancel_returned_correct_state",bool(result_holder) and result_holder[0]["state"]=="CANCELED")
    # Restore only an interrupted state marker, not a command rerun.
    interrupted=jobs.enqueue(sys.executable,["-c","print('NEVER_REEXECUTE')"],cwd=str(root))["job_id"]
    import sqlite3
    with sqlite3.connect(jobs.dbfile) as db:
        db.execute("UPDATE jobs SET state='RUNNING' WHERE id=?",(interrupted,))
    recovered=DurableJobs(root/"jobs")
    ok("restart_marks_interrupted",recovered.recover()["interrupted"]==1)
    ok("interrupted_is_not_replayed",recovered.status(interrupted)["state"]=="INTERRUPTED")
    ok("restart_preserves_done",recovered.status(job)["state"]=="DONE")
    ok("no_queued_processes_remaining",not recovered.execute_next()["executed"])
    ok("all_artifacts_inside_temporary_directory",all(f.is_relative_to(root) for f in root.rglob("*")))
print(json.dumps({"schema":"BCP_G4_DURABLE_JOB_EXECUTION_V1","passed":sum(checks.values()),
    "checks":checks,"PASS":all(checks.values()),
    "executed_only_test_python":True,"real_user_files_modified":False},indent=2))
