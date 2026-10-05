from __future__ import annotations

"""Phase 4 incident/reconciliation engine.

No background loop and no free-form execution. It turns observations into durable
incidents and typed repair plans. Only a fresh conforming observation can mark a drift
incident RECOVERED.
"""

from copy import deepcopy
import datetime as dt
import hashlib
import json
import re
from typing import Any

from .critical_store import CriticalStore, RevisionConflict
from .desired_state import DesiredStateStore, deep_drift
from .repair_recipes import RecipeRegistry, PERMISSION_ORDER, RESOURCE_ORDER
from .resource_admission import decide as resource_decide

INCIDENT_PREFIX="incident/"
ACTIVE={"OPEN","MATCHED_RECIPE","WAITING_RESOURCE","WAITING_CAPABILITY","WAITING_APPROVAL","RECONCILING","FAILED_SAFE","NEEDS_REASONING"}
PROJECT_ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")

class IncidentError(RuntimeError): pass
class IncidentNotFound(IncidentError): pass
class IncidentRevisionConflict(IncidentError): pass

def utc_now()->str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def _text(v:Any,name:str,cap:int)->str:
    s=str(v or "").strip()
    if not s or len(s)>cap: raise ValueError(f"invalid {name}")
    return s

def _canonical(v:Any)->str:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def incident_fingerprint(*,project_id:str,incident_class:str,resource_id:str|None,reason_code:str,signature:Any)->str:
    payload={"project_id":project_id,"incident_class":incident_class,"resource_id":resource_id,"reason_code":reason_code,"signature":signature}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()

def incident_stream_id(project_id:str,fingerprint:str)->str:
    pid=_text(project_id,"project_id",128)
    if not PROJECT_ID_RE.fullmatch(pid): raise ValueError("invalid project_id")
    if not re.fullmatch(r"^[a-f0-9]{64}$",str(fingerprint)): raise ValueError("invalid fingerprint")
    return f"{INCIDENT_PREFIX}{pid}/{fingerprint}"

def _cap_state(value:Any)->str:
    if isinstance(value,dict): return str(value.get("state") or "UNKNOWN").upper()
    return str(value or "UNKNOWN").upper()

def _desired_phase(incident_status:str)->str:
    return {
        "WAITING_RESOURCE":"WAITING_RESOURCE",
        "WAITING_CAPABILITY":"WAITING_CAPABILITY",
        "RECONCILING":"RECONCILING",
        "FAILED_SAFE":"FAILED_SAFE",
        "NEEDS_REASONING":"DEGRADED",
    }.get(incident_status,"DRIFTED")

class IncidentEngine:
    def __init__(self,store:CriticalStore):
        self.store=store
        self.desired=DesiredStateStore(store)
        self.recipes=RecipeRegistry(store)

    def get(self,project_id:str,fingerprint:str)->dict[str,Any]:
        state=self.store.get_state(incident_stream_id(project_id,fingerprint))
        if state is None: raise IncidentNotFound(fingerprint)
        return {"incident":state["payload"],"revision":state["revision"],"content_hash":state["content_hash"],"committed_epoch":state["committed_epoch"]}

    def list(self,project_id:str|None=None,*,limit:int=512)->list[dict[str,Any]]:
        prefix=INCIDENT_PREFIX if project_id is None else f"{INCIDENT_PREFIX}{_text(project_id,'project_id',128)}/"
        return [{"incident":s["payload"],"revision":s["revision"],"content_hash":s["content_hash"],"committed_epoch":s["committed_epoch"]} for s in self.store.list_states(prefix,limit=limit)]

    def _put(self,incident:dict[str,Any],*,owner_id:str)->dict[str,Any]:
        sid=incident_stream_id(incident["project_id"],incident["fingerprint"])
        cur=self.store.get_state(sid); rev=int(cur["revision"]) if cur else 0
        if cur and cur["payload"]==incident:
            return {"status":"UNCHANGED","revision":rev,"content_hash":cur["content_hash"],"outbox_message_id":None}
        fence=self.store.acquire_writer_fence(sid,owner_id)
        try:
            r=self.store.commit_transition(stream_id=sid,expected_revision=rev,new_revision=rev+1,fencing_token=fence,payload=deepcopy(incident),destination="BCP_INCIDENT")
        except RevisionConflict as e: raise IncidentRevisionConflict(str(e)) from e
        return {"status":r.status,"revision":r.revision,"content_hash":r.content_hash,"outbox_message_id":r.outbox_message_id}

    def _update_desired_status(self,item:dict[str,Any],*,phase:str,now:str,owner_id:str,condition_reason:str)->dict[str,Any]:
        resource=deepcopy(item["resource"]); generation=resource["metadata"]["generation"]
        resource["status"]["observed_generation"]=generation
        resource["status"]["phase"]=phase
        resource["status"]["last_observed_at"]=now
        if phase=="IN_SYNC": resource["status"]["last_reconciled_at"]=now
        resource["status"]["conditions"]=[{"type":"Reconciled","status":"TRUE" if phase=="IN_SYNC" else "FALSE","reason":condition_reason,"evidence_ref":None}]
        return self.desired.put(resource,owner_id=owner_id,expected_revision=item["revision"])

    def _close_drift_incidents(self,project_id:str,resource_id:str,*,owner_id:str,now:str)->None:
        for item in self.list(project_id,limit=1024):
            inc=item["incident"]
            if inc.get("incident_class")=="DRIFT" and inc.get("resource_id")==resource_id and inc.get("status")!="RECOVERED":
                nxt=deepcopy(inc); nxt["status"]="RECOVERED"; nxt["last_seen_at"]=now
                self._put(nxt,owner_id=owner_id)

    def reconcile(
        self,
        *,
        project_id:str,
        resource_id:str,
        observed:dict[str,Any],
        capability_states:dict[str,Any],
        resource_mode:str,
        owner_id:str,
        now:str|None=None,
    )->dict[str,Any]:
        now=now or utc_now()
        item=self.desired.get(project_id,resource_id)
        resource=item["resource"]; drift=deep_drift(resource["spec"]["desired"],observed)
        if not drift:
            self._update_desired_status(item,phase="IN_SYNC",now=now,owner_id=owner_id,condition_reason="OBSERVED_MATCH")
            self._close_drift_incidents(project_id,resource_id,owner_id=owner_id,now=now)
            return {"schema":"bcp.reconcile_result/1","status":"IN_SYNC","project_id":project_id,"resource_id":resource_id,"drift":[],"incident":None,"field_certified":False}

        paths=[d["path"] for d in drift]
        reason_code="DESIRED_STATE_DRIFT"
        fp=incident_fingerprint(project_id=project_id,incident_class="DRIFT",resource_id=resource_id,reason_code=reason_code,signature=paths)
        sid=incident_stream_id(project_id,fp); current=self.store.get_state(sid)
        old=deepcopy(current["payload"]) if current else None
        occurrence=(int(old.get("occurrence_count",0))+1) if old else 1
        first=old.get("first_seen_at") if old else now
        recipe_item=self.recipes.select(incident_class="DRIFT",project_id=project_id,resource_kind=resource["kind"],reason_code=reason_code)
        policy=resource["spec"]["reconcile_policy"]

        status="NEEDS_REASONING"; recipe_id=None; max_attempts=int(policy.get("max_attempts_per_incident") or 1); planned=[]
        attempt_count=int((old or {}).get("repair",{}).get("attempt_count",0))
        if recipe_item is not None:
            recipe=recipe_item["recipe"]; recipe_id=recipe["recipe_id"]
            max_attempts=min(max_attempts,int(recipe["policy"]["max_attempts"]))
            if attempt_count>=max_attempts:
                status="FAILED_SAFE"
            else:
                approval_block=False; resource_block=False; capability_block=False
                for step in recipe["steps"]:
                    block=None
                    if policy["mode"]=="OBSERVE_ONLY":
                        block="OBSERVE_ONLY"; approval_block=True
                    elif not recipe["auto_eligible"] or recipe["status"]!="FIELD_VALIDATED":
                        block="RECIPE_NOT_FIELD_VALIDATED"; approval_block=True
                    elif PERMISSION_ORDER[step["permission_class"]]>PERMISSION_ORDER[policy["max_permission_class"]]:
                        block="PERMISSION_CEILING"; approval_block=True
                    elif policy.get("resource_ceiling") and RESOURCE_ORDER[step["resource_class"]]>RESOURCE_ORDER[policy["resource_ceiling"]]:
                        block="RESOURCE_CEILING"; resource_block=True
                    else:
                        rd=resource_decide(step["resource_class"],mode=resource_mode,background=False,essential=False)
                        if not rd.allowed:
                            block=rd.reason; resource_block=True
                        elif _cap_state(capability_states.get(step["capability_id"]))!="AVAILABLE":
                            block="CAPABILITY_UNAVAILABLE"; capability_block=True
                    planned.append({"step_id":step["step_id"],"capability_id":step["capability_id"],"state":"BLOCKED" if block else "READY","block_reason":block})
                if approval_block: status="WAITING_APPROVAL"
                elif resource_block: status="WAITING_RESOURCE"
                elif capability_block: status="WAITING_CAPABILITY"
                else: status="RECONCILING"

        receipt_ids=list((old or {}).get("repair",{}).get("receipt_ids",[]))
        incident={
            "schema":"bcp.incident/1","incident_id":f"inc-{fp[:24]}","project_id":project_id,"resource_id":resource_id,
            "incident_class":"DRIFT","fingerprint":fp,"status":status,"occurrence_count":occurrence,
            "first_seen_at":first,"last_seen_at":now,
            "reason":{"code":reason_code,"summary":f"{len(drift)} desired-state invariant(s) drifted","drift_paths":paths},
            "evidence":[{"kind":"DESIRED_STATE_OBSERVATION","status":"OBSERVED","ref":None,"value":{"drift_count":len(drift)}}],
            "repair":{"recipe_id":recipe_id,"attempt_count":attempt_count,"max_attempts":max_attempts,"next_retry_at":None,"planned_steps":planned,"receipt_ids":receipt_ids},
            "friction":None,
        }
        self._put(incident,owner_id=owner_id)
        self._update_desired_status(item,phase=_desired_phase(status),now=now,owner_id=owner_id,condition_reason=status)
        return {"schema":"bcp.reconcile_result/1","status":status,"project_id":project_id,"resource_id":resource_id,"drift":drift,"incident":incident,"field_certified":False}

    def mark_attempt_started(self,project_id:str,fingerprint:str,*,owner_id:str,now:str|None=None)->dict[str,Any]:
        now=now or utc_now(); item=self.get(project_id,fingerprint); inc=deepcopy(item["incident"]); repair=inc["repair"]
        if inc["status"]!="RECONCILING": raise IncidentError("incident not ready for repair")
        if repair["attempt_count"]>=repair["max_attempts"]:
            inc["status"]="FAILED_SAFE"; self._put(inc,owner_id=owner_id); return inc
        repair["attempt_count"]+=1; inc["last_seen_at"]=now; self._put(inc,owner_id=owner_id); return inc

    def record_step_receipt(self,project_id:str,fingerprint:str,step_id:str,receipt:dict[str,Any],*,owner_id:str,now:str|None=None)->dict[str,Any]:
        now=now or utc_now()
        if not isinstance(receipt,dict) or receipt.get("schema")!="bcp.action_receipt/1": raise ValueError("invalid action receipt")
        item=self.get(project_id,fingerprint); inc=deepcopy(item["incident"])
        target=None
        for step in inc["repair"]["planned_steps"]:
            if step["step_id"]==step_id: target=step; break
        if target is None: raise IncidentError("unknown repair step")
        if receipt.get("project_id")!=project_id or receipt.get("capability_id")!=target["capability_id"]: raise IncidentError("receipt binding mismatch")
        rid=_text(receipt.get("receipt_id"),"receipt_id",200)
        if rid not in inc["repair"]["receipt_ids"]: inc["repair"]["receipt_ids"].append(rid)
        if receipt.get("status")=="SUCCEEDED" and receipt.get("result")=="PASS":
            target["state"]="DONE"; target["block_reason"]=None
            # Deliberately remain RECONCILING until a fresh observation proves desired state.
            inc["status"]="RECONCILING"
        else:
            target["state"]="FAILED"; target["block_reason"]="ACTION_RECEIPT_FAILED"; inc["status"]="FAILED_SAFE"
        inc["last_seen_at"]=now; self._put(inc,owner_id=owner_id); return inc

    def record_friction(
        self,*,project_id:str,category:str,detail:str,source:str,avoidable:bool,user_action_required:bool,owner_id:str,now:str|None=None
    )->dict[str,Any]:
        now=now or utc_now(); category=_text(category,"friction category",128); detail=_text(detail,"friction detail",2000); source=_text(source,"friction source",128)
        reason_code="FRICTION_"+re.sub(r"[^A-Z0-9]+","_",category.upper()).strip("_")
        fp=incident_fingerprint(project_id=project_id,incident_class="FRICTION",resource_id=None,reason_code=reason_code,signature={"category":category,"source":source,"detail":detail})
        current=self.store.get_state(incident_stream_id(project_id,fp)); old=deepcopy(current["payload"]) if current else None
        recipe_item=self.recipes.select(incident_class="FRICTION",project_id=project_id,resource_kind=None,reason_code=reason_code)
        recipe=recipe_item["recipe"] if recipe_item else None
        planned=[{"step_id":s["step_id"],"capability_id":s["capability_id"],"state":"PENDING","block_reason":"FRICTION_REQUIRES_POLICY_CONTEXT"} for s in (recipe["steps"] if recipe else [])]
        inc={
            "schema":"bcp.incident/1","incident_id":f"inc-{fp[:24]}","project_id":project_id,"resource_id":None,
            "incident_class":"FRICTION","fingerprint":fp,"status":"MATCHED_RECIPE" if recipe else "OPEN",
            "occurrence_count":int((old or {}).get("occurrence_count",0))+1,"first_seen_at":(old or {}).get("first_seen_at",now),"last_seen_at":now,
            "reason":{"code":reason_code,"summary":detail,"drift_paths":[]},
            "evidence":[{"kind":"FRICTION_EVENT","status":"OBSERVED","ref":None,"value":{"source":source}}],
            "repair":{"recipe_id":recipe["recipe_id"] if recipe else None,"attempt_count":int((old or {}).get("repair",{}).get("attempt_count",0)),"max_attempts":int(recipe["policy"]["max_attempts"]) if recipe else 0,"next_retry_at":None,"planned_steps":planned,"receipt_ids":list((old or {}).get("repair",{}).get("receipt_ids",[]))},
            "friction":{"category":category,"source":source,"avoidable":bool(avoidable),"user_action_required":bool(user_action_required),"detail":detail},
        }
        self._put(inc,owner_id=owner_id); return inc

__all__=["IncidentEngine","IncidentError","IncidentNotFound","IncidentRevisionConflict","incident_fingerprint","incident_stream_id"]
