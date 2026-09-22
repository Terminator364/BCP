from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / ".project-memory" / "ACTIVE_TRANCHE.json"
DELIVERY = ROOT / ".project-memory" / "DELIVERY_REDUNDANCY_POLICY.json"
COMM = ROOT / ".project-memory" / "COMMUNICATION_SURVIVAL_POLICY.json"
PROTOCOL = ROOT / ".project-memory" / "COMMUNICATION_PROTOCOL.json"
STATE_MACHINE = ROOT / ".project-memory" / "COMMUNICATION_STATE_MACHINE.json"
TAKEOVER = ROOT / ".project-memory" / "NEW_CONVERSATION_TAKEOVER.json"
LEDGER = ROOT / ".project-memory" / "COMMUNICATION_DELIVERY_LEDGER.jsonl"


def main() -> int:
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    delivery = json.loads(DELIVERY.read_text(encoding="utf-8"))
    comm = json.loads(COMM.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    state_machine = json.loads(STATE_MACHINE.read_text(encoding="utf-8"))
    takeover = json.loads(TAKEOVER.read_text(encoding="utf-8"))
    ledger_rows = [
        json.loads(line)
        for line in LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert active["schema"] == "bcp.active_tranche/5"
    assert active["project"] == "API/BCP"
    assert active["cadence_minutes"] == 25
    assert active["useful_work_minutes"] == 23
    assert active["normal_close_reserve_minutes"] == 2
    assert active["delivery_key"].startswith("BCP25-")
    assert active["gmail_start_message_id"]
    assert active["delivery_state"] in {
        "START_ACKNOWLEDGED", "WORKING", "CLOSE_INTENT_PERSISTED",
        "END_SEND_PENDING", "END_ACKNOWLEDGED", "CLOSED"
    }
    assert active["close_owner"] == "PRIMARY_ASSISTANT"
    assert active["final_app_reply_gate"] in {"END_ACK_REQUIRED", "OPEN_AFTER_END_ACK"}
    guard = active["communication_guard"]
    assert guard["scheduler_completion_is_not_delivery_proof"] is True
    assert guard["user_message_is_not_closeout_trigger"] is True
    assert guard["search_before_send"] is True
    assert guard["delivery_key_required"] is True

    if active["delivery_state"] in {"END_ACKNOWLEDGED", "CLOSED"} or active["status"] == "CLOSED":
        assert active["end_mail_verified"] is True
        assert active["gmail_end_message_id"]
    else:
        assert active["end_mail_verified"] is False

    email = delivery["channels"]["email"]
    assert email["foreground_end_send_primary"] is True
    assert email["scheduler_completion_is_not_delivery_proof"] is True
    assert email["end_mail_provider_ack_required"] is True
    assert email["end_mail_readback_required"] is True
    assert email["delivery_key_required"] is True
    assert delivery["cadence"]["normal_closeout_offset_minutes"] == 23
    assert delivery["cadence"]["scheduled_close_guards_required"] is False
    assert delivery["close_ownership"]["normal_owner"] == "PRIMARY_ASSISTANT"

    assert comm["schema"] == "bcp.communication_survival_policy/5"
    assert comm["anti_false_success"]["scheduler_completed_is_not_delivery"] is True
    assert comm["anti_false_success"]["user_relaunch_must_never_be_delivery_trigger"] is True
    assert comm["channels"]["gmail"]["end_delivery_proof"]["proof"] == "SENT_SEARCH_MATCH_PLUS_PROVIDER_MESSAGE_ID"

    assert protocol["schema"] == "bcp.communication_protocol/3"
    assert protocol["normal_close_owner"] == "PRIMARY_ASSISTANT"
    assert protocol["primary_work_budget_minutes"] == 23
    assert protocol["normal_close_reserve_minutes"] == 2
    assert protocol["scheduled_backup_required"] is False
    assert protocol["normal_work_contract"]["automation_is_never_normal_owner"] is True
    assert active["communication_guard"]["foreground_turn_owns_normal_close"] is True
    assert active["communication_guard"]["automation_only_after_platform_interruption"] is True

    assert state_machine["schema"] == "bcp.communication_state_machine/3"
    assert "END_SEND_PENDING->END_ACKNOWLEDGED" in state_machine["normal_path"]
    assert takeover["trigger_code"] == "BCPGO BCP"
    assert takeover["current_active_tranche"] == active["tranche_id"]
    assert takeover["current_delivery_key"] == active["delivery_key"]
    assert takeover["current_active_tranche_status"] == active["status"]
    contract = takeover["communication_contract"]
    assert contract["cadence_minutes"] == 25
    assert contract["useful_work_target_minutes"] == 23
    assert contract["close_reserve_minutes"] == 2
    assert contract["normal_close_owner"] == "PRIMARY_ASSISTANT"
    assert contract["automation_normal_close_forbidden"] is True
    assert takeover["product_scope"]["formula"] == "A+B+C"
    assert takeover["product_scope"]["phone_role"] == "PRIMARY_DEDICATED_EDGE_API_SERVER_COORDINATOR"

    starts = [
        row for row in ledger_rows
        if row.get("delivery_key") == active["delivery_key"]
        and row.get("event") == "START_ACKNOWLEDGED"
    ]
    assert len(starts) == 1
    assert (starts[0].get("gmail_start_message_id") or starts[0].get("start_message_id")) == active["gmail_start_message_id"]

    r73_ends = [
        row for row in ledger_rows
        if row.get("delivery_key") == "BCP30-20260921-1818-R73"
        and row.get("event") == "END_ACKNOWLEDGED"
    ]
    assert len(r73_ends) == 1
    assert r73_ends[0]["gmail_end_message_id"] == "1a0c520e8cc2673f"

    print("BCP_ACTIVE_TRANCHE_DELIVERY_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
