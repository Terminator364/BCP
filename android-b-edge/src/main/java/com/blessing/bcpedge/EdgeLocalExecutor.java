package com.blessing.bcpedge;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

public final class EdgeLocalExecutor {
    private EdgeLocalExecutor() {}

    public static JSONObject drain(Context context, BcpClient client) {
        JSONObject out = new JSONObject();
        int attempted = 0;
        int sent = 0;
        int waiting = 0;
        try {
            EdgeOrchestrator orchestrator = new EdgeOrchestrator(context);
            EdgeTelegramSender telegram = new EdgeTelegramSender(context);
            JSONObject network = EdgeConnectivity.snapshot(context);

            if (!telegram.configured() && !client.getServer().isEmpty() && !client.getToken().isEmpty()) {
                telegram.bootstrapFromPairedPc(client);
            }

            JSONArray jobs = orchestrator.pendingJobs(client.getProject());
            for (int i = 0; i < jobs.length() && attempted < 24; i++) {
                JSONObject job = jobs.optJSONObject(i);
                if (job == null || job.optBoolean("requires_pc", true)) continue;
                String kind = job.optString("kind", "");
                if (!"TELEGRAM_SEND".equals(kind) && !"COMMUNICATION_EVENT".equals(kind)) continue;
                attempted++;

                JSONObject payload = job.optJSONObject("payload");
                if (payload == null) payload = new JSONObject();
                String channel = payload.optString("channel", "TELEGRAM");
                if (!"TELEGRAM".equalsIgnoreCase(channel)) {
                    orchestrator.setJobState(job.optString("local_id", ""), "HOLD");
                    continue;
                }
                String text = payload.optString("text", "");
                if (text.isEmpty()) {
                    orchestrator.setJobState(job.optString("local_id", ""), "HOLD");
                    continue;
                }
                if (!network.optBoolean("validated_internet", false) || !telegram.configured()) {
                    orchestrator.setJobState(job.optString("local_id", ""), "NETWORK_WAIT");
                    waiting++;
                    continue;
                }
                try {
                    JSONObject receipt = telegram.sendText(text);
                    orchestrator.acknowledgeLocalJob(client.getProject(), job, receipt);
                    sent++;
                } catch (Exception ex) {
                    orchestrator.setJobState(job.optString("local_id", ""), "NETWORK_WAIT");
                    client.recordEvent("EDGE_TELEGRAM_SEND_DEFERRED", ex.getClass().getSimpleName());
                    waiting++;
                }
            }

            out.put("ok", true);
            out.put("attempted", attempted);
            out.put("sent", sent);
            out.put("waiting", waiting);
            out.put("telegram_configured", telegram.configured());
            out.put("network", network);
        } catch (Exception ex) {
            try {
                out.put("ok", false);
                out.put("error_class", ex.getClass().getSimpleName());
            } catch (Exception ignored) {}
        }
        return out;
    }
}
