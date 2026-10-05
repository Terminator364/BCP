from __future__ import annotations

"""BCP Execution Fabric resource admission policy.

This is not a second Resource Governor. It consumes the already-established
GREEN/AMBER/RED/CRITICAL mode and decides whether a typed worker may start.
"""

from dataclasses import dataclass


RESOURCE_ORDER = {
    "R0_TINY": 0,
    "R1_LIGHT": 1,
    "R2_MEDIUM": 2,
    "R3_HEAVY": 3,
    "R4_LOCAL_AI": 4,
}

PRIORITIES = {
    "CRITICAL_INTEGRITY_RECOVERY",
    "USER_INTERACTIVE",
    "NORMAL_PROJECT",
    "BACKGROUND_IMPROVEMENT",
}


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    state: str
    reason: str
    mode: str
    resource_class: str
    priority: str


def decide_admission(
    *,
    mode: str,
    resource_class: str,
    priority: str,
    local_ai_enabled: bool = False,
) -> AdmissionDecision:
    m = str(mode).upper()
    rc = str(resource_class).upper()
    pr = str(priority).upper()

    if m not in {"GREEN", "AMBER", "RED", "CRITICAL"}:
        raise ValueError(f"unknown resource mode: {mode}")
    if rc not in RESOURCE_ORDER:
        raise ValueError(f"unknown resource class: {resource_class}")
    if pr not in PRIORITIES:
        raise ValueError(f"unknown priority: {priority}")

    if rc == "R4_LOCAL_AI" and not local_ai_enabled:
        return AdmissionDecision(False, "WAITING_POLICY", "LOCAL_AI_NOT_QUALIFIED", m, rc, pr)

    if m == "GREEN":
        if rc == "R4_LOCAL_AI":
            return AdmissionDecision(
                local_ai_enabled,
                "ADMITTED" if local_ai_enabled else "WAITING_POLICY",
                "GREEN_LOCAL_AI_QUALIFIED" if local_ai_enabled else "LOCAL_AI_NOT_QUALIFIED",
                m, rc, pr,
            )
        return AdmissionDecision(True, "ADMITTED", "GREEN_CAPACITY", m, rc, pr)

    if m == "AMBER":
        if pr == "BACKGROUND_IMPROVEMENT":
            if RESOURCE_ORDER[rc] <= RESOURCE_ORDER["R0_TINY"]:
                return AdmissionDecision(True, "ADMITTED", "AMBER_TINY_BACKGROUND", m, rc, pr)
            return AdmissionDecision(False, "WAITING_RESOURCE", "AMBER_BACKGROUND_DEFERRED", m, rc, pr)
        if RESOURCE_ORDER[rc] <= RESOURCE_ORDER["R1_LIGHT"]:
            return AdmissionDecision(True, "ADMITTED", "AMBER_LIGHT_ONLY", m, rc, pr)
        return AdmissionDecision(False, "WAITING_RESOURCE", "AMBER_MEDIUM_OR_HEAVY_DEFERRED", m, rc, pr)

    if m == "RED":
        if pr in {"CRITICAL_INTEGRITY_RECOVERY", "USER_INTERACTIVE"} and rc == "R0_TINY":
            return AdmissionDecision(True, "ADMITTED", "RED_TINY_FOREGROUND_ONLY", m, rc, pr)
        return AdmissionDecision(False, "WAITING_RESOURCE", "RED_DEFER", m, rc, pr)

    # CRITICAL: preserve the machine. Only a tiny integrity recovery action may run.
    if pr == "CRITICAL_INTEGRITY_RECOVERY" and rc == "R0_TINY":
        return AdmissionDecision(True, "ADMITTED", "CRITICAL_TINY_RECOVERY_ONLY", m, rc, pr)
    return AdmissionDecision(False, "WAITING_RESOURCE", "CRITICAL_PRESERVE_MACHINE", m, rc, pr)


__all__ = ["AdmissionDecision", "decide_admission", "RESOURCE_ORDER", "PRIORITIES"]
