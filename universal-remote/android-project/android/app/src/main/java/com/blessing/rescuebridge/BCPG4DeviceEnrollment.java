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

    private static boolean wifiAvailable(){
        try{
            java.util.Enumeration<java.net.NetworkInterface> e=
                java.net.NetworkInterface.getNetworkInterfaces();
            if(e==null)return false;
            while(e.hasMoreElements()){
                java.net.NetworkInterface iface=e.nextElement();
                if(iface.isUp()&&!iface.isLoopback()&&
                   iface.getName().toLowerCase(java.util.Locale.ROOT).startsWith("wlan"))
                    return true;
            }
        }catch(Exception ignored){}
        return false;
    }
    private static String invoke(Context ctx,String endpoint,JSONObject payload,
                                 SecureDeviceIdentity.Credential device) throws Exception {
        String legacy=SecurePairingStore.load(ctx);
        if(legacy==null||!legacy.matches("[0-9a-fA-F]{64}"))
            throw new SecurityException("G2_PAIRING_REQUIRED");
        if(wifiAvailable()){
            try{
                G2TransportClient local=new G2TransportClient("192.168.168.106",8898,legacy,
                    "66d6f13e525f517b97e1e553eebd5cc024ecb861c4ae7becfdfedaefcbc928cd");
                return device==null?local.perform(endpoint,payload.toString()):
                    local.performDevice(endpoint,payload.toString(),device.deviceId,device.secret);
            }catch(SecurityException ex){
                throw ex;
            }catch(IllegalStateException ex){
                // An authenticated server denial must not trigger a cellular
                // retry; only network unavailability allows failover.
                if(ex.getMessage()!=null&&ex.getMessage().startsWith("Server declined:"))
                    throw ex;
            }catch(Exception unavailable){
                // LAN unavailable: private Tailscale HTTPS fallback.
            }
        }
        G2TransportClient tailnet=new G2TransportClient(
            "mbmpc.taild48ba2.ts.net",443,legacy,"");
        return device==null?tailnet.perform(endpoint,payload.toString()):
            tailnet.performDevice(endpoint,payload.toString(),device.deviceId,device.secret);
    }

    /** All file actions require the individually signed, locally approved device. */
    public static JSONObject ownerFiles(Context ctx,String action,JSONObject args) throws Exception {
        if(action==null || !(
                action.equals("begin") || action.equals("append") ||
                action.equals("status") || action.equals("commit") ||
                action.equals("abort")))
            throw new SecurityException("G4_FILE_ACTION_NOT_ALLOWED");
        if(args==null)throw new IllegalArgumentException("G4_ARGS_REQUIRED");
        SecureDeviceIdentity.Credential ident=SecureDeviceIdentity.getOrCreate(ctx);
        JSONObject payload=new JSONObject().put("action",action).put("args",args);
        JSONObject response=new JSONObject(invoke(ctx,"/v1/g4/owner/files",payload,ident));
        if(!response.optBoolean("ok"))
            throw new SecurityException("G4_OWNER_FILE_ACTION_REFUSED");
        return response.getJSONObject("result");
    }

    public static String request(Context ctx) throws Exception {
        SecureDeviceIdentity.Credential ident=SecureDeviceIdentity.getOrCreate(ctx);
        JSONObject payload=new JSONObject()
            .put("device_id",ident.deviceId)
            .put("device_secret",ident.secret)
            .put("label","Samsung BCP personnel");
        JSONObject reply=new JSONObject(invoke(ctx,"/v1/g4/device/enroll/request",payload,null));
        if(!reply.optBoolean("ok"))throw new SecurityException("SERVER_REJECTED");
        JSONObject value=reply.getJSONObject("result");
        if("ALREADY_ENROLLED".equals(value.optString("status")))
            return "ALREADY_ENROLLED";
        String code=value.getString("verification_code");
        if(!code.matches("[0-9]{6}"))throw new SecurityException("ENROLLMENT_CODE_INVALID");
        return code;
    }

    public static int checkOwnedWindowsDrives(Context ctx) throws Exception {
        SecureDeviceIdentity.Credential ident=SecureDeviceIdentity.getOrCreate(ctx);
        JSONObject body=new JSONObject()
            .put("action","system.volumes").put("args",new JSONObject());
        JSONObject reply=new JSONObject(invoke(ctx,"/v1/g4/universal/inventory",body,ident));
        if(!reply.optBoolean("ok"))throw new SecurityException("OWNER_ACCESS_REJECTED");
        return reply.getJSONObject("result").getJSONObject("data")
            .getJSONArray("drives").length();
    }
}
