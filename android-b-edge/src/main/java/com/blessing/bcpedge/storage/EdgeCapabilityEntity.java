package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.Entity;
import androidx.room.Index;

@Entity(
        tableName = "edge_capabilities",
        primaryKeys = {"projectId", "capabilityId"},
        indices = {
                @Index(value = {"projectId", "provider", "state", "updatedAt"}),
                @Index(value = {"projectId", "capabilityKind", "updatedAt"})
        }
)
public final class EdgeCapabilityEntity {
    @NonNull public String projectId;
    @NonNull public String capabilityId;
    @NonNull public String nodeId;
    @NonNull public String provider;
    @NonNull public String capabilityKind;
    @NonNull public String state;
    @NonNull public String transport;
    @NonNull public String detailsJson;
    @NonNull public String evidenceClass;
    public long observedAt;
    @Nullable public Long expiresAt;
    public long updatedAt;

    public EdgeCapabilityEntity(@NonNull String projectId, @NonNull String capabilityId,
                                @NonNull String nodeId, @NonNull String provider,
                                @NonNull String capabilityKind, @NonNull String state,
                                @NonNull String transport, @NonNull String detailsJson,
                                @NonNull String evidenceClass, long observedAt,
                                @Nullable Long expiresAt, long updatedAt) {
        this.projectId = projectId;
        this.capabilityId = capabilityId;
        this.nodeId = nodeId;
        this.provider = provider;
        this.capabilityKind = capabilityKind;
        this.state = state;
        this.transport = transport;
        this.detailsJson = detailsJson;
        this.evidenceClass = evidenceClass;
        this.observedAt = observedAt;
        this.expiresAt = expiresAt;
        this.updatedAt = updatedAt;
    }
}
