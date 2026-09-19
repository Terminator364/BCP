package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;

@Entity(tableName="edge_context_cache", primaryKeys={"projectId"})
public final class EdgeContextEntity {
    @NonNull public String projectId;
    @NonNull public String payloadJson;
    @NonNull public String sourceRevision;
    @NonNull public String sourceHash;
    public long updatedAt;

    public EdgeContextEntity(@NonNull String projectId, @NonNull String payloadJson,
                             @NonNull String sourceRevision, @NonNull String sourceHash,
                             long updatedAt) {
        this.projectId=projectId;
        this.payloadJson=payloadJson;
        this.sourceRevision=sourceRevision;
        this.sourceHash=sourceHash;
        this.updatedAt=updatedAt;
    }
}
