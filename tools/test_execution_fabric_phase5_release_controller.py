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
from execution_fabric.release_controller import (
    ReleaseController, ReleaseTransitionError, operation_bindings_from_adapter
)

NOW="2026-10-05T22:00:00Z"

def rel(version,seq,sha,qualification="FIELD_VERIFIED"):
    return {
        "version":version,"sequence":seq,"artifact_sha256":sha,
        "manifest_ref":f"release/{version}.json","source_revision":f"sha-{version}",
        "qualification":qualification
    }

def lkg(version="1.0.0",seq=10,sha="a"*64,scope="FIELD",proven=True):
    return {**rel(version,seq,sha),"proof_scope":scope,"proven":proven}

def policy(scope="FIELD",permission="P3_BOUNDED_SYSTEM_CHANGE",resource="R3_HEAVY",rollback=True):
    return {
        "target_scope":scope,"rollback_required":rollback,"anti_downgrade":True,
        "exact_readback_required":True,"healthcheck_required":True,
        "max_permission_class":permission,"resource_ceiling":resource
    }

def migration(kind="NONE",approval=False):
    return {
        "class":kind,"approval_granted":approval,
        "rollback_capability_required":True,"notes":None
    }

def binding(op,state="BOUND",permission=None,resource=None):
    defaults={
        "RELEASE_VERIFY":("release.verify","P0_READ","R1_LIGHT",["GIT_REVISION","HASH","TEST_RESULT"]),
        "UPDATE_STAGE":("release.stage","P1_SAFE_WRITE","R1_LIGHT",["HASH","DESTINATION_READBACK"]),
        "UPDATE_ACTIVATE":("release.activate","P2_PROJECT_MUTATION","R2_MEDIUM",["HASH","DESTINATION_READBACK"]),
        "HEALTHCHECK":("release.health","P0_READ","R0_TINY",["PROCESS_HEALTH","HTTP_HEALTH"]),
        "ROLLBACK":("release.rollback","P2_PROJECT_MUTATION","R1_LIGHT",["HASH","DESTINATION_READBACK","PROCESS_HEALTH"]),
    }
    cap,p,r,e=defaults[op]
    return {
        "operation":op,"capability_id":cap,"provider_id":"BCP_NATIVE_PC","state":state,
        "permission_class":permission or p,"resource_class":resource or r,
        "evidence_contract":e,"input_defaults":{},"binding_reason":"test"
    }

def adapter(project="BCP_CORE", mutate=None):
    binds=[binding(op) for op in ("RELEASE_VERIFY","UPDATE_STAGE","UPDATE_ACTIVATE","HEALTHCHECK","ROLLBACK")]
    if mutate:
        mutate(binds)
    return {
        "schema":"bcp.project_adapter/1","adapter_id":"test.release.adapter",
        "project_id":project,"version":"1","bindings":binds,
        "source_revision":"phase5-test","notes":[]
    }

def receipt(tx,op,*,success=True,scope=None,field=None,missing_evidence=None,rid=None):
    b=tx["operations"][op]
    if scope is None:
        scope="FIELD" if op in {"UPDATE_ACTIVATE","HEALTHCHECK","ROLLBACK"} and tx["policy"]["target_scope"]=="FIELD" else "REPOSITORY"
    if field is None:
        field=(scope=="FIELD")
    ev=[]
    for kind in b["evidence_contract"]:
        if kind==missing_evidence: continue
        ev.append({
            "evidence_id":f"{op.lower()}-{kind.lower()}","kind":kind,
            "status":"PASS","value":{"ok":True},"sha256":None,
            "source":"phase5-test","observed_at":NOW
        })
    return {
        "schema":"bcp.action_receipt/1",
        "receipt_id":rid or f"receipt-{op.lower()}-0001",
        "mission_id":"mission-release-test","project_id":tx["project_id"],
        "action_id":op.lower(),"job_id":None,"step_id":op.lower(),
        "capability_id":b["capability_id"],"provider_id":b["provider_id"],"node_id":"TEST",
        "idempotency_key":f"idem-{tx['release_id']}-{op}",
        "status":"SUCCEEDED" if success else "FAILED",
        "result":"PASS" if success else "FAIL",
        "proof_scope":scope,"field_certified":field,"durability":"PROVIDER_COMMITTED",
        "committed_revision":1,"fencing_token":1,"content_hash":None,
        "predecessor_hash":None,"output_hash":None,"source_revision":"test",
        "environment_fingerprint":"test","outbox_message_id":None,"idempotent_replay":False,
        "evidence":ev,"readback":{"status":"PASS" if success else "FAIL","summary":"test","observed_revision":"test"},
        "side_effects":[],"error":None if success else {"class":"TEST","code":"FAIL","detail":"test failure","retryable":False},
        "created_at":NOW,"committed_at":NOW
    }

class ReleaseControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CriticalStore(pathlib.Path(self.tmp.name)/"bcp.sqlite3")
        self.c=ReleaseController(self.store)

    def tearDown(self): self.tmp.cleanup()

    def create(self,release_id="release-11",candidate=None,current=None,lkg_ref=None,adapter_obj=None,policy_obj=None,migration_obj=None,mode="GREEN",project="BCP_CORE"):
        return self.c.create(
            release_id=release_id,project_id=project,
            candidate=candidate or rel("2.0.0",11,"b"*64,"CI_QUALIFIED"),
            current=current if current is not None else rel("1.0.0",10,"a"*64),
            lkg=lkg_ref if lkg_ref is not None else lkg(),
            migration=migration_obj or migration(),
            policy=policy_obj or policy(),
            adapter=adapter_obj or adapter(project),
            resource_mode=mode,owner_id="test",now=NOW
        )

    def progress_to_health(self,tx):
        tx=self.c.record_operation_receipt(tx["project_id"],tx["release_id"],"RELEASE_VERIFY",receipt(tx,"RELEASE_VERIFY"),owner_id="r")
        self.assertEqual(tx["state"],"STAGE_READY")
        tx=self.c.record_operation_receipt(tx["project_id"],tx["release_id"],"UPDATE_STAGE",receipt(tx,"UPDATE_STAGE"),owner_id="r")
        self.assertEqual(tx["state"],"ACTIVATE_READY")
        tx=self.c.record_operation_receipt(tx["project_id"],tx["release_id"],"UPDATE_ACTIVATE",receipt(tx,"UPDATE_ACTIVATE"),owner_id="r")
        self.assertEqual(tx["state"],"HEALTH_PENDING")
        tx=self.c.record_operation_receipt(tx["project_id"],tx["release_id"],"HEALTHCHECK",receipt(tx,"HEALTHCHECK"),owner_id="r")
        self.assertEqual(tx["state"],"HEALTH_PENDING")
        return tx

    def commit_happy(self,tx):
        tx=self.progress_to_health(tx)
        with self.assertRaises(ReleaseTransitionError):
            self.c.commit(tx["project_id"],tx["release_id"],owner_id="too-early")
        cand=tx["candidate"]
        tx=self.c.record_candidate_readback(
            tx["project_id"],tx["release_id"],observed_version=cand["version"],
            observed_sequence=cand["sequence"],observed_sha256=cand["artifact_sha256"],
            health="PASS",owner_id="observer"
        )
        self.assertEqual(tx["state"],"COMMIT_READY")
        tx=self.c.commit(tx["project_id"],tx["release_id"],owner_id="commit")
        self.assertEqual(tx["state"],"COMMITTED")
        return tx

    def test_happy_path_requires_exact_readback_before_commit(self):
        tx=self.create()
        self.assertEqual(tx["state"],"VERIFY_READY")
        tx=self.commit_happy(tx)
        self.assertEqual(tx["readback"]["status"],"PASS")
        latest=self.c.latest_committed("BCP_CORE")
        self.assertEqual(latest["transaction"]["release_id"],tx["release_id"])

    def test_transaction_uses_shared_outbox(self):
        tx=self.create()
        due=self.store.due_outbox(limit=20)
        self.assertEqual(len(due),1)
        self.assertEqual(due[0]["destination"],"BCP_RELEASE_TRANSACTION")
        self.assertEqual(due[0]["envelope"]["payload"]["release_id"],tx["release_id"])

    def test_normal_downgrade_is_never_activated(self):
        tx=self.create(candidate=rel("0.9.0",9,"c"*64))
        self.assertEqual(tx["state"],"SUPERSEDED_NO_ROLLBACK")
        self.assertEqual(tx["failure"]["code"],"RELEASE_LINE_RECONCILIATION_REQUIRED")

    def test_field_activation_requires_proven_field_lkg(self):
        tx=self.create(lkg_ref=lkg(scope="REPOSITORY",proven=True))
        self.assertEqual(tx["state"],"WAITING_LKG")
        tx2=self.create(release_id="release-no-lkg",lkg_ref=None)
        # default helper supplies LKG when None; exercise explicit controller instead.
        tx2=self.c.create(
            release_id="release-no-lkg-2",project_id="BCP_CORE",
            candidate=rel("2.0.1",12,"d"*64,"CI_QUALIFIED"),current=rel("1.0.0",10,"a"*64),
            lkg=None,migration=migration(),policy=policy(),adapter=adapter(),
            resource_mode="GREEN",owner_id="test"
        )
        self.assertEqual(tx2["state"],"WAITING_LKG")

    def test_irreversible_migration_waits_for_approval(self):
        tx=self.create(migration_obj=migration("IRREVERSIBLE",False))
        self.assertEqual(tx["state"],"WAITING_APPROVAL")

    def test_p4_binding_is_represented_but_not_auto_admitted(self):
        def mutate(bs):
            for b in bs:
                if b["operation"]=="UPDATE_ACTIVATE":
                    b["permission_class"]="P4_DESTRUCTIVE_OR_SECURITY_SENSITIVE"
        tx=self.create(adapter_obj=adapter(mutate=mutate))
        self.assertEqual(tx["state"],"WAITING_APPROVAL")
        self.assertEqual(tx["failure"]["operation"],"UPDATE_ACTIVATE")

    def test_amber_blocks_medium_activation(self):
        tx=self.create(mode="AMBER")
        # verify/stage are <=R1, activation is R2 and should hold at creation preflight.
        self.assertEqual(tx["state"],"WAITING_RESOURCE")
        self.assertEqual(tx["failure"]["operation"],"UPDATE_ACTIVATE")

    def test_med_rebuild_remains_waiting_capability(self):
        med=json.loads((ROOT/"docs"/"examples"/"execution-fabric"/"med-rebuild.project-adapter.example.json").read_text(encoding="utf-8"))
        ops=operation_bindings_from_adapter(med)
        self.assertEqual(ops["UPDATE_STAGE"]["state"],"UNSUPPORTED")
        tx=self.c.create(
            release_id="med-candidate-example",project_id="MED_REBUILD",
            candidate=rel("example-candidate",2,"e"*64,"CI_QUALIFIED"),
            current=rel("example-current",1,"f"*64,"FIELD_VERIFIED"),
            lkg={**rel("example-current",1,"f"*64,"FIELD_VERIFIED"),"proof_scope":"SIMULATION","proven":True},
            migration=migration(),policy=policy(scope="SIMULATION"),
            adapter=med,resource_mode="GREEN",owner_id="test"
        )
        self.assertEqual(tx["state"],"WAITING_CAPABILITY")
        self.assertEqual(tx["failure"]["operation"],"UPDATE_STAGE")

    def test_field_receipt_scope_and_evidence_are_enforced(self):
        tx=self.create()
        tx=self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"RELEASE_VERIFY",receipt(tx,"RELEASE_VERIFY"),owner_id="r")
        tx=self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"UPDATE_STAGE",receipt(tx,"UPDATE_STAGE"),owner_id="r")
        weak=receipt(tx,"UPDATE_ACTIVATE",scope="PROVIDER",field=False)
        with self.assertRaisesRegex(ReleaseTransitionError,"proof scope too weak"):
            self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"UPDATE_ACTIVATE",weak,owner_id="r")
        untrusted_field=receipt(tx,"UPDATE_ACTIVATE",scope="FIELD",field=False)
        with self.assertRaisesRegex(ReleaseTransitionError,"field-certified"):
            self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"UPDATE_ACTIVATE",untrusted_field,owner_id="r")
        incomplete=receipt(tx,"UPDATE_ACTIVATE",missing_evidence="DESTINATION_READBACK")
        with self.assertRaisesRegex(ReleaseTransitionError,"evidence contract incomplete"):
            self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"UPDATE_ACTIVATE",incomplete,owner_id="r")
        self.assertEqual(self.c.get("BCP_CORE",tx["release_id"])["transaction"]["state"],"ACTIVATE_READY")

    def test_failed_activation_rolls_back_only_to_exact_lkg(self):
        tx=self.create()
        tx=self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"RELEASE_VERIFY",receipt(tx,"RELEASE_VERIFY"),owner_id="r")
        tx=self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"UPDATE_STAGE",receipt(tx,"UPDATE_STAGE"),owner_id="r")
        tx=self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"UPDATE_ACTIVATE",receipt(tx,"UPDATE_ACTIVATE",success=False),owner_id="r")
        self.assertEqual(tx["state"],"ROLLBACK_REQUIRED")
        tx=self.c.prepare_rollback("BCP_CORE",tx["release_id"],owner_id="r",resource_mode="GREEN")
        self.assertEqual(tx["state"],"ROLLBACK_READY")
        tx=self.c.record_operation_receipt("BCP_CORE",tx["release_id"],"ROLLBACK",receipt(tx,"ROLLBACK"),owner_id="r")
        self.assertEqual(tx["state"],"ROLLBACK_READBACK_PENDING")
        ref=tx["lkg"]
        tx=self.c.record_rollback_readback(
            "BCP_CORE",tx["release_id"],observed_version=ref["version"],
            observed_sequence=ref["sequence"],observed_sha256=ref["artifact_sha256"],
            health="PASS",owner_id="observer"
        )
        self.assertEqual(tx["state"],"ROLLED_BACK")

    def test_candidate_readback_mismatch_requires_rollback(self):
        tx=self.progress_to_health(self.create())
        tx=self.c.record_candidate_readback(
            "BCP_CORE",tx["release_id"],observed_version="WRONG",
            observed_sequence=tx["candidate"]["sequence"],observed_sha256=tx["candidate"]["artifact_sha256"],
            health="PASS",owner_id="observer"
        )
        self.assertEqual(tx["state"],"ROLLBACK_REQUIRED")
        self.assertEqual(tx["readback"]["status"],"FAIL")

    def test_stale_interrupted_transaction_never_rolls_back_newer_commit(self):
        stale=self.create(release_id="release-stale",candidate=rel("2.0.0",11,"b"*64))
        newer=self.create(release_id="release-newer",candidate=rel("3.0.0",12,"c"*64),current=rel("2.0.0",11,"b"*64),lkg_ref={**rel("2.0.0",11,"b"*64),"proof_scope":"FIELD","proven":True})
        newer=self.commit_happy(newer)
        recovered=self.c.recover_incomplete("BCP_CORE",stale["release_id"],owner_id="recovery")
        self.assertEqual(recovered["state"],"SUPERSEDED_NO_ROLLBACK")
        self.assertEqual(recovered["failure"]["code"],"SUPERSEDED_NO_ROLLBACK")
        self.assertEqual(self.c.latest_committed("BCP_CORE")["transaction"]["release_id"],newer["release_id"])

    def test_adapter_project_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"does not match"):
            self.c.create(
                release_id="bad-project",project_id="BCP_CORE",
                candidate=rel("2.0.0",11,"b"*64),current=rel("1.0.0",10,"a"*64),
                lkg=lkg(),migration=migration(),policy=policy(),
                adapter=adapter("OTHER"),resource_mode="GREEN",owner_id="test"
            )

if __name__=="__main__":
    unittest.main()
