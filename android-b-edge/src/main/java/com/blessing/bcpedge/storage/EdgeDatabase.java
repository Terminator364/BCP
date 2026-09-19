package com.blessing.bcpedge.storage;

import android.content.Context;

import androidx.room.Database;
import androidx.room.Room;
import androidx.room.RoomDatabase;
import androidx.room.migration.Migration;
import androidx.sqlite.db.SupportSQLiteDatabase;
import androidx.annotation.NonNull;

@Database(
        entities = {
                EdgeProjectEntity.class,
                EdgeJobEntity.class,
                EdgeMemoryEntity.class,
                EdgeReceiptEntity.class,
                EdgeDependencyEntity.class,
                EdgeContextEntity.class
        },
        version = 2,
        exportSchema = false
)
public abstract class EdgeDatabase extends RoomDatabase {
    private static volatile EdgeDatabase INSTANCE;

    private static final Migration MIGRATION_1_2 = new Migration(1, 2) {
        @Override public void migrate(@NonNull SupportSQLiteDatabase db) {
            db.execSQL("CREATE TABLE IF NOT EXISTS edge_job_dependencies (jobId TEXT NOT NULL, dependsOnJobId TEXT NOT NULL, PRIMARY KEY(jobId, dependsOnJobId))");
            db.execSQL("CREATE TABLE IF NOT EXISTS edge_context_cache (projectId TEXT NOT NULL, payloadJson TEXT NOT NULL, sourceRevision TEXT NOT NULL, sourceHash TEXT NOT NULL, updatedAt INTEGER NOT NULL, PRIMARY KEY(projectId))");
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
                        .addMigrations(MIGRATION_1_2)
                        .build();
                INSTANCE = local;
            }
        }
        return local;
    }
}
