package com.blessing.rescuebridge;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.content.pm.PackageInfo;
import android.os.Build;
import org.json.JSONObject;

/** Explicitly requested, authenticated minimal phone status; no device identifiers or private data. */
public final class BCPPhoneReporter {
    private BCPPhoneReporter(){}
    private static String network(Context ctx){
        try{
            ConnectivityManager cm=(ConnectivityManager)ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
            if(cm==null||cm.getActiveNetwork()==null)return "offline";
            NetworkCapabilities n=cm.getNetworkCapabilities(cm.getActiveNetwork());
            if(n==null)return "offline";
            if(n.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))return "wifi";
            if(n.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))return "cellular";
            return "other";
        }catch(Exception e){return "other";}
    }
    private static String state(Context ctx) {
        String status=BCPAutoUpdater.status(ctx).toLowerCase(java.util.Locale.ROOT);
        if(status.contains("à jour") || status.contains("installée"))return "current";
        if(status.contains("en cours") || status.contains("vérification"))return "checking";
        if(status.contains("attente") || status.contains("prête") || status.contains("installation") ||
           status.contains("autorisation") || status.contains("confirmation"))return "pending";
        if(status.contains("erreur") || status.contains("refus") ||
           status.contains("indisponible") || status.contains("différée"))return "error";
        return "unknown";
    }
    public static boolean report(Context ctx) {
        try{
            String key=SecurePairingStore.load(ctx);
            if(key==null||!key.matches("[0-9a-fA-F]{64}"))return false;
            PackageInfo pkg=ctx.getPackageManager().getPackageInfo(ctx.getPackageName(),0);
            long version=Build.VERSION.SDK_INT>=28?pkg.getLongVersionCode():pkg.versionCode;
            if(version<=0 || version>100000)return false;
            JSONObject body=new JSONObject().put("version_code",version)
                .put("network",network(ctx))
                .put("update_state",state(ctx));
            String reply=new G2TransportClient("mbmpc.taild48ba2.ts.net",443,key,"")
                .perform("/v1/phone-state",body.toString());
            return new JSONObject(reply).optBoolean("ok");
        }catch(Exception ignored){return false;}
    }
}
