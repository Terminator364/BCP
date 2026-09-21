from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeLocalTaskEngine.java"
CLIENT = ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/BcpClient.java"
ORCH = ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeOrchestrator.java"
SERVER = ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayService.java"


def need(text: str, *markers: str) -> None:
    missing = [m for m in markers if m not in text]
    assert not missing, missing


def main() -> int:
    engine = ENGINE.read_text(encoding="utf-8")
    client = CLIENT.read_text(encoding="utf-8")
    orch = ORCH.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")

    need(
        engine,
        "LOCAL_CONTEXT_SNAPSHOT",
        "LOCAL_HEALTH_SNAPSHOT",
        "LOCAL_QUEUE_SUMMARY",
        "LOCAL_MEMORY_COMPACT",
        "B_EDGE_LOCAL_TASK_ENGINE",
        "EdgeNetworkState.snapshot",
        "EdgeResourceGovernor.snapshot",
    )
    assert "Runtime.getRuntime" not in engine
    assert "ProcessBuilder" not in engine
    assert "/bin/sh" not in engine
    assert "exec(" not in engine

    need(
        client,
        "runLocalReadyJobs",
        "EdgeLocalTaskEngine.supports",
        "EdgeLocalTaskEngine.execute",
        'local.put("executed_locally"',
        'out.put("local_execution", runLocalReadyJobs(8))',
        "EDGE_LOCAL_TASK_COMMITTED",
        "communicationHistory",
    )
    need(
        orch,
        "acknowledgeLocalJob",
        "local-receipt-",
        '"COMMITTED"',
        "B_EDGE_LOCAL_TASK_ENGINE",
    )
    need(
        server,
        '"local_allowlisted_executor", true',
        '"LOCAL_CONTEXT_SNAPSHOT"',
        '"LOCAL_HEALTH_SNAPSHOT"',
        '"LOCAL_QUEUE_SUMMARY"',
        '"LOCAL_MEMORY_COMPACT"',
        '"LOCAL_COMMUNICATION_RECORD"',
        '"local_executor", "ALLOWLISTED_ACTIVE"',
        '"durable_communication_journal", true',
        '"/v1/node/communications"',
    )
    print("BCP_BEDGE_LOCAL_EXECUTOR_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
