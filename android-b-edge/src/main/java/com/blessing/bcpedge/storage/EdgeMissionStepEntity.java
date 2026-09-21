package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Index;
import androidx.room.PrimaryKey;

/**
 * Durable UCMF Postulate-9 mission-step envelope.
 * It records resumable mission/provider state before remote waits so a dead
 * conversation/provider cannot become the mission authority.
 */
@Entity(
        tableName = "edge_mission_steps",
        indices = {
                @Index(value = {"projectId", "providerState", "updatedAtWallMs"}),
                @Index(value = {"missionId", "updatedAtWallMs"}),
                @Index(value = {"projectId", "idempotencyKey"}, unique = true)
        }
)
public final class EdgeMissionStepEntity {
    @PrimaryKey @NonNull public String stepId;
    @NonNull public String missionId;
    @NonNull public String projectId;
    public long stepRevision;
    @NonNull public String requestedOperation;
    @NonNull public String inputHash;
    @NonNull public String contextCapsuleHash;
    @NonNull public String policyRevision;
    public long expectedStateRevision;
    @NonNull public String lastConfirmedCheckpoint;
    @NonNull public String dependenciesJson;
    @NonNull public String sideEffectClass;
    @NonNull public String idempotencyKey;
    @NonNull public String fencingToken;
    @NonNull public String nextSafeAction;
    @NonNull public String continuationFrontier;
    @NonNull public String providerState;
    public long createdAtWallMs;
    public long createdAtElapsedMs;
    public long updatedAtWallMs;

    public EdgeMissionStepEntity(@NonNull String stepId, @NonNull String missionId,
                                 @NonNull String projectId, long stepRevision,
                                 @NonNull String requestedOperation, @NonNull String inputHash,
                                 @NonNull String contextCapsuleHash, @NonNull String policyRevision,
                                 long expectedStateRevision, @NonNull String lastConfirmedCheckpoint,
                                 @NonNull String dependenciesJson, @NonNull String sideEffectClass,
                                 @NonNull String idempotencyKey, @NonNull String fencingToken,
                                 @NonNull String nextSafeAction, @NonNull String continuationFrontier,
                                 @NonNull String providerState, long createdAtWallMs,
                                 long createdAtElapsedMs, long updatedAtWallMs) {
        this.stepId = stepId;
        this.missionId = missionId;
        this.projectId = projectId;
        this.stepRevision = stepRevision;
        this.requestedOperation = requestedOperation;
        this.inputHash = inputHash;
        this.contextCapsuleHash = contextCapsuleHash;
        this.policyRevision = policyRevision;
        this.expectedStateRevision = expectedStateRevision;
        this.lastConfirmedCheckpoint = lastConfirmedCheckpoint;
        this.dependenciesJson = dependenciesJson;
        this.sideEffectClass = sideEffectClass;
        this.idempotencyKey = idempotencyKey;
        this.fencingToken = fencingToken;
        this.nextSafeAction = nextSafeAction;
        this.continuationFrontier = continuationFrontier;
        this.providerState = providerState;
        this.createdAtWallMs = createdAtWallMs;
        this.createdAtElapsedMs = createdAtElapsedMs;
        this.updatedAtWallMs = updatedAtWallMs;
    }
}
