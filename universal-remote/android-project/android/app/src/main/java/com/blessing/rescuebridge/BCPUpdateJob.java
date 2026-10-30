package com.blessing.rescuebridge;

import android.app.job.JobParameters;
import android.app.job.JobService;

/** Android system-scheduled unmetered network update check. */
public final class BCPUpdateJob extends JobService {
    @Override public boolean onStartJob(JobParameters params) {
        Thread thread=new Thread(()->{
            try { BCPAutoUpdater.check(getApplicationContext(),false); }
            finally { jobFinished(params,false); }
        },"BCP-Update-Check");
        thread.setDaemon(true);
        thread.start();
        return true;
    }
    @Override public boolean onStopJob(JobParameters params) {
        // JobScheduler will try again at the next scheduled interval.
        return false;
    }
}
