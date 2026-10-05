from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
WINDOWS=ROOT/"windows"
sys.path.insert(0,str(WINDOWS))

from execution_fabric.critical_store import CriticalStore
from execution_fabric.desired_state import DesiredStateStore, deep_drift, validate_desired_resource
from execution_fabric.repair_recipes import RecipeRegistry, validate_recipe
from execution_fabric.incident_engine import IncidentEngine

def desired(*,mode="AUTO_PROJECT",perm="P2_PROJECT_MUTATION",ceiling="R2_MEDIUM",attempts=3):
    return {
        "schema":"bcp.desired_state_resource/1","api_version":"bcp/v1","kind":"DemoResource",
        "metadata":{"resource_id":"demo-resource","project_id":"BCP_CORE","generation":1,"created_at":"2026-10-05T21:45:00Z","updated_at":None,"owner":"BCP_POLICY"},
        "spec":{
            "desired":{"enabled":True,"version":"1"},
            "reconcile_policy":{"mode":mode,"max_permission_class":perm,"resource_ceiling":ceiling,"repair_backoff_seconds":10,"max_attempts_per_incident":attempts},
            "evidence_contract":["TEST_RESULT"],"dependencies":[]
        },
        "status":{"observed_generation":0,"phase":"UNKNOWN","last_observed_at":None,"last_reconciled_at":None,"conditions":[]}
    }

def recipe(*,status="FIELD_VALIDATED",auto=True,perm="P1_SAFE_WRITE",resource="R1_LIGHT",capability="demo.repair",attempts=3,incident_class="DRIFT",reason="DESIRED_STATE_DRIFT"):
    return {
        "schema":"bcp.repair_recipe/1","recipe_id":f"demo.{incident_class.lower()}.repair","version":"1.0.0","status":status,"auto_eligible":auto,
        "match":{"incident_class":incident_class,"resource_kind":"DemoResource" if incident_class=="DRIFT" else None,"reason_codes":[reason],"project_ids":["BCP_CORE"]},
        "policy":{"max_permission_class":perm,"max_resource_class":resource,"max_attempts":attempts,"backoff_seconds":10,"rollback_required":False},
        "steps":[{
            "step_id":"repair","capability_id":capability,"permission_class":perm,"resource_class":resource,
            "evidence_contract":["TEST_RESULT"],"input_defaults":{"target":"demo"},"on_failure":"STOP_FAIL_SAFE"
        }],
        "source_revision":"phase4-test","ledger_refs":[],"regression_refs":[],"notes":[]
    }

class Phase4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CriticalStore(pathlib.Path(self.tmp.name)/"bcp.sqlite3")
        self.desired=DesiredStateStore(self.store)
        self.recipes=RecipeRegistry(self.store)
        self.engine=IncidentEngine(self.store)

    def tearDown(self): self.tmp.cleanup()

    def seed_desired(self,**kw):
        r=desired(**kw)
        self.desired.put(r,owner_id="test")
        return r

    def seed_recipe(self,**kw):
        r=recipe(**kw)
        self.recipes.put(r,owner_id="test")
        return r

    def test_desired_store_uses_same_fenced_outbox(self):
        r=self.seed_desired()
        got=self.desired.get("BCP_CORE","demo-resource")
        self.assertEqual(got["resource"],r)
        self.assertEqual(got["revision"],1)
        second=self.desired.put(r,owner_id="again")
        self.assertEqual(second["status"],"UNCHANGED")
        due=self.store.due_outbox(limit=10)
        self.assertEqual(len(due),1)
        self.assertEqual(due[0]["destination"],"BCP_DESIRED_STATE")

    def test_deep_drift_is_subset_based_and_stable(self):
        self.assertEqual(deep_drift({"a":1},{"a":1,"extra":2}),[])
        drift=deep_drift({"a":{"b":1},"x":[1,2]},{"a":{"b":2},"x":[1,3],"extra":True})
        self.assertEqual([x["path"] for x in drift],["$/a/b","$/x"])

    def test_ledger_recipe_is_not_auto_eligible(self):
        path=ROOT/"docs"/"examples"/"execution-fabric"/"bcp-startup.repair-recipe.example.json"
        r=json.loads(path.read_text(encoding="utf-8"))
        validate_recipe(r)
        self.assertEqual(r["status"],"REPOSITORY_VALIDATED")
        self.assertFalse(r["auto_eligible"])
        bad=json.loads(json.dumps(r)); bad["auto_eligible"]=True
        with self.assertRaisesRegex(ValueError,"FIELD_VALIDATED"): validate_recipe(bad)

    def test_recipe_forbids_freeform_execution(self):
        r=recipe()
        r["steps"][0]["input_defaults"]={"command":"cmd.exe /c whoami"}
        with self.assertRaisesRegex(ValueError,"forbidden executable"): validate_recipe(r)

    def test_no_recipe_goes_to_needs_reasoning(self):
        self.seed_desired()
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":False,"version":"1"},capability_states={},resource_mode="GREEN",owner_id="reconciler",now="2026-10-05T21:46:00Z")
        self.assertEqual(out["status"],"NEEDS_REASONING")
        self.assertEqual(out["incident"]["repair"]["recipe_id"],None)
        self.assertEqual(self.desired.get("BCP_CORE","demo-resource")["resource"]["status"]["phase"],"DEGRADED")

    def test_repository_validated_recipe_waits_for_approval(self):
        self.seed_desired(mode="AUTO_BOUNDED_SYSTEM",perm="P3_BOUNDED_SYSTEM_CHANGE")
        r=recipe(status="REPOSITORY_VALIDATED",auto=False)
        self.recipes.put(r,owner_id="recipe")
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"AVAILABLE"},resource_mode="GREEN",owner_id="reconciler")
        self.assertEqual(out["status"],"WAITING_APPROVAL")
        self.assertEqual(out["incident"]["repair"]["planned_steps"][0]["block_reason"],"RECIPE_NOT_FIELD_VALIDATED")

    def test_permission_resource_and_capability_blockers(self):
        self.seed_desired(perm="P0_READ",ceiling="R3_HEAVY")
        self.seed_recipe(perm="P1_SAFE_WRITE")
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"AVAILABLE"},resource_mode="GREEN",owner_id="p")
        self.assertEqual(out["status"],"WAITING_APPROVAL")

        # New resource isolates the next blocker.
        d=desired(perm="P3_BOUNDED_SYSTEM_CHANGE",ceiling="R3_HEAVY"); d["metadata"]["resource_id"]="resource-2"
        self.desired.put(d,owner_id="d2")
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="resource-2",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"AVAILABLE"},resource_mode="AMBER",owner_id="r2")
        self.assertEqual(out["status"],"WAITING_RESOURCE")

        d=desired(perm="P3_BOUNDED_SYSTEM_CHANGE",ceiling="R3_HEAVY"); d["metadata"]["resource_id"]="resource-3"
        self.desired.put(d,owner_id="d3")
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="resource-3",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"TEMP_UNAVAILABLE"},resource_mode="GREEN",owner_id="r3")
        self.assertEqual(out["status"],"WAITING_CAPABILITY")

    def test_ready_recipe_receipt_cannot_false_recover(self):
        self.seed_desired()
        self.seed_recipe()
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"AVAILABLE"},resource_mode="GREEN",owner_id="r",now="2026-10-05T21:46:00Z")
        self.assertEqual(out["status"],"RECONCILING")
        fp=out["incident"]["fingerprint"]
        inc=self.engine.mark_attempt_started("BCP_CORE",fp,owner_id="dispatcher",now="2026-10-05T21:46:10Z")
        self.assertEqual(inc["repair"]["attempt_count"],1)
        receipt={"schema":"bcp.action_receipt/1","receipt_id":"receipt-demo-0001","project_id":"BCP_CORE","capability_id":"demo.repair","status":"SUCCEEDED","result":"PASS"}
        inc=self.engine.record_step_receipt("BCP_CORE",fp,"repair",receipt,owner_id="dispatcher",now="2026-10-05T21:46:20Z")
        self.assertEqual(inc["status"],"RECONCILING")
        self.assertEqual(inc["repair"]["planned_steps"][0]["state"],"DONE")
        # Only fresh observation closes the incident.
        final=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":True,"version":"1","extra":"ok"},capability_states={},resource_mode="GREEN",owner_id="observer",now="2026-10-05T21:47:00Z")
        self.assertEqual(final["status"],"IN_SYNC")
        self.assertEqual(self.engine.get("BCP_CORE",fp)["incident"]["status"],"RECOVERED")

    def test_attempt_ceiling_fails_safe(self):
        self.seed_desired(attempts=1); self.seed_recipe(attempts=1)
        out=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"AVAILABLE"},resource_mode="GREEN",owner_id="r")
        fp=out["incident"]["fingerprint"]
        self.engine.mark_attempt_started("BCP_CORE",fp,owner_id="d")
        again=self.engine.reconcile(project_id="BCP_CORE",resource_id="demo-resource",observed={"enabled":False,"version":"1"},capability_states={"demo.repair":"AVAILABLE"},resource_mode="GREEN",owner_id="r2")
        self.assertEqual(again["status"],"FAILED_SAFE")

    def test_friction_is_durable_and_deduplicated_by_fingerprint(self):
        a=self.engine.record_friction(project_id="BCP_CORE",category="REPEATED_MANUAL_QR",detail="User had to repeat pairing mechanics",source="CHATGPT",avoidable=True,user_action_required=True,owner_id="f",now="2026-10-05T21:50:00Z")
        b=self.engine.record_friction(project_id="BCP_CORE",category="REPEATED_MANUAL_QR",detail="User had to repeat pairing mechanics",source="CHATGPT",avoidable=True,user_action_required=True,owner_id="f",now="2026-10-05T21:51:00Z")
        self.assertEqual(a["fingerprint"],b["fingerprint"])
        self.assertEqual(b["occurrence_count"],2)
        self.assertEqual(b["incident_class"],"FRICTION")

    def test_example_desired_state_validates(self):
        p=ROOT/"docs"/"examples"/"execution-fabric"/"bcp-microkernel-startup.desired-state.example.json"
        x=json.loads(p.read_text(encoding="utf-8"))
        validate_desired_resource(x)
        self.assertEqual(x["status"]["phase"],"UNKNOWN")

if __name__=="__main__": unittest.main()
