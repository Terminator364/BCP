package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;

@Entity(tableName="edge_job_dependencies", primaryKeys={"jobId","dependsOnJobId"})
public final class EdgeDependencyEntity {
    @NonNull public String jobId;
    @NonNull public String dependsOnJobId;
    public EdgeDependencyEntity(@NonNull String jobId,@NonNull String dependsOnJobId){
        this.jobId=jobId; this.dependsOnJobId=dependsOnJobId;
    }
}
