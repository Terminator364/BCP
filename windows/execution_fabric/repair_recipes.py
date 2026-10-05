from __future__ import annotations

"""Typed repair-recipe registry on the shared BCP CriticalStore."""

from copy import deepcopy
import re
from typing import Any

from .critical_store import CriticalStore, RevisionConflict

RECIPE_PREFIX="recipe/"
RECIPE_ID_RE=re.compile(r"^[a-z0-9][a-z0-9._-]{2,159}$")
INCIDENT_CLASSES={"DRIFT","FRICTION","CAPABILITY","RESOURCE","PROVIDER","AUTH","UPDATE","UNKNOWN"}
STATUSES={"DRAFT","REPOSITORY_VALIDATED","FIELD_VALIDATED","RETIRED"}
PERMISSION_ORDER={"P0_READ":0,"P1_SAFE_WRITE":1,"P2_PROJECT_MUTATION":2,"P3_BOUNDED_SYSTEM_CHANGE":3}
RESOURCE_ORDER={"R0_TINY":0,"R1_LIGHT":1,"R2_MEDIUM":2,"R3_HEAVY":3,"R4_LOCAL_AI":4}
EVIDENCE={"EXIT_CODE","FILE_READBACK","HASH","PROCESS_HEALTH","HTTP_HEALTH","SERVICE_STATE","GIT_REVISION","TEST_RESULT","ARTIFACT_SIGNATURE","PROVIDER_ACK","DESTINATION_READBACK","CUSTOM_VALIDATOR"}
FAILURE={"STOP_FAIL_SAFE","NEXT_RECIPE","ROLLBACK","NEEDS_REASONING"}
FORBIDDEN_KEYS={"command","argv","shell","powershell","cmd","executable","script"}

class RecipeError(RuntimeError): pass
class RecipeNotFound(RecipeError): pass
class RecipeRevisionConflict(RecipeError): pass

def _text(v:Any,name:str,cap:int)->str:
    s=str(v or "").strip()
    if not s or len(s)>cap: raise ValueError(f"invalid {name}")
    return s

def _no_freeform_exec(value:Any,path:str="$")->None:
    if isinstance(value,dict):
        for k,v in value.items():
            if str(k).casefold() in FORBIDDEN_KEYS: raise ValueError(f"forbidden executable field at {path}/{k}")
            _no_freeform_exec(v,f"{path}/{k}")
    elif isinstance(value,list):
        for i,v in enumerate(value): _no_freeform_exec(v,f"{path}/{i}")
    elif isinstance(value,str):
        low=value.casefold()
        if "powershell.exe" in low or "cmd.exe" in low: raise ValueError(f"forbidden executable value at {path}")

def validate_recipe(x:Any)->dict[str,Any]:
    if not isinstance(x,dict): raise ValueError("recipe must be object")
    allowed={"schema","recipe_id","version","status","auto_eligible","match","policy","steps","source_revision","ledger_refs","regression_refs","notes"}
    if set(x)-allowed: raise ValueError("unexpected recipe field")
    if x.get("schema")!="bcp.repair_recipe/1": raise ValueError("unsupported recipe schema")
    rid=_text(x.get("recipe_id"),"recipe_id",160)
    if not RECIPE_ID_RE.fullmatch(rid): raise ValueError("invalid recipe_id")
    _text(x.get("version"),"recipe version",64)
    status=x.get("status")
    if status not in STATUSES: raise ValueError("invalid recipe status")
    if type(x.get("auto_eligible")) is not bool: raise ValueError("invalid auto_eligible")
    if x["auto_eligible"] and status!="FIELD_VALIDATED": raise ValueError("auto recipe must be FIELD_VALIDATED")

    match=x.get("match")
    if not isinstance(match,dict) or set(match)-{"incident_class","resource_kind","reason_codes","project_ids"}: raise ValueError("invalid recipe match")
    if match.get("incident_class") not in INCIDENT_CLASSES: raise ValueError("invalid incident_class")
    if match.get("resource_kind") is not None and (not isinstance(match["resource_kind"],str) or len(match["resource_kind"])>128): raise ValueError("invalid resource_kind")
    for name,cap in (("reason_codes",160),("project_ids",128)):
        vals=match.get(name) or []
        if not isinstance(vals,list) or len(vals)!=len(set(vals)) or any(not isinstance(v,str) or not v or len(v)>cap for v in vals): raise ValueError(f"invalid {name}")

    policy=x.get("policy")
    if not isinstance(policy,dict) or set(policy)!={"max_permission_class","max_resource_class","max_attempts","backoff_seconds","rollback_required"}: raise ValueError("invalid recipe policy")
    if policy.get("max_permission_class") not in PERMISSION_ORDER: raise ValueError("invalid recipe permission")
    if policy.get("max_resource_class") not in RESOURCE_ORDER: raise ValueError("invalid recipe resource")
    if type(policy.get("max_attempts")) is not int or not 1<=policy["max_attempts"]<=20: raise ValueError("invalid recipe max_attempts")
    if type(policy.get("backoff_seconds")) is not int or not 1<=policy["backoff_seconds"]<=86400: raise ValueError("invalid recipe backoff")
    if type(policy.get("rollback_required")) is not bool: raise ValueError("invalid rollback_required")

    steps=x.get("steps")
    if not isinstance(steps,list) or not 1<=len(steps)<=64: raise ValueError("invalid recipe steps")
    seen=set()
    for step in steps:
        if not isinstance(step,dict) or set(step)-{"step_id","capability_id","permission_class","resource_class","evidence_contract","input_defaults","on_failure"}: raise ValueError("invalid recipe step")
        sid=_text(step.get("step_id"),"step_id",128)
        if not re.fullmatch(r"^[a-z0-9][a-z0-9._-]{1,127}$",sid) or sid in seen: raise ValueError("invalid or duplicate step_id")
        seen.add(sid)
        cap=_text(step.get("capability_id"),"capability_id",160)
        if not re.fullmatch(r"^[a-z0-9][a-z0-9._-]{2,159}$",cap): raise ValueError("invalid capability_id")
        perm=step.get("permission_class"); res=step.get("resource_class")
        if perm not in PERMISSION_ORDER or PERMISSION_ORDER[perm]>PERMISSION_ORDER[policy["max_permission_class"]]: raise ValueError("step exceeds recipe permission")
        if res not in RESOURCE_ORDER or RESOURCE_ORDER[res]>RESOURCE_ORDER[policy["max_resource_class"]]: raise ValueError("step exceeds recipe resource")
        ev=step.get("evidence_contract")
        if not isinstance(ev,list) or not ev or len(ev)!=len(set(ev)) or any(v not in EVIDENCE for v in ev): raise ValueError("invalid step evidence_contract")
        if step.get("on_failure") not in FAILURE: raise ValueError("invalid on_failure")
        defaults=step.get("input_defaults") or {}
        if not isinstance(defaults,dict): raise ValueError("invalid input_defaults")
        _no_freeform_exec(defaults)

    _text(x.get("source_revision"),"source_revision",256)
    for name,cap in (("ledger_refs",256),("regression_refs",512),("notes",1000)):
        vals=x.get(name) or []
        if not isinstance(vals,list) or len(vals)!=len(set(vals)) or any(not isinstance(v,str) or not v or len(v)>cap for v in vals): raise ValueError(f"invalid {name}")
    return deepcopy(x)

def recipe_stream_id(recipe_id:str)->str:
    rid=_text(recipe_id,"recipe_id",160)
    if not RECIPE_ID_RE.fullmatch(rid): raise ValueError("invalid recipe_id")
    return RECIPE_PREFIX+rid

def recipe_matches(recipe:dict[str,Any],*,incident_class:str,project_id:str,resource_kind:str|None,reason_code:str)->bool:
    m=recipe["match"]
    if m["incident_class"]!=incident_class: return False
    if m.get("project_ids") and project_id not in m["project_ids"]: return False
    if m.get("resource_kind") and m["resource_kind"]!=resource_kind: return False
    if m.get("reason_codes") and reason_code not in m["reason_codes"]: return False
    return True

class RecipeRegistry:
    def __init__(self,store:CriticalStore): self.store=store

    def put(self,recipe:dict[str,Any],*,owner_id:str,expected_revision:int|None=None)->dict[str,Any]:
        clean=validate_recipe(recipe); sid=recipe_stream_id(clean["recipe_id"]); cur=self.store.get_state(sid); rev=int(cur["revision"]) if cur else 0
        if expected_revision is not None and int(expected_revision)!=rev: raise RecipeRevisionConflict(f"expected revision {expected_revision}, current {rev}")
        if cur and cur["payload"]==clean:
            return {"schema":"bcp.recipe_registry_receipt/1","status":"UNCHANGED","recipe_id":clean["recipe_id"],"revision":rev,"content_hash":cur["content_hash"],"idempotent_replay":True,"field_certified":False}
        fence=self.store.acquire_writer_fence(sid,owner_id)
        try:
            r=self.store.commit_transition(stream_id=sid,expected_revision=rev,new_revision=rev+1,fencing_token=fence,payload=clean,destination="BCP_REPAIR_RECIPE")
        except RevisionConflict as e: raise RecipeRevisionConflict(str(e)) from e
        return {"schema":"bcp.recipe_registry_receipt/1","status":r.status,"recipe_id":clean["recipe_id"],"revision":r.revision,"content_hash":r.content_hash,"outbox_message_id":r.outbox_message_id,"idempotent_replay":r.idempotent_replay,"field_certified":False}

    def get(self,recipe_id:str)->dict[str,Any]:
        s=self.store.get_state(recipe_stream_id(recipe_id))
        if s is None: raise RecipeNotFound(recipe_id)
        return {"recipe":s["payload"],"revision":s["revision"],"content_hash":s["content_hash"],"committed_epoch":s["committed_epoch"]}

    def list(self,*,limit:int=512)->list[dict[str,Any]]:
        return [{"recipe":s["payload"],"revision":s["revision"],"content_hash":s["content_hash"],"committed_epoch":s["committed_epoch"]} for s in self.store.list_states(RECIPE_PREFIX,limit=limit)]

    def select(self,*,incident_class:str,project_id:str,resource_kind:str|None,reason_code:str,limit:int=512)->dict[str,Any]|None:
        candidates=[]
        for item in self.list(limit=limit):
            r=item["recipe"]
            if r["status"]=="RETIRED" or not recipe_matches(r,incident_class=incident_class,project_id=project_id,resource_kind=resource_kind,reason_code=reason_code): continue
            m=r["match"]
            score=(4 if m.get("project_ids") else 0)+(2 if m.get("resource_kind") else 0)+(1 if m.get("reason_codes") else 0)+(1 if r["status"]=="FIELD_VALIDATED" else 0)
            candidates.append((score,r["recipe_id"],item))
        if not candidates: return None
        candidates.sort(key=lambda x:(-x[0],x[1]))
        return candidates[0][2]

__all__=["RecipeRegistry","RecipeError","RecipeNotFound","RecipeRevisionConflict","validate_recipe","recipe_matches","PERMISSION_ORDER","RESOURCE_ORDER"]
