from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def need(text: str, *markers: str) -> None:
    for marker in markers:
        assert marker in text, marker

def main() -> int:
    entity = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeEventEntity.java")
    db = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDatabase.java")
    dao = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDao.java")
    client = read("android-b-edge/src/main/java/com/blessing/bcpedge/BcpClient.java")
    policy = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayPolicy.java")
    service = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayService.java")

    need(entity,
         'tableName = "edge_events"',
         '"projectId", "idempotencyKey"',
         "payloadSha256",
         "truthStatus",
         "occurredAt",
         "ingestedAt")
    need(db,
         "version = 3",
         "MIGRATION_2_3",
         "CREATE TABLE IF NOT EXISTS edge_events",
         "index_edge_events_projectId_idempotencyKey")
    need(dao, "insertEvent", "recentEvents", "eventCount")
    need(client,
         "appendLocalEvent",
         "localEventTail",
         "APPEND_ONLY_LOCAL_CHRONICLE",
         '"OBSERVED","VERIFIED","REPORTED","INFERRED","MODEL_GENERATED","UNKNOWN"',
         "sha256Hex")
    need(policy,
         '"/v1/node/events"',
         '"GET".equalsIgnoreCase(method)',
         '"POST".equalsIgnoreCase(method)')
    need(service,
         '"universal_event_ledger", true',
         '"APPEND_ONLY_LOCAL_CHRONICLE"',
         '"/v1/node/events".equals(path)',
         "appendLocalEvent",
         "localEventTail")

    assert "arbitrary_shell" in service and '"arbitrary_shell", false' in service
    assert "api.telegram.org" in policy
    print("BCP_BEDGE_UNIVERSAL_CHRONICLE_CONTRACT=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
