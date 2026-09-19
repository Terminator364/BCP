package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Index;
import androidx.room.PrimaryKey;

@Entity(
        tableName = "edge_receipts",
        indices = {
                @Index(value = {"projectId", "idempotencyKey"}),
                @Index(value = {"jobId", "createdAt"})
        }
)
public final class EdgeReceiptEntity {
    @PrimaryKey
    @NonNull
    public String actionId;
    @NonNull
    public String jobId;
    @NonNull
    public String projectId;
    @NonNull
    public String idempotencyKey;
    @NonNull
    public String result;
    @NonNull
    public String outputHash;
    public long committedRevision;
    public long createdAt;

    public EdgeReceiptEntity(@NonNull String actionId, @NonNull String jobId,
                             @NonNull String projectId, @NonNull String idempotencyKey,
                             @NonNull String result, @NonNull String outputHash,
                             long committedRevision, long createdAt) {
        this.actionId = actionId;
        this.jobId = jobId;
        this.projectId = projectId;
        this.idempotencyKey = idempotencyKey;
        this.result = result;
        this.outputHash = outputHash;
        this.committedRevision = committedRevision;
        this.createdAt = createdAt;
    }
}
