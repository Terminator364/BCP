package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Index;
import androidx.room.PrimaryKey;

@Entity(
        tableName = "edge_jobs",
        indices = {
                @Index(value = {"projectId", "idempotencyKey"}, unique = true),
                @Index(value = {"projectId", "state", "priority"})
        }
)
public final class EdgeJobEntity {
    @PrimaryKey
    @NonNull
    public String localId;
    @NonNull
    public String projectId;
    @NonNull
    public String kind;
    @NonNull
    public String payloadJson;
    @NonNull
    public String state;
    public boolean requiresPc;
    public int priority;
    @NonNull
    public String resourceClass;
    @NonNull
    public String idempotencyKey;
    public long createdAt;
    public long updatedAt;

    public EdgeJobEntity(@NonNull String localId, @NonNull String projectId,
                         @NonNull String kind, @NonNull String payloadJson,
                         @NonNull String state, boolean requiresPc, int priority,
                         @NonNull String resourceClass, @NonNull String idempotencyKey,
                         long createdAt, long updatedAt) {
        this.localId = localId;
        this.projectId = projectId;
        this.kind = kind;
        this.payloadJson = payloadJson;
        this.state = state;
        this.requiresPc = requiresPc;
        this.priority = priority;
        this.resourceClass = resourceClass;
        this.idempotencyKey = idempotencyKey;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }
}
