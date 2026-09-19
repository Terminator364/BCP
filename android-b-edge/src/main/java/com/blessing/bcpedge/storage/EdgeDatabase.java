package com.blessing.bcpedge.storage;

import android.content.Context;

import androidx.room.Database;
import androidx.room.Room;
import androidx.room.RoomDatabase;

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
                        .fallbackToDestructiveMigration()
                        .build();
                INSTANCE = local;
            }
        }
        return local;
    }
}
