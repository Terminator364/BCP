package com.blessing.bcpedge.storage;

import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;

import java.util.List;

@Dao
public interface EdgeDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putProject(EdgeProjectEntity project);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertJob(EdgeJobEntity job);

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void putMemory(EdgeMemoryEntity memory);

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    long insertReceipt(EdgeReceiptEntity receipt);

    @Query("SELECT * FROM edge_jobs WHERE projectId = :projectId AND state IN ('READY','WAITING_FOR_PC','HOLD') ORDER BY priority DESC, createdAt ASC LIMIT :limit")
    List<EdgeJobEntity> pendingJobs(String projectId, int limit);

    @Query("SELECT COUNT(*) FROM edge_jobs WHERE state IN ('READY','WAITING_FOR_PC','HOLD')")
    int countPendingJobs();

    @Query("SELECT * FROM edge_memory WHERE projectId = :projectId AND scope = :scope AND (expiresAt IS NULL OR expiresAt > :now) ORDER BY pinned DESC, updatedAt DESC LIMIT :limit")
    List<EdgeMemoryEntity> memoryForScope(String projectId, String scope, long now, int limit);

    @Query("UPDATE edge_jobs SET state = :state, updatedAt = :updatedAt WHERE localId = :localId")
    int setJobState(String localId, String state, long updatedAt);

    @Query("DELETE FROM edge_memory WHERE pinned = 0 AND expiresAt IS NOT NULL AND expiresAt <= :now")
    int deleteExpiredMemory(long now);
}
