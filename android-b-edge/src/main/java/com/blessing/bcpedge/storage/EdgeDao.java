package com.blessing.bcpedge.storage;

import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import androidx.room.Transaction;

import java.util.List;

@Dao
public interface EdgeDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertProject(EdgeProjectEntity project);

    @Query("UPDATE edge_projects SET status = :status, headRevision = :headRevision, updatedAt = :updatedAt WHERE projectId = :projectId")
    int updateProjectHeadPreservingEpoch(String projectId, String status, long headRevision, long updatedAt);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertJob(EdgeJobEntity job);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putMemory(EdgeMemoryEntity memory);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putCapability(EdgeCapabilityEntity capability);

    @Query("SELECT * FROM edge_capabilities WHERE projectId = :projectId AND (expiresAt IS NULL OR expiresAt > :now) ORDER BY updatedAt DESC LIMIT :limit")
    List<EdgeCapabilityEntity> capabilities(String projectId, long now, int limit);

    @Query("SELECT * FROM edge_capabilities WHERE projectId = :projectId AND capabilityId = :capabilityId LIMIT 1")
    EdgeCapabilityEntity capability(String projectId, String capabilityId);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertMemoryClaim(EdgeMemoryClaimEntity claim);

    @Query("SELECT * FROM edge_memory_claims WHERE projectId = :projectId AND idempotencyKey = :idempotencyKey LIMIT 1")
    EdgeMemoryClaimEntity memoryClaimByIdempotency(String projectId, String idempotencyKey);

    @Query("SELECT * FROM edge_memory_claims WHERE projectId = :projectId ORDER BY admittedAt DESC LIMIT :limit")
    List<EdgeMemoryClaimEntity> memoryClaims(String projectId, int limit);

    @Query("SELECT * FROM edge_memory_claims WHERE claimId = :claimId LIMIT 1")
    EdgeMemoryClaimEntity memoryClaimById(String claimId);

    @Query("SELECT * FROM edge_memory_claims WHERE projectId = :projectId AND scope = :scope AND memoryKey = :memoryKey AND state = 'ADMITTED' ORDER BY admittedAt DESC LIMIT 1")
    EdgeMemoryClaimEntity latestAdmittedMemoryClaim(String projectId, String scope, String memoryKey);

    @Query("UPDATE edge_memory_claims SET state = :state, reason = :reason, updatedAt = :updatedAt WHERE claimId = :claimId")
    int setMemoryClaimState(String claimId, String state, String reason, long updatedAt);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertReceipt(EdgeReceiptEntity receipt);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertDependency(EdgeDependencyEntity dependency);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertEvent(EdgeEventEntity event);

    @Query("SELECT * FROM edge_events WHERE projectId = :projectId ORDER BY occurredAt DESC LIMIT :limit")
    List<EdgeEventEntity> recentEvents(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_events WHERE projectId = :projectId")
    int eventCount(String projectId);


    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putMissionStep(EdgeMissionStepEntity step);

    @Query("SELECT * FROM edge_mission_steps WHERE projectId = :projectId ORDER BY updatedAtWallMs DESC LIMIT :limit")
    List<EdgeMissionStepEntity> recentMissionSteps(String projectId, int limit);

    @Query("SELECT * FROM edge_mission_steps WHERE projectId = :projectId AND providerState NOT IN ('RESULT_COMMITTED','SUPERSEDED') ORDER BY updatedAtWallMs DESC LIMIT :limit")
    List<EdgeMissionStepEntity> resumableMissionSteps(String projectId, int limit);

    @Query("UPDATE edge_mission_steps SET providerState = :providerState, nextSafeAction = :nextSafeAction, continuationFrontier = :continuationFrontier, updatedAtWallMs = :updatedAtWallMs WHERE stepId = :stepId")
    int updateMissionStepState(String stepId, String providerState, String nextSafeAction,
                               String continuationFrontier, long updatedAtWallMs);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putSentinel(EdgeSentinelEntity sentinel);

    @Query("SELECT * FROM edge_sentinel WHERE projectId = :projectId LIMIT 1")
    EdgeSentinelEntity sentinel(String projectId);

    @Query("SELECT * FROM edge_projects ORDER BY updatedAt DESC")
    List<EdgeProjectEntity> projects();

    @Query("SELECT * FROM edge_receipts WHERE projectId = :projectId ORDER BY createdAt DESC LIMIT :limit")
    List<EdgeReceiptEntity> receipts(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_receipts WHERE idempotencyKey = :key")
    int receiptCount(String key);

    @Query("SELECT COUNT(*) FROM edge_job_dependencies d WHERE d.jobId = :jobId AND NOT EXISTS (" +
            "SELECT 1 FROM edge_receipts r WHERE r.jobId = d.dependsOnJobId " +
            "AND r.result IN ('COMMITTED','ALREADY_COMMITTED','DONE','PASS','SUCCESS'))")
    int unresolvedDependencies(String jobId);

    @Query("SELECT * FROM edge_jobs WHERE projectId = :projectId AND state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED') ORDER BY priority DESC, createdAt ASC LIMIT :limit")
    List<EdgeJobEntity> pendingJobs(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_jobs WHERE state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED','REMOTE_QUEUED')")
    int countPendingJobs();

    @Query("SELECT * FROM edge_memory WHERE projectId = :projectId AND scope = :scope AND (expiresAt IS NULL OR expiresAt > :now) ORDER BY pinned DESC, updatedAt DESC LIMIT :limit")
    List<EdgeMemoryEntity> memoryForScope(String projectId, String scope, long now, int limit);

    @Query("SELECT * FROM edge_memory WHERE projectId = :projectId AND scope = :scope AND memoryKey = :key LIMIT 1")
    EdgeMemoryEntity memoryItem(String projectId, String scope, String key);

    @Query("UPDATE edge_jobs SET state = :state, updatedAt = :updatedAt WHERE localId = :localId")
    int setJobState(String localId, String state, long updatedAt);

    @Query("DELETE FROM edge_jobs WHERE localId = :localId")
    int deleteJob(String localId);

    @Query("DELETE FROM edge_memory WHERE pinned = 0 AND expiresAt IS NOT NULL AND expiresAt <= :now")
    int deleteExpiredMemory(long now);
}
