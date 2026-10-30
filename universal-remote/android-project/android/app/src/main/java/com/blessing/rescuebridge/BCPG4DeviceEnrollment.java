package com.blessing.rescuebridge;

import android.content.Context;
import org.json.JSONObject;

/**
 * G4 individual-device enrollment transport.
 * This class does not grant owner access: the signed-in Windows user must
 * confirm the displayed six-digit challenge in the BCP Owner Center.
 */
public final class BCPG4DeviceEnrollment {
    private BCPG4DeviceEnrollment(){}

    private static G2TransportClient transport(Context ctx) throws Exception {
        String legacy=SecurePairingStore.load(ctx);
        if(legacy==null||!legacy.matches("[0-9a-fA-F]{64}"))
            throw new SecurityException("G2_PAIRING_REQUIRED");
        return new G2TransportClient("mbmpc.taild48ba2.ts.net",443,legacy,"");
    }

    public static String request(Context ctx) throws Exception {
        SecureDeviceIdentity.Credential ident=SecureDeviceIdentity.getOrCreate(ctx);
        JSONObject payload=new JSONObject()
            .put("device_id",ident.deviceId)
            .put("device_secret",ident.secret)
            .put("label","Samsung BCP personnel");
        JSONObject reply=new JSONObject(transport(ctx).perform(
            "/v1/g4/device/enroll/request",payload.toString()));
        if(!reply.optBoolean("ok"))throw new SecurityException("SERVER_REJECTED");
        JSONObject value=reply.getJSONObject("result");
        String code=value.getString("verification_code");
        if(!code.matches("[0-9]{6}"))throw new SecurityException("ENROLLMENT_CODE_INVALID");
        return code;
    }

    public static int checkOwnedWindowsDrives(Context ctx) throws Exception {
        SecureDeviceIdentity.Credential ident=SecureDeviceIdentity.getOrCreate(ctx);
        JSONObject body=new JSONObject()
            .put("action","system.volumes").put("args",new JSONObject());
        JSONObject reply=new JSONObject(transport(ctx).performDevice(
            "/v1/g4/universal/inventory",body.toString(),
            ident.deviceId,ident.secret));
        if(!reply.optBoolean("ok"))throw new SecurityException("OWNER_ACCESS_REJECTED");
        return reply.getJSONObject("result").getJSONObject("data")
            .getJSONArray("drives").length();
    }
}
