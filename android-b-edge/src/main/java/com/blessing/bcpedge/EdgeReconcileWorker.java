package com.blessing.bcpedge;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.work.*;

public final class EdgeReconcileWorker extends Worker {
    public static final String UNIQUE_NAME="bcp-edge-reconcile";
    public EdgeReconcileWorker(@NonNull Context context,@NonNull WorkerParameters params){super(context,params);}

    @NonNull @Override public Result doWork(){
        try{
            BcpClient c=new BcpClient(getApplicationContext());
            c.syncOrchestrationState();
            return Result.success();
        }catch(Exception ex){
            return Result.retry();
        }
    }

    public static void schedule(Context context){
        Constraints constraints=new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build();
        PeriodicWorkRequest periodic=new PeriodicWorkRequest.Builder(EdgeReconcileWorker.class,15,java.util.concurrent.TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build();
        WorkManager.getInstance(context.getApplicationContext()).enqueueUniquePeriodicWork(
            UNIQUE_NAME, ExistingPeriodicWorkPolicy.KEEP, periodic);
    }

    public static void requestNow(Context context){
        OneTimeWorkRequest now=new OneTimeWorkRequest.Builder(EdgeReconcileWorker.class)
            .setConstraints(new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build();
        WorkManager.getInstance(context.getApplicationContext()).enqueueUniqueWork(
            UNIQUE_NAME+"-now",ExistingWorkPolicy.REPLACE,now);
    }
}
