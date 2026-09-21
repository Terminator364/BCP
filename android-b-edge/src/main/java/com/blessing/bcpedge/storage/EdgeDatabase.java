package com.blessing.bcpedge.storage;

import android.content.Context;

import androidx.room.Database;
import androidx.room.Room;
import androidx.room.RoomDatabase;
import androidx.room.migration.Migration;
import androidx.sqlite.db.SupportSQLiteDatabase;

@Database(
        entities = {
                EdgeProjectEntity.class,
                EdgeJobEntity.class,
                EdgeMemoryEntity.class,
                EdgeReceiptEntity.class,
                EdgeDependencyEntity.class,
                EdgeSentinelEntity.class,
                EdgeEventEntity.class,
                EdgeMissionStepEntity.class
        },
        version = 4,
        exportSchema = false
)
public abstract class EdgeDatabase extends RoomDatabase {
    private static volatile EdgeDatabase INSTANCE;

    private static final Migration MIGRATION_1_2 = new Migration(1, 2) {
        @Override
        public void migrate(SupportSQLiteDatabase db) {
            db.execSQL("CREATE TABLE IF NOT EXISTS edge_sentinel (" +
                    "projectId TEXT NOT NULL PRIMARY KEY, " +
                    "state TEXT NOT NULL, " +
                    "lastPcSuccessAt INTEGER NOT NULL, " +
                    "lastCheckAt INTEGER NOT NULL, " +
                    "consecutiveFailures INTEGER NOT NULL, " +
                    "lastAlertKey TEXT NOT NULL, " +
                    "lastAlertAt INTEGER NOT NULL, " +
                    "resumePending INTEGER NOT NULL, " +
                    "resumeRequestId TEXT NOT NULL)");
        }
    };

    private static final Migration MIGRATION_2_3 = new Migration(2, 3) {
        @Override
        public void migrate(SupportSQLiteDatabase db) {
            db.execSQL("CREATE TABLE IF NOT EXISTS edge_events (" +
                    "eventId TEXT NOT NULL PRIMARY KEY, " +
                    "projectId TEXT NOT NULL, " +
                    "eventType TEXT NOT NULL, " +
                    "actorType TEXT NOT NULL, " +
                    "source TEXT NOT NULL, " +
                    "truthStatus TEXT NOT NULL, " +
                    "payloadJson TEXT NOT NULL, " +
                    "payloadSha256 TEXT NOT NULL, " +
                    "idempotencyKey TEXT NOT NULL, " +
                    "occurredAt INTEGER NOT NULL, " +
                    "ingestedAt INTEGER NOT NULL)");
            db.execSQL("CREATE INDEX IF NOT EXISTS index_edge_events_projectId_occurredAt ON edge_events(projectId, occurredAt)");
            db.execSQL("CREATE INDEX IF NOT EXISTS index_edge_events_eventType_occurredAt ON edge_events(eventType, occurredAt)");
            db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_edge_events_projectId_idempotencyKey ON edge_events(projectId, idempotencyKey)");
        }
    };

    private static final Migration MIGRATION_3_4 = new Migration(3, 4) {
        @Override
        public void migrate(SupportSQLiteDatabase db) {
            db.execSQL("CREATE TABLE IF NOT EXISTS edge_mission_steps (" +
                    "stepId TEXT NOT NULL PRIMARY KEY, " +
                    "missionId TEXT NOT NULL, " +
                    "projectId TEXT NOT NULL, " +
                    "stepRevision INTEGER NOT NULL, " +
                    "requestedOperation TEXT NOT NULL, " +
                    "inputHash TEXT NOT NULL, " +
                    "contextCapsuleHash TEXT NOT NULL, " +
                    "policyRevision TEXT NOT NULL, " +
                    "expectedStateRevision INTEGER NOT NULL, " +
                    "lastConfirmedCheckpoint TEXT NOT NULL, " +
                    "dependenciesJson TEXT NOT NULL, " +
                    "sideEffectClass TEXT NOT NULL, " +
                    "idempotencyKey TEXT NOT NULL, " +
                    "fencingToken TEXT NOT NULL, " +
                    "nextSafeAction TEXT NOT NULL, " +
                    "continuationFrontier TEXT NOT NULL, " +
                    "providerState TEXT NOT NULL, " +
                    "createdAtWallMs INTEGER NOT NULL, " +
                    "createdAtElapsedMs INTEGER NOT NULL, " +
                    "updatedAtWallMs INTEGER NOT NULL)");
            db.execSQL("CREATE INDEX IF NOT EXISTS index_edge_mission_steps_projectId_providerState_updatedAtWallMs ON edge_mission_steps(projectId, providerState, updatedAtWallMs)");
            db.execSQL("CREATE INDEX IF NOT EXISTS index_edge_mission_steps_missionId_updatedAtWallMs ON edge_mission_steps(missionId, updatedAtWallMs)");
            db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_edge_mission_steps_projectId_idempotencyKey ON edge_mission_steps(projectId, idempotencyKey)");
        }
    };

    public abstract EdgeDao edgeDao();

    public static EdgeDatabase get(Context context) {
        EdgeDatabase local = INSTANCE;
        if (local != null) return local;
        synchronized (EdgeDatabase.class) {
            local = INSTANCE;
            if (local == null) {
                local = Room.databaseBuilder(
                                context.getApplicationContext(),
                                EdgeDatabase.class,
                                "bcp-edge-v2-shadow.db")
                        .setJournalMode(JournalMode.WRITE_AHEAD_LOGGING)
                        .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4)
                        .build();
                INSTANCE = local;
            }
        }
        return local;
    }
}
