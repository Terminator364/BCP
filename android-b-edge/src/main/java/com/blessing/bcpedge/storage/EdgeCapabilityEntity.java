package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Index;
import androidx.room.PrimaryKey;

/**
 * Durable phone-resident capability/source observation.
 *
 * The dedicated phone is not just a relay: it keeps a local, queryable view of
 * which execution/communication/data capabilities are currently available,
 * what evidence established that state, and when the observation expires.
 */
@Entity(
        tableName = "edge_capabilities",
        indices = {
                @Index(value = {"projectId", "capabilityType", "updatedAt"}),
                @Index(value = {"projectId", "availabilityState", "updatedAt"}),
                @Index(value = {"sourceKind", "updatedAt"})
        }
)
public final class EdgeCapabilityEntity {
    @PrimaryKey @NonNull public String capabilityId;
    @NonNull public String projectId;
    @NonNull public String capabilityType;
    @NonNull public String provider;
    @NonNull public String sourceKind;
    @NonNull public String availabilityState;
    @NonNull public String evidenceClass;
    @NonNull public String endpointHint;
    @NonNull public String metadataJson;
    @NonNull public String metadataSha256;
    public long observedAt;
    public long updatedAt;
    public long expiresAt;

    public EdgeCapabilityEntity(@NonNull String capabilityId, @NonNull String projectId,
                                @NonNull String capabilityType, @NonNull String provider,
                                @NonNull String sourceKind, @NonNull String availabilityState,
                                @NonNull String evidenceClass, @NonNull String endpointHint,
                                @NonNull String metadataJson, @NonNull String metadataSha256,
                                long observedAt, long updatedAt, long expiresAt) {
        this.capabilityId = capabilityId;
        this.projectId = projectId;
        this.capabilityType = capabilityType;
        this.provider = provider;
        this.sourceKind = sourceKind;
        this.availabilityState = availabilityState;
        this.evidenceClass = evidenceClass;
        this.endpointHint = endpointHint;
        this.metadataJson = metadataJson;
        this.metadataSha256 = metadataSha256;
        this.observedAt = observedAt;
        this.updatedAt = updatedAt;
        this.expiresAt = expiresAt;
    }
}
