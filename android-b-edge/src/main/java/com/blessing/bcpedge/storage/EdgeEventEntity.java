package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Index;
import androidx.room.PrimaryKey;

/**
 * Append-only local Universal Chronicle event.
 * Exact/observable event records are durable evidence pointers; derived memory remains separate.
 */
@Entity(
        tableName = "edge_events",
        indices = {
                @Index(value = {"projectId", "occurredAt"}),
                @Index(value = {"eventType", "occurredAt"}),
                @Index(value = {"projectId", "idempotencyKey"}, unique = true)
        }
)
public final class EdgeEventEntity {
    @PrimaryKey @NonNull public String eventId;
    @NonNull public String projectId;
    @NonNull public String eventType;
    @NonNull public String actorType;
    @NonNull public String source;
    @NonNull public String truthStatus;
    @NonNull public String payloadJson;
    @NonNull public String payloadSha256;
    @NonNull public String idempotencyKey;
    public long occurredAt;
    public long ingestedAt;

    public EdgeEventEntity(@NonNull String eventId, @NonNull String projectId,
                           @NonNull String eventType, @NonNull String actorType,
                           @NonNull String source, @NonNull String truthStatus,
                           @NonNull String payloadJson, @NonNull String payloadSha256,
                           @NonNull String idempotencyKey, long occurredAt, long ingestedAt) {
        this.eventId = eventId;
        this.projectId = projectId;
        this.eventType = eventType;
        this.actorType = actorType;
        this.source = source;
        this.truthStatus = truthStatus;
        this.payloadJson = payloadJson;
        this.payloadSha256 = payloadSha256;
        this.idempotencyKey = idempotencyKey;
        this.occurredAt = occurredAt;
        this.ingestedAt = ingestedAt;
    }
}
