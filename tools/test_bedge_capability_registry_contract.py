from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDatabase.java").read_text(encoding="utf-8")
DAO = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDao.java").read_text(encoding="utf-8")
ENTITY = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeCapabilityEntity.java").read_text(encoding="utf-8")
CLIENT = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/BcpClient.java").read_text(encoding="utf-8")
SERVICE = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayService.java").read_text(encoding="utf-8")
POLICY = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayPolicy.java").read_text(encoding="utf-8")

def ck(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"{name}=PASS")

ck("entity", 'tableName = "edge_capabilities"' in ENTITY)
ck("db-version", "version = 5" in DB)
ck("migration-4-5", "Migration(4, 5)" in DB and "MIGRATION_4_5" in DB)
ck("migration-chain", ".addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)" in DB)
for marker in [
    "putCapability", "capabilityById", "activeCapabilities",
    "activeCapabilitiesByType", "deleteExpiredCapabilities"
]:
    ck("dao-" + marker.lower(), marker in DAO)
for marker in [
    "observeLocalCapability", "localCapabilityRegistry", "refreshBuiltinCapabilities",
    "B_EDGE_LOCAL_CAPABILITY_REGISTRY", "CAPABILITY_OBSERVED",
    "CAPABILITY_DURABLE_CHANGED", "CAPABILITY_REFRESHED"
]:
    ck("client-" + marker.lower(), marker in CLIENT)
for state in ["AVAILABLE", "DEGRADED", "UNAVAILABLE", "WAITING_AUTH", "UNKNOWN"]:
    ck("state-" + state.lower(), state in CLIENT)
for evidence in ["MACHINE_READBACK", "LOCAL_PROBE", "PROVIDER_ACK", "USER_CONFIRMED", "CONFIGURED"]:
    ck("evidence-" + evidence.lower(), evidence in CLIENT)
ck("api-get", '"/v1/node/capability-registry".equals(path)' in SERVICE and "localCapabilityRegistry" in SERVICE)
ck("api-post", '"/v1/node/capability-registry".equals(path)' in SERVICE and "observeLocalCapability" in SERVICE)
public_block = POLICY.split("isPublicApiPath", 1)[1].split("isAllowedApiPath", 1)[0]
ck("api-private", '"/v1/node/capability-registry"' not in public_block)
ck("api-allowed", '"/v1/node/capability-registry"' in POLICY)
ck("self-refresh", "refreshBuiltinCapabilities" in SERVICE)
ck("no-arbitrary-shell", '"arbitrary_shell", false' in SERVICE and "ProcessBuilder" not in CLIENT)
print("BCP_BEDGE_CAPABILITY_REGISTRY_CONTRACT=PASS")
