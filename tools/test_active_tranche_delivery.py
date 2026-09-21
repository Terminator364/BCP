from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / ".project-memory" / "ACTIVE_TRANCHE.json"
DELIVERY = ROOT / ".project-memory" / "DELIVERY_REDUNDANCY_POLICY.json"
COMM = ROOT / ".project-memory" / "COMMUNICATION_SURVIVAL_POLICY.json"


def main() -> int:
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    delivery = json.loads(DELIVERY.read_text(encoding="utf-8"))
    comm = json.loads(COMM.read_text(encoding="utf-8"))

    assert active["schema"] == "bcp.active_tranche/2"
    assert active["project"] == "API/BCP"
    assert active["target_minutes"] == 30
    assert active["start_email"]["acknowledged"] is True
    assert bool(active["start_email"]["message_id"])
    assert active["closeout"]["user_message_required"] is False
    assert active["closeout"]["scheduler_completion_is_not_delivery_proof"] is True
    assert active["closeout"]["gmail_sent_readback_required"] is True
    assert active["closeout"]["foreground_closeout_required"] is True
    assert active["closeout"]["minimal_backup_email_precomposed"] is True

    if active["status"] == "CLOSED":
        end = active["end_email"]
        assert end["acknowledged"] is True
        assert bool(end["message_id"])
        assert bool(end["checkpoint_id"])
    else:
        assert active["status"] in {"WORKING", "CLOSING", "END_SEND_PENDING", "END_ACK_PENDING"}

    email = delivery["channels"]["email"]
    assert email["foreground_end_send_primary"] is True
    assert email["scheduler_completion_is_not_delivery_proof"] is True
    assert email["end_mail_provider_ack_required"] is True
    assert email["end_mail_readback_required"] is True
    assert delivery["cadence"]["normal_closeout_offset_minutes"] == 27
    assert delivery["cadence"]["hard_close_guard_offset_minutes"] == 29
    assert delivery["cadence"]["absolute_end_deadline_minutes"] == 30

    assert comm["schema"] == "bcp.communication_survival_policy/3"
    assert comm["anti_false_success"]["scheduler_completed_is_not_delivery"] is True
    assert comm["anti_false_success"]["user_relaunch_must_never_be_delivery_trigger"] is True
    assert comm["channels"]["gmail"]["end_delivery_proof"]["proof"] == "SENT_SEARCH_MATCH_PLUS_PROVIDER_MESSAGE_ID"

    print("BCP_ACTIVE_TRANCHE_DELIVERY_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
