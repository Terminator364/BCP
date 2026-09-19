package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

@Entity(tableName = "edge_projects")
public final class EdgeProjectEntity {
    @PrimaryKey
    @NonNull
    public String projectId;
    @NonNull
    public String status;
    public long headRevision;
    public long coordinatorEpoch;
    public long updatedAt;

    public EdgeProjectEntity(@NonNull String projectId, @NonNull String status,
                             long headRevision, long coordinatorEpoch, long updatedAt) {
        this.projectId = projectId;
        this.status = status;
        this.headRevision = headRevision;
        this.coordinatorEpoch = coordinatorEpoch;
        this.updatedAt = updatedAt;
    }
}
