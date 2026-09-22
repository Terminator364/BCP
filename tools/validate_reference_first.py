from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / ".project-memory" / "REFERENCE_FIRST_POLICY.json"
REGISTRY = ROOT / ".project-memory" / "EXTERNAL_REFERENCE_REGISTRY.json"
MATRIX = ROOT / ".project-memory" / "BCP_R89_SOURCE_ADOPTION_MATRIX.json"
STATE = ROOT / "project_state.json"
SPEC = ROOT / "docs" / "BCP_CANONICAL_SPEC_ABC.md"
BENCH = ROOT / "docs" / "BCP_R89_ANTI_REINVENTION_BENCHMARK.md"


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(obj, dict), path
    return obj


def main() -> int:
    policy = load(POLICY)
    registry = load(REGISTRY)
    matrix = load(MATRIX)
    state = load(STATE)
    spec = SPEC.read_text(encoding="utf-8")
    bench = BENCH.read_text(encoding="utf-8")

    assert policy["schema"] == "bcp.reference_first_policy/1"
    assert policy["status"].startswith("CANONICAL_CANDIDATE")
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
    assert policy["transport_rules"]["new_transport_requires_measured_gap"] is True
    assert policy["reliability_rules"]["unknown_outcome_is_success"] is False
    assert policy["reliability_rules"]["unknown_outcome_is_failure"] is False
    assert policy["product_release_rules"]["next_user_install_deferred_until_reference_reconciliation"] is True
    assert policy["benchmark_doc"] == "docs/BCP_R89_ANTI_REINVENTION_BENCHMARK.md"

    assert registry["schema"] == "bcp.external_reference_registry/1"
    ids = [x["id"] for x in registry["sources"]]
    assert len(ids) == len(set(ids))
    for required in {
        "REF-ANDROID-SETTINGS","REF-HOMEASSISTANT-ONBOARDING","REF-KDECONNECT-PAIRING",
        "REF-SYNCTHING-IDENTITY","REF-LOCALSEND-PROTOCOL","REF-TAILSCALE-CONNECTIVITY",
        "REF-RUSTDESK-CONNECTIVITY","REF-TEMPORAL-DURABILITY","REF-STRIPE-IDEMPOTENCY",
        "REF-AWS-OUTBOX","REF-NODERED-FLOWLIB",
    }:
        assert required in ids
    localsend = next(x for x in registry["sources"] if x["id"] == "REF-LOCALSEND-PROTOCOL")
    assert localsend.get("license") == "APACHE-2.0"
    rustdesk = next(x for x in registry["sources"] if x["id"] == "REF-RUSTDESK-CONNECTIVITY")
    assert rustdesk.get("license") == "AGPL-3.0"
    assert registry["videos_and_tutorials"]["architecture_authority"] is False

    assert matrix["schema"] == "bcp.r89_source_adoption_matrix/1"
    mids = {x["id"] for x in matrix["sources"]}
    for required in {"HOME_ASSISTANT_ANDROID","SYNCTHING_AND_ANDROID_FORK","TAILSCALE",
                     "KDE_CONNECT","LOCALSEND","TEMPORAL_UI","ANDROID_OFFICIAL_UX",
                     "ADYEN_PAYMENT_LIFECYCLE","RUSTDESK"}:
        assert required in mids

    r89 = state["evidence"]["r89_anti_reinvention"]
    assert r89["product_bytes_changed"] is False
    assert r89["decision"] == "DEFER_CURRENT_2_2_HUMAN_INSTALL_UNTIL_ONE_COHERENT_UI_CONVERGENCE_CANDIDATE"
    assert state["product_priorities"]["P0_source_benchmark_before_new_ui_design"] is True
    assert state["product_priorities"]["P0_one_coherent_ui_convergence_before_next_human_install"] is True

    assert "Anti-Reinvention Benchmark" in bench
    assert "PARAMÈTRES / DIAGNOSTIC" in bench
    assert "Home Assistant" in bench and "Temporal" in bench and "Adyen" in bench
    assert "reference-first" in spec.lower() or "anti-réinvention" in spec.lower()

    print("BCP_REFERENCE_FIRST_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
