from __future__ import annotations

"""BCP Desired State store + deterministic drift detector (Phase 4 candidate)."""

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from .critical_store import CriticalStore, RevisionConflict

DESIRED_PREFIX="desired/"
PROJECT_ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
PHASES={"UNKNOWN","IN_SYNC","DRIFTED","RECONCILING","WAITING_RESOURCE","WAITING_CAPABILITY","AUTH_REQUIRED","DEGRADED","FAILED_SAFE"}
MODES={"OBSERVE_ONLY","AUTO_SAFE","AUTO_PROJECT","AUTO_BOUNDED_SYSTEM"}
PERMISSIONS={"P0_READ","P1_SAFE_WRITE","P2_PROJECT_MUTATION","P3_BOUNDED_SYSTEM_CHANGE"}
RESOURCES={"R0_TINY","R1_LIGHT","R2_MEDIUM","R3_HEAVY","R4_LOCAL_AI"}
OWNERS={"USER","CHATGPT","BCP_POLICY","PROJECT_ADAPTER"}

class DesiredStateError(RuntimeError): pass
class DesiredStateNotFound(DesiredStateError): pass
class DesiredStateRevisionConflict(DesiredStateError): pass

def _text(v:Any,name:str,cap:int)->str:
    s=str(v or "").strip()
    if not s or len(s)>cap: raise ValueError(f"invalid {name}")
    return s

def _time(v:Any,name:str,nullable:bool=True):
    if v is None and nullable: return None
    s=_text(v,name,80)
    if "T" not in s: raise ValueError(f"invalid {name}")
    return s

def validate_desired_resource(x:Any)->dict[str,Any]:
    if not isinstance(x,dict): raise ValueError("desired state resource must be object")
    if set(x)-{"schema","api_version","kind","metadata","spec","status"}: raise ValueError("unexpected desired state field")
    if x.get("schema")!="bcp.desired_state_resource/1": raise ValueError("unsupported desired state schema")
    if x.get("api_version")!="bcp/v1": raise ValueError("unsupported desired state api_version")
    kind=_text(x.get("kind"),"desired state kind",128)
    if not re.fullmatch(r"^[A-Za-z][A-Za-z0-9._-]{2,127}$",kind): raise ValueError("invalid desired state kind")

    m=x.get("metadata")
    if not isinstance(m,dict) or set(m)-{"resource_id","project_id","generation","created_at","updated_at","owner"}: raise ValueError("invalid metadata")
    rid=_text(m.get("resource_id"),"resource_id",160); pid=_text(m.get("project_id"),"project_id",128)
    if not PROJECT_ID_RE.fullmatch(pid): raise ValueError("invalid project_id")
    if type(m.get("generation")) is not int or m["generation"]<1: raise ValueError("invalid generation")
    _time(m.get("created_at"),"created_at",False); _time(m.get("updated_at"),"updated_at",True)
    if m.get("owner") is not None and m.get("owner") not in OWNERS: raise ValueError("invalid desired state owner")

    spec=x.get("spec")
    if not isinstance(spec,dict) or "desired" not in spec or "reconcile_policy" not in spec: raise ValueError("invalid desired state spec")
    if not isinstance(spec["desired"],dict): raise ValueError("desired must be object")
    p=spec["reconcile_policy"]
    if not isinstance(p,dict) or set(p)-{"mode","max_permission_class","resource_ceiling","repair_backoff_seconds","max_attempts_per_incident"}: raise ValueError("invalid reconcile_policy")
    if p.get("mode") not in MODES: raise ValueError("invalid reconcile mode")
    if p.get("max_permission_class") not in PERMISSIONS: raise ValueError("invalid reconcile permission")
    if p.get("resource_ceiling") is not None and p.get("resource_ceiling") not in RESOURCES: raise ValueError("invalid resource ceiling")
    if p.get("repair_backoff_seconds") is not None and (type(p["repair_backoff_seconds"]) is not int or not 1<=p["repair_backoff_seconds"]<=86400): raise ValueError("invalid repair backoff")
    if p.get("max_attempts_per_incident") is not None and (type(p["max_attempts_per_incident"]) is not int or not 1<=p["max_attempts_per_incident"]<=20): raise ValueError("invalid max attempts")
    ev=spec.get("evidence_contract") or []
    if not isinstance(ev,list) or any(not isinstance(v,str) or not v or len(v)>128 for v in ev): raise ValueError("invalid evidence_contract")
    deps=spec.get("dependencies") or []
    if not isinstance(deps,list) or len(deps)!=len(set(deps)) or any(not isinstance(v,str) or not v or len(v)>160 for v in deps): raise ValueError("invalid dependencies")

    st=x.get("status")
    if not isinstance(st,dict): raise ValueError("status required")
    if type(st.get("observed_generation")) is not int or st["observed_generation"]<0: raise ValueError("invalid observed_generation")
    if st.get("phase") not in PHASES: raise ValueError("invalid desired state phase")
    _time(st.get("last_observed_at"),"last_observed_at",True); _time(st.get("last_reconciled_at"),"last_reconciled_at",True)
    for c in st.get("conditions") or []:
        if not isinstance(c,dict) or not isinstance(c.get("type"),str) or c.get("status") not in {"TRUE","FALSE","UNKNOWN"}: raise ValueError("invalid condition")
    return deepcopy(x)

def deep_drift(desired:Any,observed:Any,path:str="$")->list[dict[str,Any]]:
    out=[]
    if isinstance(desired,dict):
        if not isinstance(observed,dict): return [{"path":path,"reason":"TYPE_MISMATCH","expected":desired,"observed":observed}]
        for k in sorted(desired):
            p=f"{path}/{str(k).replace('~','~0').replace('/','~1')}"
            if k not in observed: out.append({"path":p,"reason":"MISSING","expected":desired[k],"observed":None})
            else: out.extend(deep_drift(desired[k],observed[k],p))
    elif isinstance(desired,list):
        if not isinstance(observed,list) or desired!=observed: out.append({"path":path,"reason":"VALUE_MISMATCH","expected":desired,"observed":observed})
    elif desired!=observed:
        out.append({"path":path,"reason":"VALUE_MISMATCH","expected":desired,"observed":observed})
    return out

def desired_stream_id(project_id:str,resource_id:str)->str:
    pid=_text(project_id,"project_id",128); rid=_text(resource_id,"resource_id",160)
    if not PROJECT_ID_RE.fullmatch(pid): raise ValueError("invalid project_id")
    return f"{DESIRED_PREFIX}{pid}/{hashlib.sha256(rid.encode()).hexdigest()[:24]}"

class DesiredStateStore:
    def __init__(self,store:CriticalStore): self.store=store

    def put(self,resource:dict[str,Any],*,owner_id:str,expected_revision:int|None=None)->dict[str,Any]:
        clean=validate_desired_resource(resource); m=clean["metadata"]; sid=desired_stream_id(m["project_id"],m["resource_id"])
        cur=self.store.get_state(sid); rev=int(cur["revision"]) if cur else 0
        if expected_revision is not None and int(expected_revision)!=rev: raise DesiredStateRevisionConflict(f"expected revision {expected_revision}, current {rev}")
        if cur and cur["payload"]==clean:
            return {"schema":"bcp.desired_state_receipt/1","status":"UNCHANGED","project_id":m["project_id"],"resource_id":m["resource_id"],"revision":rev,"content_hash":cur["content_hash"],"outbox_message_id":None,"idempotent_replay":True,"field_certified":False}
        fence=self.store.acquire_writer_fence(sid,owner_id)
        try:
            r=self.store.commit_transition(stream_id=sid,expected_revision=rev,new_revision=rev+1,fencing_token=fence,payload=clean,destination="BCP_DESIRED_STATE")
        except RevisionConflict as e: raise DesiredStateRevisionConflict(str(e)) from e
        return {"schema":"bcp.desired_state_receipt/1","status":r.status,"project_id":m["project_id"],"resource_id":m["resource_id"],"revision":r.revision,"content_hash":r.content_hash,"outbox_message_id":r.outbox_message_id,"idempotent_replay":r.idempotent_replay,"field_certified":False}

    def get(self,project_id:str,resource_id:str)->dict[str,Any]:
        s=self.store.get_state(desired_stream_id(project_id,resource_id))
        if s is None: raise DesiredStateNotFound(resource_id)
        return {"resource":s["payload"],"revision":s["revision"],"content_hash":s["content_hash"],"fencing_token":s["fencing_token"],"committed_epoch":s["committed_epoch"]}

    def list(self,project_id:str|None=None,*,limit:int=512)->list[dict[str,Any]]:
        prefix=DESIRED_PREFIX if project_id is None else f"{DESIRED_PREFIX}{_text(project_id,'project_id',128)}/"
        return [{"resource":s["payload"],"revision":s["revision"],"content_hash":s["content_hash"],"fencing_token":s["fencing_token"],"committed_epoch":s["committed_epoch"]} for s in self.store.list_states(prefix,limit=limit)]

    def drift(self,project_id:str,resource_id:str,observed:dict[str,Any])->list[dict[str,Any]]:
        return deep_drift(self.get(project_id,resource_id)["resource"]["spec"]["desired"],observed)

__all__=["DesiredStateStore","DesiredStateError","DesiredStateNotFound","DesiredStateRevisionConflict","validate_desired_resource","desired_stream_id","deep_drift"]
