"""BCP G6 memory governor test: synthetic edge cases + real Windows sample."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"windows"))
from g6_resource_governor import ResourceGovernor,Resources,MIB,windows_memory

checks={}
def ok(name,flag):
    checks[name]=bool(flag)
    if not flag:raise AssertionError(name)
def bad(name,call):
    try:call()
    except (ValueError,OSError):ok(name,True)
    else:raise AssertionError(name)
def mem(mib):
    return Resources(4096*MIB,int(mib*MIB))

policy=ResourceGovernor()
ok("healthy_allows_heavy",policy.decide(mem(650))["start_optional_heavy_job"])
ok("no_total_job_cap",policy.decide(mem(650))["max_total_operations"] is None)
ok("no_file_size_cap",policy.decide(mem(650))["max_total_transfer_bytes"] is None)
ok("one_heavy_worker_budget",not policy.decide(mem(650),1)["start_optional_heavy_job"])
ok("low_ram_pauses_new_heavy",not policy.decide(mem(126))["start_optional_heavy_job"])
ok("ram_hysteresis_stays_paused",not policy.decide(mem(190))["start_optional_heavy_job"])
ok("ram_recovery_resumes",policy.decide(mem(300))["start_optional_heavy_job"])
ok("at_critical_boundary_pauses",not policy.decide(mem(128))["start_optional_heavy_job"])
ok("at_resume_boundary_resumes",policy.decide(mem(256))["start_optional_heavy_job"])
ok("light_user_control_never_disabled",policy.decide(mem(15))["user_interactive_control_allowed"])
ok("jobs_retained_under_pressure",policy.decide(mem(15))["queued_jobs_retained"])
ok("existing_jobs_not_killed",policy.decide(mem(15))["leave_existing_jobs_running"])
ok("network_data_not_collected",not any(x in policy.decide(mem(400)) for x in ("ssid","email","key")))
ok("chunk_stays_small",policy.decide(mem(400))["per_chunk_bytes"]==65536)
bad("negative_sample_rejected",lambda:Resources(-10,0))
bad("overfilled_sample_rejected",lambda:Resources(100,101))
bad("bool_not_accepted_as_memory",lambda:Resources(True,0))
bad("invalid_policy_rejected",lambda:ResourceGovernor(256,128))
bad("invalid_worker_count_rejected",lambda:policy.decide(mem(400),-1))
bad("invalid_sample_rejected",lambda:policy.decide(None))
sample=windows_memory()
ok("real_windows_total_ram_positive",sample.total_bytes>0)
ok("real_windows_free_ram_bounded",0<=sample.available_bytes<=sample.total_bytes)
live=policy.decide(sample)
ok("live_policy_returned",live["reason"] in ("RAM_PRESSURE","HEAVY_WORKER_BUSY","AVAILABLE"))
ok("user_controls_available_on_real_pc",live["user_interactive_control_allowed"])
print(json.dumps({"schema":"BCP_G6_LOW_RAM_LAB_AND_REAL_SAMPLE",
 "passed":len(checks),"checks":checks,"PASS":all(checks.values()),
 "real_pc_total_ram_mib":round(sample.total_bytes/MIB),
 "real_pc_free_ram_mib":round(sample.free_mib),
 "sample_only_no_system_settings_modified":True},indent=2))
