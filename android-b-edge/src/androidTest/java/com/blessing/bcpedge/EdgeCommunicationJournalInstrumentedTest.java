package com.blessing.bcpedge;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class EdgeCommunicationJournalInstrumentedTest {
    @Test public void localCommunicationJournalCommitsOfflineWithoutPc() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        BcpClient client = new BcpClient(context);
        client.setProject("instrumented-communication-proof");

        String key = "android-test-" + System.currentTimeMillis();
        JSONObject payload = new JSONObject();
        payload.put("idempotency_key", key);
        payload.put("channel", "TEST");
        payload.put("direction", "LOCAL");
        payload.put("kind", "CHECKPOINT");
        payload.put("state", "STAGED");
        payload.put("text", "offline communication proof");
        payload.put("source_node", "ANDROID_EMULATOR");

        JSONObject queued = client.queueJob("LOCAL_COMMUNICATION_RECORD", payload, false);
        assertTrue("must execute locally without PC", queued.optBoolean("executed_locally", false));

        JSONArray rows = client.communicationHistory();
        boolean found = false;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row == null) continue;
            if (key.equals(row.optString("record_id", ""))) {
                found = true;
                JSONObject value = row.optJSONObject("value");
                assertNotNull(value);
                assertEquals("offline communication proof", value.optString("text", ""));
                assertEquals("ANDROID_EMULATOR", value.optString("source_node", ""));
                break;
            }
        }
        assertTrue("durable communication record must be readable locally", found);
    }
}
