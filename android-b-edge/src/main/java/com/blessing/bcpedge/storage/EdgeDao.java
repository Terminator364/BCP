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

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertReceipt(EdgeReceiptEntity receipt);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertDependency(EdgeDependencyEntity dependency);

    @Query("SELECT * FROM edge_projects ORDER BY updatedAt DESC")
    List<EdgeProjectEntity> projects();

    @Query("SELECT * FROM edge_projects WHERE projectId = :projectId LIMIT 1")
    EdgeProjectEntity project(String projectId);

    @Query("SELECT * FROM edge_receipts WHERE projectId = :projectId ORDER BY createdAt DESC LIMIT :limit")
    List<EdgeReceiptEntity> receipts(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_receipts WHERE idempotencyKey = :key")
    int receiptCount(String key);

    @Query("SELECT COUNT(*) FROM edge_job_dependencies d WHERE d.jobId = :jobId AND NOT EXISTS (SELECT 1 FROM edge_receipts r WHERE r.jobId = d.dependsOnJobId)")
    int unresolvedDependencies(String jobId);

    @Query("SELECT * FROM edge_jobs WHERE projectId = :projectId AND state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED') ORDER BY priority DESC, createdAt ASC LIMIT :limit")
    List<EdgeJobEntity> pendingJobs(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_jobs WHERE state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED')")
    int countPendingJobs();

    @Query("SELECT * FROM edge_memory WHERE projectId = :projectId AND scope = :scope AND (expiresAt IS NULL OR expiresAt > :now) ORDER BY pinned DESC, updatedAt DESC LIMIT :limit")
    List<EdgeMemoryEntity> memoryForScope(String projectId, String scope, long now, int limit);

    @Query("UPDATE edge_jobs SET state = :state, updatedAt = :updatedAt WHERE localId = :localId")
    int setJobState(String localId, String state, long updatedAt);

    @Query("DELETE FROM edge_jobs WHERE localId = :localId")
    int deleteJob(String localId);

    @Query("DELETE FROM edge_memory WHERE pinned = 0 AND expiresAt IS NOT NULL AND expiresAt <= :now")
    int deleteExpiredMemory(long now);
}
