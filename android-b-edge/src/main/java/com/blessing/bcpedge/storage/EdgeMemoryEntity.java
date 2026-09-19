package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.room.Entity;
import androidx.room.Index;

@Entity(
        tableName = "edge_memory",
        primaryKeys = {"projectId", "scope", "memoryKey"},
        indices = {
                @Index(value = {"projectId", "scope", "updatedAt"}),
                @Index(value = {"evidenceClass", "pinned"})
        }
)
public final class EdgeMemoryEntity {
    @NonNull public String projectId;
    @NonNull public String scope;
    @NonNull public String memoryKey;
    @NonNull public String valueJson;
    @NonNull public String evidenceClass;
    @NonNull public String source;
    public boolean pinned;
    public long createdAt;
    public long updatedAt;
    @Nullable public Long expiresAt;

    public EdgeMemoryEntity(@NonNull String projectId, @NonNull String scope,
                            @NonNull String memoryKey, @NonNull String valueJson,
                            @NonNull String evidenceClass, @NonNull String source,
                            boolean pinned, long createdAt, long updatedAt,
                            @Nullable Long expiresAt) {
        this.projectId = projectId;
        this.scope = scope;
        this.memoryKey = memoryKey;
        this.valueJson = valueJson;
        this.evidenceClass = evidenceClass;
        this.source = source;
        this.pinned = pinned;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.expiresAt = expiresAt;
    }
}
