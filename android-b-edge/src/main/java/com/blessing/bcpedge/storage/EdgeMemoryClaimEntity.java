package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Index;

@Entity(
        tableName = "edge_memory_claims",
        indices = {
                @Index(value = {"projectId", "scope", "memoryKey", "admittedAt"}),
                @Index(value = {"projectId", "idempotencyKey"}, unique = true),
                @Index(value = {"projectId", "state", "updatedAt"})
        }
)
public final class EdgeMemoryClaimEntity {
    @androidx.room.PrimaryKey
    @NonNull public String claimId;
    @NonNull public String projectId;
    @NonNull public String scope;
    @NonNull public String memoryKey;
    @NonNull public String valueJson;
    @NonNull public String evidenceClass;
    @NonNull public String source;
    @NonNull public String authority;
    @NonNull public String supersedesClaimId;
    @NonNull public String state;
    @NonNull public String reason;
    @NonNull public String idempotencyKey;
    public boolean pinned;
    public long admittedAt;
    public long updatedAt;

    public EdgeMemoryClaimEntity(@NonNull String claimId, @NonNull String projectId,
                                 @NonNull String scope, @NonNull String memoryKey,
                                 @NonNull String valueJson, @NonNull String evidenceClass,
                                 @NonNull String source, @NonNull String authority,
                                 @NonNull String supersedesClaimId, @NonNull String state,
                                 @NonNull String reason, @NonNull String idempotencyKey,
                                 boolean pinned, long admittedAt, long updatedAt) {
        this.claimId = claimId;
        this.projectId = projectId;
        this.scope = scope;
        this.memoryKey = memoryKey;
        this.valueJson = valueJson;
        this.evidenceClass = evidenceClass;
        this.source = source;
        this.authority = authority;
        this.supersedesClaimId = supersedesClaimId;
        this.state = state;
        this.reason = reason;
        this.idempotencyKey = idempotencyKey;
        this.pinned = pinned;
        this.admittedAt = admittedAt;
        this.updatedAt = updatedAt;
    }
}
