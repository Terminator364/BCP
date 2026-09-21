from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "release" / "current.json"
SERVER = ROOT / "release" / "server.json"
ANDROID = ROOT / "release" / "android.json"
NEXUS = ROOT / "release" / "nexus_bootstrap.json"
TELEGRAM = ROOT / "release" / "telegram_observability.json"
SERVER_SOURCE = ROOT / "windows" / "bcp_server.py"
INSTALLER_SOURCE = ROOT / "windows" / "INSTALL_BCP_FINAL.ps1"
ACCEPTANCE_SOURCE = ROOT / "windows" / "BCP_FINAL_ACCEPTANCE_CURRENT.ps1"
TELEGRAM_SOURCE = ROOT / "windows" / "bcp_telegram_observability.py"
SPEC = ROOT / "docs" / "CANONICAL_PRODUCT_REQUIREMENTS.md"
CADENCE_POLICY = ROOT / ".project-memory" / "INTERACTIVE_WORK_CADENCE_POLICY.json"
DELIVERY_POLICY = ROOT / ".project-memory" / "DELIVERY_REDUNDANCY_POLICY.json"
PRE_HUMAN_POLICY = ROOT / ".project-memory" / "PRE_HUMAN_ACTION_SIMULATION_POLICY.json"
HUMAN_ACTION_MATRIX = ROOT / ".project-memory" / "HUMAN_ACTION_QUALIFICATION_MATRIX.json"
ABC_TRACEABILITY = ROOT / ".project-memory" / "ABC_REQUIREMENTS_TRACEABILITY.json"
ABC_SPEC = ROOT / "docs" / "BCP_CANONICAL_SPEC_ABC_R76.md"
COMMUNICATION_POLICY = ROOT / ".project-memory" / "COMMUNICATION_SURVIVAL_POLICY.json"
COMM_PROTOCOL = ROOT / ".project-memory" / "COMMUNICATION_PROTOCOL.json"
COMM_STATE_MACHINE = ROOT / ".project-memory" / "COMMUNICATION_STATE_MACHINE.json"
NEW_CONVERSATION_TAKEOVER = ROOT / ".project-memory" / "NEW_CONVERSATION_TAKEOVER.json"


def fail(message: str) -> None:
    raise SystemExit("BCP_CURRENT_RELEASE_INVALID: " + message)


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        fail(path.as_posix() + " not object")
    return obj


def is_sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value or ""))


def version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for item in str(value or "").split("-", 1)[0].split("."):
        try:
            parts.append(int(item))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def main() -> int:
    cur = load(CURRENT)
    srv = load(SERVER)
    edge = load(ANDROID)
    nexus_manifest = load(NEXUS)
    telegram_manifest = load(TELEGRAM)
    source = SERVER_SOURCE.read_bytes()
    telegram_source = TELEGRAM_SOURCE.read_bytes()
    installer_source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    acceptance_source = ACCEPTANCE_SOURCE.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")
    cadence = load(CADENCE_POLICY)
    delivery = load(DELIVERY_POLICY)
    pre_human = load(PRE_HUMAN_POLICY)
    active_tranche = load(ROOT / ".project-memory" / "ACTIVE_TRANCHE.json")
    human_actions = load(HUMAN_ACTION_MATRIX)
    abc = load(ABC_TRACEABILITY)
    abc_spec = ABC_SPEC.read_text(encoding="utf-8")
    communication = load(COMMUNICATION_POLICY)
    comm_protocol = load(COMM_PROTOCOL)
    comm_state_machine = load(COMM_STATE_MACHINE)
    takeover = load(NEW_CONVERSATION_TAKEOVER)

    if cur.get("schema") != "bcp.current_release/1":
        fail("schema")
    if cur.get("channel") != "CURRENT":
        fail("channel")
    if cur.get("zero_usd") is not True:
        fail("zero_usd")
    policy = cur.get("update_policy") or {}
    required_policy = {
        "unchanged_version_zero_download": True,
        "metered_large_download_default": False,
        "hash_verification_required": True,
        "rollback_required": True,
        "scheduled_chatgpt_automation": False,
    }
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            fail("policy." + key)

    if int(cadence.get("target_minutes") or 0) != 25:
        fail("cadence_target_not_25")
    window = cadence.get("acceptable_window_minutes") or []
    if window != [23, 25]:
        fail("cadence_window_not_23_25")
    if delivery.get("channels", {}).get("email", {}).get("send_before_chat_pointer") is not True:
        fail("email_first_delivery_contract")
    if delivery.get("channels", {}).get("chatgpt", {}).get("role") != "POINTER_ONLY_AFTER_SUCCESSFUL_EMAIL_END_ACK":
        fail("chat_pointer_only_contract")
    if not str(active_tranche.get("delivery_key") or "").startswith("BCP25-"):
        fail("active_tranche_delivery_key_contract")
    if active_tranche.get("close_owner") != "PRIMARY_ASSISTANT":
        fail("active_tranche_primary_close_owner")
    if active_tranche.get("final_app_reply_gate") not in {"END_ACK_REQUIRED", "OPEN_AFTER_END_ACK"}:
        fail("active_tranche_final_reply_gate")
    if active_tranche.get("communication_guard", {}).get("user_message_is_not_normal_closeout_trigger") is not True:
        fail("active_tranche_user_message_normal_trigger_contract")
    email = delivery.get("channels", {}).get("email", {})
    if email.get("start_notice_required_before_substantive_work") is not True:
        fail("start_email_before_work_contract")
    if email.get("end_checkpoint_required") is not True:
        fail("end_email_checkpoint_contract")
    if email.get("end_mail_retry_required") is not True:
        fail("end_email_retry_contract")
    if email.get("end_mail_provider_ack_required") is not True:
        fail("end_email_provider_ack_contract")
    if email.get("chat_output_before_end_ack_forbidden") is not True:
        fail("chat_before_end_email_ack_forbidden_contract")
    cadence_delivery = delivery.get("cadence") or {}
    if cadence_delivery.get("two_guard_closeout_required") is not False:
        fail("dual_closeout_guard_contract")
    if int(cadence_delivery.get("normal_closeout_offset_minutes") or 0) != 23:
        fail("normal_closeout_offset_contract")
    if int(cadence_delivery.get("backup_earliest_offset_minutes") or 0) != 28:
        fail("backup_earliest_offset_contract")
    if cadence_delivery.get("hard_close_guard_offset_minutes") is not None:
        fail("hard_close_guard_must_be_disabled")
    if int(cadence_delivery.get("absolute_end_deadline_minutes") or 0) != 25:
        fail("absolute_end_deadline_contract")
    if cadence_delivery.get("user_relaunch_must_never_be_required") is not True:
        fail("user_relaunch_dependency_contract")
    if delivery.get("checkpoint_delivery_order") != ["EMAIL_START_NOTICE","SUBSTANTIVE_WORK","EMAIL_END_FULL_CHECKPOINT_RETRY_UNTIL_ACK","CHATGPT_POINTER_ONLY_AFTER_EMAIL_END_ACK","TELEGRAM_WITNESS_OPTIONAL"]:
        fail("start_work_end_chat_order_contract")
    if pre_human.get("default_rule") != "NO_HUMAN_ACTION_INSTRUCTION_BEFORE_REPRESENTATIVE_SIMULATION_WHEN_TECHNICALLY_FEASIBLE":
        fail("pre_human_action_simulation_contract")
    if "RUNTIME_PATH" not in (pre_human.get("required_layers") or []):
        fail("pre_human_runtime_layer_missing")
    if pre_human.get("qualification_matrix_ref") != ".project-memory/HUMAN_ACTION_QUALIFICATION_MATRIX.json":
        fail("human_action_matrix_ref_drift")
    if communication.get("schema") != "bcp.communication_survival_policy/4":
        fail("communication_survival_schema")
    if communication.get("cold_recovery", {}).get("code") != "BCPGO BCP":
        fail("communication_cold_recovery_code")
    if communication.get("checkpoint_protocol", {}).get("target_minutes") != 25:
        fail("communication_25_minute_checkpoint")
    if communication.get("channels", {}).get("gmail", {}).get("end_retry_until_provider_ack") is not True:
        fail("communication_gmail_end_ack")
    if communication.get("channels", {}).get("phone_edge", {}).get("store_and_forward") is not True:
        fail("communication_phone_store_forward")
    if communication.get("channels", {}).get("telegram", {}).get("fallback_path") != "PC_TO_PHONE_EDGE_CONNECT_RELAY_TO_TELEGRAM":
        fail("communication_telegram_edge_fallback")
    if communication.get("anti_false_success", {}).get("phone_queue_accepted_is_not_remote_delivery") is not True:
        fail("communication_evidence_truth_boundary")
    if communication.get("anti_false_success", {}).get("scheduler_completed_is_not_delivery") is not True:
        fail("scheduler_completion_truth_boundary")
    if email.get("scheduler_completion_is_not_delivery_proof") is not True:
        fail("email_scheduler_completion_truth_boundary")
    if email.get("foreground_end_send_primary") is not True:
        fail("foreground_end_send_primary_contract")
    if email.get("delivery_key_required") is not True:
        fail("email_delivery_key_contract")
    if comm_protocol.get("schema") != "bcp.communication_protocol/2":
        fail("communication_protocol_schema")
    if comm_protocol.get("normal_close_owner") != "PRIMARY_ASSISTANT":
        fail("communication_primary_owner")
    if comm_protocol.get("cadence_minutes") != 25 or comm_protocol.get("primary_work_budget_minutes") != 23:
        fail("communication_protocol_cadence")
    if comm_protocol.get("normal_close_reserve_minutes") != 4:
        fail("communication_close_reserve")
    if comm_protocol.get("backup_earliest_offset_minutes") != 28 or comm_protocol.get("hard_guard_offset_minutes") != 29:
        fail("communication_backup_offsets")
    if comm_state_machine.get("schema") != "bcp.communication_state_machine/1":
        fail("communication_state_machine_schema")
    if comm_state_machine.get("useful_work_minutes") != 23 or comm_state_machine.get("normal_close_reserve_minutes") != 2:
        fail("communication_state_machine_cadence")
    if "END_SEND_PENDING->END_ACKNOWLEDGED" not in (comm_state_machine.get("normal_path") or []):
        fail("communication_state_machine_end_ack")
    if takeover.get("trigger_code") != "BCPGO BCP":
        fail("new_conversation_takeover_code")
    if takeover.get("communication_contract", {}).get("normal_close_owner") != "PRIMARY_ASSISTANT":
        fail("new_conversation_takeover_close_owner")
    if abc.get("schema") != "bcp.abc_requirements_traceability/1":
        fail("abc_traceability_schema")
    if abc.get("scoring", {}).get("weights_total") != 100:
        fail("abc_traceability_weight_total")
    if "A+B+C" not in abc_spec:
        fail("abc_spec_rule_missing")
    if android_candidate.get("abc_spec_revision") != "2026-09-21-R76":
        fail("android_candidate_abc_spec_revision")
    if android_candidate.get("abc_traceability_ref") != ".project-memory/ABC_REQUIREMENTS_TRACEABILITY.json":
        fail("android_candidate_abc_traceability_ref")
    if human_actions.get("schema") != "bcp.human_action_qualification_matrix/1":
        fail("human_action_matrix_schema")
    actions = human_actions.get("actions") or []
    by_id = {str(a.get("action_id") or ""): a for a in actions}
    required_action_ids = {
        "WINDOWS_INSTALL_OR_UPDATE",
        "WINDOWS_FINAL_ACCEPTANCE",
        "NEXUS_FRESH_DEVICE_AUTH",
        "ANDROID_BEDGE_INSTALL_OR_OPEN",
    }
    if set(by_id) != required_action_ids:
        fail("human_action_matrix_coverage")
    for action_id, action in by_id.items():
        if not (action.get("entrypoints") or []):
            fail("human_action_entrypoint_missing:" + action_id)
        if not (action.get("required_workflows") or []):
            fail("human_action_workflow_missing:" + action_id)
        if not (action.get("required_evidence") or []):
            fail("human_action_evidence_missing:" + action_id)
        if not (action.get("remaining_field_boundary") or []):
            fail("human_action_field_boundary_missing:" + action_id)
    workflow_names = set()
    for workflow_path in (ROOT / ".github" / "workflows").glob("*.yml"):
        head = workflow_path.read_text(encoding="utf-8", errors="replace")
        wm = re.search(r"^name:\s*(.+?)\s*$", head, re.M)
        if wm:
            workflow_names.add(wm.group(1).strip())
    for action_id, action in by_id.items():
        for workflow_name in action.get("required_workflows") or []:
            if workflow_name not in workflow_names:
                fail("human_action_workflow_not_found:" + action_id + ":" + workflow_name)

    android_action = by_id["ANDROID_BEDGE_INSTALL_OR_OPEN"]
    if "android_emulator_api_35" not in (android_action.get("representative_environment") or []):
        fail("android_emulator_qualification_missing")
    nexus_action = by_id["NEXUS_FRESH_DEVICE_AUTH"]
    evidence = set(nexus_action.get("required_evidence") or [])
    if not {"202_LAUNCHED_positive_control", "500_HOLD_negative_control"}.issubset(evidence):
        fail("nexus_positive_negative_controls_missing")

    m = re.search(r"^Revision:\s*(\S+)", spec, re.M)
    if not m or m.group(1) != cur.get("requirements_revision"):
        fail("requirements_revision_not_current")

    components = cur.get("components") or {}
    pc = components.get("windows_bcp") or {}
    android = components.get("android_b_edge") or {}
    nexus = components.get("nexus") or {}
    telegram = cur.get("telegram_cockpit") or {}

    expected_revision = str(cur.get("requirements_revision") or "")
    for name, manifest in [
        ("server", srv),
        ("android", edge),
        ("nexus", nexus_manifest),
        ("telegram", telegram_manifest),
    ]:
        if str(manifest.get("requirements_revision") or "") != expected_revision:
            fail(name + "_requirements_revision_drift")

    actual_server_sha = hashlib.sha256(source).hexdigest()
    if pc.get("version") != str(srv.get("version")):
        fail("server_version_drift")
    if pc.get("artifact", {}).get("url") != str(srv.get("url")):
        fail("server_url_drift")
    if pc.get("artifact", {}).get("sha256") != str(srv.get("sha256")):
        fail("server_manifest_sha_drift")
    if actual_server_sha != str(srv.get("sha256")):
        fail("server_source_sha_drift")
    if pc.get("distribution_ready") is not True or pc.get("auto_update_eligible") is not True:
        fail("server_distribution_contract")

    release_version = str(srv.get("version") or "")
    installer_match = re.search(r'\$InstallerVersion\s*=\s*"([^"]+)"', installer_source)
    acceptance_match = re.search(r'\$TargetVersion\s*=\s*"([^"]+)"', acceptance_source)
    if not installer_match or installer_match.group(1) != release_version:
        fail("installer_version_pin_drift")
    if not acceptance_match or acceptance_match.group(1) != release_version:
        fail("acceptance_version_pin_drift")

    if android.get("version") != str(edge.get("version_name")):
        fail("android_version_drift")
    if version_tuple(str(srv.get("version"))) < version_tuple(str(edge.get("minimum_server_version"))):
        fail("component_compatibility_drift")

    edge_url = str(edge.get("apk_url") or "")
    edge_sha = str(edge.get("apk_sha256") or "")
    edge_ready = bool(edge_url and is_sha(edge_sha))
    if bool(android.get("distribution_ready")) != edge_ready:
        fail("android_distribution_truth_mismatch")
    if bool(android.get("auto_update_eligible")) != edge_ready:
        fail("android_auto_update_truth_mismatch")

    nexus_artifact = nexus.get("artifact", {}) or {}
    nexus_ready = bool(nexus_artifact.get("url") and is_sha(nexus_artifact.get("sha256") or ""))
    if nexus_ready:
        actual_nexus_sha = hashlib.sha256(NEXUS.read_bytes()).hexdigest()
        if nexus.get("version") != str(nexus_manifest.get("version")):
            fail("nexus_version_drift")
        if nexus_artifact.get("sha256") != actual_nexus_sha:
            fail("nexus_manifest_sha_drift")
        if version_tuple(str(srv.get("version"))) < version_tuple(str(nexus_manifest.get("minimum_server_version"))):
            fail("nexus_server_compatibility_drift")
        files = nexus_manifest.get("files") or []
        if not files:
            fail("nexus_bundle_empty")
        for item in files:
            rel = str(item.get("path") or "")
            p = ROOT / rel
            if not p.is_file():
                fail("nexus_bundle_file_missing:" + rel)
            if hashlib.sha256(p.read_bytes()).hexdigest() != str(item.get("sha256") or ""):
                fail("nexus_bundle_file_sha_drift:" + rel)
    if bool(nexus.get("distribution_ready")) != nexus_ready:
        fail("nexus_distribution_truth_mismatch")

    actual_telegram_sha = hashlib.sha256(telegram_source).hexdigest()
    if telegram.get("version") != str(telegram_manifest.get("version")):
        fail("telegram_version_drift")
    if actual_telegram_sha != str(telegram_manifest.get("sha256") or ""):
        fail("telegram_source_sha_drift")
    if telegram_manifest.get("auto_update") is not True:
        fail("telegram_auto_update_contract")
    if not str(telegram_manifest.get("minimum_selftest") or ""):
        fail("telegram_selftest_contract")
    if version_tuple(str(srv.get("version"))) < version_tuple(str(telegram_manifest.get("minimum_server_version"))):
        fail("telegram_server_compatibility_drift")

    all_ready = bool(pc.get("distribution_ready") and android.get("distribution_ready") and nexus.get("distribution_ready"))
    overall = str(cur.get("overall_state") or "")
    if all_ready and overall == "CI_QUALIFIED_DISTRIBUTION_INCOMPLETE":
        fail("overall_state_underclaims_ready")
    if not all_ready and overall != "CI_QUALIFIED_DISTRIBUTION_INCOMPLETE":
        fail("overall_state_overclaims_ready")

    print(json.dumps({
        "schema": cur["schema"],
        "overall_state": overall,
        "server": {"version": pc["version"], "distribution_ready": pc["distribution_ready"]},
        "android": {"version": android["version"], "distribution_ready": android["distribution_ready"]},
        "nexus": {"version": nexus["version"], "distribution_ready": nexus["distribution_ready"]},
        "telegram": {"version": telegram["version"], "sha256_verified": True},
        "zero_usd": True,
    }, sort_keys=True))
    print("BCP_CURRENT_RELEASE_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
