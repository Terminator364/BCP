package com.blessing.bcpedge.storage;

import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import androidx.room.Transaction;

import java.util.List;

@Dao
public interface EdgeDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putProject(EdgeProjectEntity project);

    @Query("SELECT * FROM edge_projects ORDER BY updatedAt DESC")
    List<EdgeProjectEntity> projects();

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertJob(EdgeJobEntity job);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertDependency(EdgeDependencyEntity dep);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putMemory(EdgeMemoryEntity memory);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertReceipt(EdgeReceiptEntity receipt);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putContext(EdgeContextEntity context);

    @Query("SELECT * FROM edge_context_cache WHERE projectId=:projectId LIMIT 1")
    EdgeContextEntity contextForProject(String projectId);

    @Query("SELECT * FROM edge_jobs WHERE projectId = :projectId AND state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED') ORDER BY priority DESC, createdAt ASC LIMIT :limit")
    List<EdgeJobEntity> pendingJobs(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_jobs WHERE state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED')")
    int countPendingJobs();

    @Query("SELECT COUNT(*) FROM edge_jobs WHERE projectId=:projectId AND state IN ('READY','WAITING_FOR_PC','HOLD','BLOCKED')")
    int countPendingJobs(String projectId);

    @Query("SELECT * FROM edge_memory WHERE projectId = :projectId AND scope = :scope AND (expiresAt IS NULL OR expiresAt > :now) ORDER BY pinned DESC, updatedAt DESC LIMIT :limit")
    List<EdgeMemoryEntity> memoryForScope(String projectId, String scope, long now, int limit);

    @Query("UPDATE edge_jobs SET state = :state, updatedAt = :updatedAt WHERE localId = :localId")
    int setJobState(String localId, String state, long updatedAt);

    @Query("SELECT COUNT(*) FROM edge_job_dependencies d JOIN edge_jobs p ON p.localId=d.dependsOnJobId WHERE d.jobId=:jobId AND p.state NOT IN ('ACKED','DONE')")
    int unresolvedDependencies(String jobId);

    @Query("DELETE FROM edge_memory WHERE pinned = 0 AND expiresAt IS NOT NULL AND expiresAt <= :now")
    int deleteExpiredMemory(long now);

    @Query("DELETE FROM edge_context_cache WHERE updatedAt < :cutoff")
    int deleteStaleContext(long cutoff);

    @Transaction
    default boolean admitJob(EdgeJobEntity job, List<EdgeDependencyEntity> deps, int queueLimit) {
        if (countPendingJobs(job.projectId) >= queueLimit) return false;
        if (insertJob(job) == -1L) return true;
        if (deps != null) {
            for (EdgeDependencyEntity dep : deps) insertDependency(dep);
        }
        return true;
    }
}
