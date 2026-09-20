package com.blessing.bcpedge.storage;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

@Entity(tableName = "edge_sentinel")
public final class EdgeSentinelEntity {
    @PrimaryKey
    @NonNull
    public String projectId;
    @NonNull
    public String state;
    public long lastPcSuccessAt;
    public long lastCheckAt;
    public int consecutiveFailures;
    @NonNull
    public String lastAlertKey;
    public long lastAlertAt;
    public boolean resumePending;
    @NonNull
    public String resumeRequestId;

    public EdgeSentinelEntity(@NonNull String projectId, @NonNull String state,
                              long lastPcSuccessAt, long lastCheckAt,
                              int consecutiveFailures, @NonNull String lastAlertKey,
                              long lastAlertAt, boolean resumePending,
                              @NonNull String resumeRequestId) {
        this.projectId = projectId;
        this.state = state;
        this.lastPcSuccessAt = lastPcSuccessAt;
        this.lastCheckAt = lastCheckAt;
        this.consecutiveFailures = consecutiveFailures;
        this.lastAlertKey = lastAlertKey;
        this.lastAlertAt = lastAlertAt;
        this.resumePending = resumePending;
        this.resumeRequestId = resumeRequestId;
    }
}
