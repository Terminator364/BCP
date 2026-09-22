from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def ck(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"{name}=PASS")

DB = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDatabase.java")
DAO = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDao.java")
CAP = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeCapabilityEntity.java")
CLAIM = read("android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeMemoryClaimEntity.java")
ORCH = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgeOrchestrator.java")
CLIENT = read("android-b-edge/src/main/java/com/blessing/bcpedge/BcpClient.java")
SERVICE = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayService.java")
POLICY = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayPolicy.java")
EDGE_POLICY = read("android-b-edge/src/main/java/com/blessing/bcpedge/EdgePolicy.java")

ck("room-v5", "version = 5" in DB and "Migration(4, 5)" in DB and "MIGRATION_4_5" in DB)
ck("room-v5-chain", ".addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)" in DB)
ck("capability-table", 'tableName = "edge_capabilities"' in CAP and "capabilityId" in CAP and "evidenceClass" in CAP)
ck("claim-table", 'tableName = "edge_memory_claims"' in CLAIM and "supersedesClaimId" in CLAIM and "idempotencyKey" in CLAIM)
ck("claim-idem-index", '"projectId", "idempotencyKey"' in CLAIM and "unique = true" in CLAIM)
ck("dao-capabilities", all(x in DAO for x in ["putCapability", "capabilities(", "capability("]))
ck("dao-claims", all(x in DAO for x in ["insertMemoryClaim", "memoryClaimByIdempotency", "memoryClaims", "memoryClaimById", "latestAdmittedMemoryClaim", "setMemoryClaimState"]))
ck("admission-precedence", "EdgePolicy.canReplaceMemory" in ORCH and "PRECEDENCE_REJECTED" in ORCH)
ck("supersession", "SUPERSEDED_BY:" in ORCH and "supersedesClaimId" in ORCH)
ck("same-key-supersession", "invalid_supersedes_claim" in ORCH and "latestAdmittedMemoryClaim" in ORCH)
ck("claim-idempotency", "memoryClaimByIdempotency" in ORCH and "ALREADY_RECORDED" in ORCH)
ck("internal-memory-routes-through-ledger", "JSONObject receipt = admitMemoryClaim(" in ORCH and '"B_EDGE_INTERNAL"' in ORCH)
ck("capability-registry", "putCapability" in ORCH and "capabilityRegistry" in ORCH)
ck("builtin-capability-refresh", all(x in CLIENT for x in [
    "LOCAL_API_SERVER", "DURABLE_STATE_CORE", "LOCAL_EXECUTOR", "NETWORK_UPLINK",
    "NEARBY_DISCOVERY", "RESOURCE_GOVERNOR", "PC_HEAVY_WORKER_LINK", "TELEGRAM_CONNECT_RELAY"
]))
ck("memory-claim-client", "admitMemoryClaim" in CLIENT and "localMemoryClaims" in CLIENT)
ck("context-includes-governance", '"capabilities"' in CLIENT and '"memory_claims"' in CLIENT)
ck("api-capability-get-post", '"/v1/node/capability-registry"' in SERVICE and "registerCapability" in SERVICE)
ck("api-memory-get-post", '"/v1/node/memory-claims"' in SERVICE and "admitMemoryClaim" in SERVICE)
public_block = POLICY.split("isPublicApiPath", 1)[1].split("isAllowedApiPath", 1)[0]
ck("governance-apis-private", '"/v1/node/capability-registry"' not in public_block and '"/v1/node/memory-claims"' not in public_block)
ck("policy-evidence-ranking", "evidenceRank" in EDGE_POLICY and "canReplaceMemory" in EDGE_POLICY)
ck("no-arbitrary-shell", '"arbitrary_shell", false' in SERVICE and "ProcessBuilder" not in ORCH)
print("BCP_BEDGE_MEMORY_CAPABILITY_CONTRACT=PASS")
