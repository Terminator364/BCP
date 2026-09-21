from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDatabase.java").read_text(encoding="utf-8")
DAO = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeDao.java").read_text(encoding="utf-8")
ENTITY = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/storage/EdgeMissionStepEntity.java").read_text(encoding="utf-8")
CLIENT = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/BcpClient.java").read_text(encoding="utf-8")
SERVICE = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayService.java").read_text(encoding="utf-8")
POLICY = (ROOT / "android-b-edge/src/main/java/com/blessing/bcpedge/EdgeRelayPolicy.java").read_text(encoding="utf-8")


def ck(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"{name}=PASS")


ck("mission-entity", 'tableName = "edge_mission_steps"' in ENTITY)
ck("mission-db-version", "version = 5" in DB)
ck("mission-migration", "Migration(3, 4)" in DB and "MIGRATION_3_4" in DB)
ck("mission-migration-chain", ".addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)" in DB)
ck("mission-dao", "putMissionStep" in DAO and "resumableMissionSteps" in DAO and "updateMissionStepState" in DAO)
for state in [
    "NOT_DISPATCHED", "DISPATCH_ATTEMPTED", "PROVIDER_ACKED", "STREAM_OBSERVED",
    "RESULT_OBSERVED", "RESULT_COMMITTED", "PLATFORM_HOLD", "INTERRUPTED",
    "OUTCOME_UNKNOWN", "RECONCILING", "SUPERSEDED",
]:
    ck("provider-state-" + state.lower(), state in CLIENT)
for effect in ["NONE", "READ_ONLY", "IDEMPOTENT", "MUTATING"]:
    ck("effect-" + effect.lower(), effect in CLIENT)
ck("mission-wall-monotonic-time", "created_at_wall_ms" in CLIENT and "SystemClock.elapsedRealtime()" in CLIENT)
ck("mission-api-get", '"/v1/node/mission-steps"' in SERVICE and "localMissionSteps" in SERVICE)
ck("mission-api-post", "upsertMissionStep" in SERVICE and "updateMissionStepState" in SERVICE)
ck("mission-api-auth", '"/v1/node/mission-steps"' in POLICY and not ('"/v1/node/mission-steps"' in POLICY.split("isPublicApiPath")[1].split("isAllowedApiPath")[0]))
ck("mission-capability", '"mission_step_envelope_v1", true' in SERVICE)
ck("provider-degraded-capability", '"provider_degraded_resume", true' in SERVICE)
ck("mission-authority", "DURABLE_BCP_STATE_NOT_CHAT_UI" in SERVICE)
print("BCP_BEDGE_MISSION_STEP_CONTRACT=PASS")
