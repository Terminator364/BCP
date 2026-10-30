package com.blessing.rescuebridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;

/** System install result; no arbitrary network or command execution. */
public final class BCPUpdateReceiver extends BroadcastReceiver {
    public static volatile android.app.Activity foreground;
    @Override public void onReceive(Context ctx,Intent intent) {
        if(intent==null || !"com.blessing.rescuebridge.BCP_UPDATE_RESULT".equals(intent.getAction()))return;
        int status=intent.getIntExtra(PackageInstaller.EXTRA_STATUS,PackageInstaller.STATUS_FAILURE);
        if(status==PackageInstaller.STATUS_SUCCESS) {
            BCPAutoUpdater.setStatus(ctx,"Mise à jour installée.");
            BCPAutoUpdater.prefs(ctx).edit().remove("pending_version").remove("pending_sha256").apply();
        } else if(status==PackageInstaller.STATUS_PENDING_USER_ACTION) {
            // Handle the system confirmation only while the app is foregrounded.
            Intent systemConfirm=intent.getParcelableExtra(Intent.EXTRA_INTENT);
            android.app.Activity visible=foreground;
            if(visible!=null && systemConfirm!=null){
                visible.runOnUiThread(()->{
                    try{visible.startActivity(systemConfirm);}
                    catch(Exception ex){BCPAutoUpdater.setStatus(ctx,"Confirmation Android requise dans BCP.");}
                });
            }else{
                BCPAutoUpdater.setStatus(ctx,"Android demande une confirmation : ouvre BCP et appuie sur Installer.");
            }
        } else {
            BCPAutoUpdater.setStatus(ctx,"Installation refusée par Android (code "+status+").");
        }
    }
}
