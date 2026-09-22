from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / ".project-memory" / "REFERENCE_FIRST_POLICY.json"
REGISTRY = ROOT / ".project-memory" / "EXTERNAL_REFERENCE_REGISTRY.json"
STATE = ROOT / "project_state.json"
SPEC = ROOT / "docs" / "BCP_CANONICAL_SPEC_ABC.md"
BENCH = ROOT / "docs" / "BCP_REFERENCE_FIRST_BENCHMARK_R89.md"


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(obj, dict), path
    return obj


def main() -> int:
    policy = load(POLICY)
    registry = load(REGISTRY)
    state = load(STATE)
    spec = SPEC.read_text(encoding="utf-8")
    bench = BENCH.read_text(encoding="utf-8")

    assert policy["schema"] == "bcp.reference_first_policy/1"
    assert policy["status"].startswith("CANONICAL")
    assert policy["pipeline"][:3] == [
        "LOAD_CURRENT_A_PLUS_B_PLUS_C",
        "IDENTIFY_USER_JOB_AND_FIELD_CONSTRAINTS",
        "SEARCH_MATURE_EXTERNAL_REFERENCES",
    ]
    assert "CLASSIFY_REUSE_ADAPT_BUILD_ONLY_IF_GAP" in policy["pipeline"]
    assert "VERIFY_LICENSE_AND_PROVENANCE_BEFORE_CODE_REUSE" in policy["pipeline"]
    assert policy["minimum_reference_rule"]["when_mature_pattern_plausibly_exists"] >= 2
    assert policy["license_and_provenance"]["noncommercial_is_not_license_exemption"] is True
    assert policy["license_and_provenance"]["copy_external_code_before_license_review"] is False
    assert policy["ui_rules"]["frequent_actions_in_settings_forbidden"] is True
    assert policy["ui_rules"]["exactly_one_primary_human_cta_when_blocked"] is True
    assert policy["ui_rules"]["task_completion_tests_over_string_presence"] is True
    assert policy["ui_rules"]["compact_320x640_primary_action_without_scroll"] is True
    assert policy["transport_rules"]["new_transport_requires_measured_gap"] is True
    assert policy["reliability_rules"]["unknown_outcome_is_success"] is False
    assert policy["reliability_rules"]["unknown_outcome_is_failure"] is False
    assert policy["product_release_rules"]["next_user_install_deferred_until_reference_reconciliation"] is True

    assert registry["schema"] == "bcp.external_reference_registry/1"
    refs = registry["sources"]
    ids = [x["id"] for x in refs]
    assert len(refs) >= 15
    assert len(ids) == len(set(ids))
    required = {
        "REF-ANDROID-SETTINGS",
        "REF-HOMEASSISTANT-ONBOARDING",
        "REF-KDECONNECT-PAIRING",
        "REF-SYNCTHING-IDENTITY",
        "REF-LOCALSEND-PROTOCOL",
        "REF-TAILSCALE-CONNECTIVITY",
        "REF-OBTAINIUM-UPDATER",
        "REF-TEMPORAL-DURABILITY",
        "REF-STRIPE-IDEMPOTENCY",
        "REF-AWS-OUTBOX",
        "REF-NODERED-FLOWLIB",
        "REF-OPENHANDS-RUNTIME",
    }
    assert required.issubset(set(ids))
    obtainium = next(x for x in refs if x["id"] == "REF-OBTAINIUM-UPDATER")
    assert "GPL_3_0" in obtainium["code_reuse"]
    assert registry["videos_and_tutorials"]["architecture_authority"] is False
    assert registry["videos_and_tutorials"]["security_authority"] is False

    r89 = state["r89_reference_first"]
    assert r89["user_install_authorized"] is False
    assert r89["baseline_role"] == "TECHNICAL_BASELINE_NOT_TARGET_UX"
    assert r89["code_reuse_rule"] == "NO_EXTERNAL_CODE_COPY_BEFORE_LICENSE_PROVENANCE_REVIEW"
    assert state["product_priorities"]["P0_reference_first_before_new_implementation"] is True

    assert "R89 — Reference-first / anti-réinvention" in spec
    assert "REUSE/ADAPT/BUILD_ONLY_IF_GAP" in spec
    assert "baseline technique" in spec
    assert "Reference-first benchmark" in bench
    assert "PARAMÈTRES / DIAGNOSTIC" in bench
    assert "BUILD_ONLY_IF_GAP" in bench

    print("BCP_REFERENCE_FIRST_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
