package com.blessing.rescuebridge;

import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.os.Build;

import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * BCP self-update V1: Wi-Fi/unmetered only, signed APK verified before install.
 * Can request no-user-action self-update on Android 12+, but system may still prompt.
 * No third-party update services, no mobile data, no device owner privileges.
 */
public final class BCPAutoUpdater {
    public static final String PREFS="bcp_internal_updates_v1";
    public static final String BASE="https://mbmpc.taild48ba2.ts.net";
    private static final String MANIFEST=BASE+"/updates/stable.json";
    private static final int JOB_ID=0x42435021;
    private static final long INTERVAL=24L*60*60*1000;
    private static final long FOREGROUND_INTERVAL=4L*60*60*1000;
    private static final long MAX_APK=30L*1024*1024;
    private static final ExecutorService POOL=Executors.newSingleThreadExecutor();
    private BCPAutoUpdater(){}

    static SharedPreferences prefs(Context ctx) {
        return ctx.getApplicationContext().getSharedPreferences(PREFS,Context.MODE_PRIVATE);
    }
    public static String status(Context ctx) {
        return prefs(ctx).getString("status","Système de mise à jour prêt.");
    }
    static void setStatus(Context ctx,String s) {
        prefs(ctx).edit().putString("status",s).putLong("status_at",System.currentTimeMillis()).apply();
    }
    public static void schedule(Context ctx){
        try {
            JobScheduler js=(JobScheduler)ctx.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if(js==null) return;
            // Avoid replacing an existing schedule each time the app opens.
            if(js.getPendingJob(JOB_ID)!=null) return;
            JobInfo info=new JobInfo.Builder(JOB_ID,new ComponentName(ctx,BCPUpdateJob.class))
                .setPeriodic(INTERVAL,INTERVAL/4)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                .setPersisted(true).build();
            if(js.schedule(info)!=JobScheduler.RESULT_SUCCESS) setStatus(ctx,"Planification différée.");
        }catch(Exception ex){setStatus(ctx,"Planification indisponible.");}
    }
    public static void checkForeground(Context ctx) {
        long last=prefs(ctx).getLong("last_check",0);
        if(System.currentTimeMillis()-last<FOREGROUND_INTERVAL)return;
        POOL.execute(()->check(ctx.getApplicationContext(),false));
    }
    public static void checkManually(Context ctx){
        POOL.execute(()->check(ctx.getApplicationContext(),true));
    }
    static boolean unmetered(Context ctx){
        ConnectivityManager cm=(ConnectivityManager)ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
        return cm!=null && cm.getActiveNetwork()!=null && !cm.isActiveNetworkMetered();
    }
    private static byte[] readBounded(InputStream in,int max) throws Exception {
        ByteArrayOutputStream buf=new ByteArrayOutputStream();
        byte[] tmp=new byte[8192];int n;
        while((n=in.read(tmp))>=0){
            if(buf.size()+n>max) throw new IOException("Mise à jour trop volumineuse");
            buf.write(tmp,0,n);
        }
        return buf.toByteArray();
    }
    private static HttpURLConnection connection(String address) throws Exception{
        if(!address.startsWith(BASE+"/"))throw new SecurityException("Serveur de mise à jour non reconnu");
        HttpURLConnection c=(HttpURLConnection)new URL(address).openConnection();
        c.setConnectTimeout(7000);c.setReadTimeout(16000);
        c.setUseCaches(false);c.setRequestProperty("Cache-Control","no-cache");
        c.setInstanceFollowRedirects(false);
        return c;
    }
    private static String sha256(File f) throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(f)){
            byte[] b=new byte[16384];int n;
            while((n=in.read(b))!=-1)md.update(b,0,n);
        }
        StringBuilder out=new StringBuilder();
        for(byte b:md.digest())out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        return out.toString();
    }
    private static long currentCode(Context ctx) throws Exception{
        PackageInfo self=ctx.getPackageManager().getPackageInfo(ctx.getPackageName(),0);
        return Build.VERSION.SDK_INT>=28?self.getLongVersionCode():self.versionCode;
    }
    private static boolean sameSigner(Context ctx,File apk) throws Exception {
        PackageManager pm=ctx.getPackageManager();
        PackageInfo old, incoming;
        if(Build.VERSION.SDK_INT>=28){
            old=pm.getPackageInfo(ctx.getPackageName(),PackageManager.GET_SIGNING_CERTIFICATES);
            incoming=pm.getPackageArchiveInfo(apk.getAbsolutePath(),PackageManager.GET_SIGNING_CERTIFICATES);
            if(old==null||incoming==null||old.signingInfo==null||incoming.signingInfo==null)return false;
            return sameSignatureSet(old.signingInfo.getApkContentsSigners(),
                                    incoming.signingInfo.getApkContentsSigners());
        }
        old=pm.getPackageInfo(ctx.getPackageName(),PackageManager.GET_SIGNATURES);
        incoming=pm.getPackageArchiveInfo(apk.getAbsolutePath(),PackageManager.GET_SIGNATURES);
        return old!=null && incoming!=null && sameSignatureSet(old.signatures,incoming.signatures);
    }
    private static boolean sameSignatureSet(android.content.pm.Signature[] a,
                                            android.content.pm.Signature[] b) throws Exception {
        if(a==null||b==null||a.length==0||a.length!=b.length)return false;
        byte[][] aa=new byte[a.length][],bb=new byte[b.length][];
        for(int i=0;i<a.length;i++)aa[i]=MessageDigest.getInstance("SHA-256").digest(a[i].toByteArray());
        for(int i=0;i<b.length;i++)bb[i]=MessageDigest.getInstance("SHA-256").digest(b[i].toByteArray());
        for(byte[] expected:aa){
            boolean found=false;
            for(byte[] given:bb) if(MessageDigest.isEqual(expected,given)){found=true;break;}
            if(!found)return false;
        }
        return true;
    }
    /** Called by foreground or periodic network-unmetered Android JobScheduler. */
    public static void check(Context ctx,boolean manual){
        ctx=ctx.getApplicationContext();
        if(!unmetered(ctx)){
            setStatus(ctx,"Réseau limité : aucune mise à jour téléchargée sur forfait mobile.");
            return;
        }
        HttpURLConnection req=null;
        try{
            req=connection(MANIFEST);
            if(req.getResponseCode()!=200)throw new IOException("Manifeste indisponible");
            byte[] bytes;
            try(InputStream stream=req.getInputStream()){bytes=readBounded(stream,8192);}
            JSONObject m=new JSONObject(new String(bytes,java.nio.charset.StandardCharsets.UTF_8));
            long next=m.getLong("versionCode"), current=currentCode(ctx);
            if(!ctx.getPackageName().equals(m.getString("package")) ||
               !"stable".equals(m.getString("channel")))throw new SecurityException("Manifeste invalide");
            prefs(ctx).edit().putLong("last_check",System.currentTimeMillis()).apply();
            if(next<=current){setStatus(ctx,"Application à jour · version "+current);return;}
            String url=m.getString("url");
            if(!url.matches("https://mbmpc[.]taild48ba2[.]ts[.]net/updates/stable[.]apk"))
                throw new SecurityException("Adresse APK refusée");
            long size=m.getLong("size");
            String hash=m.getString("sha256").toLowerCase(java.util.Locale.ROOT);
            if(size<20000||size>MAX_APK||!hash.matches("[0-9a-f]{64}"))
                throw new SecurityException("Métadonnées de mise à jour refusées");
            File target=new File(ctx.getFilesDir(),"bcp-update-next.apk");
            File temp=new File(ctx.getFilesDir(),"bcp-update-partial.apk");
            HttpURLConnection download=null;
            try {
                download=connection(url);
                if(download.getResponseCode()!=200)throw new IOException("Téléchargement refusé");
                long total=0;
                try(InputStream in=download.getInputStream();OutputStream out=new FileOutputStream(temp)){
                    byte[] b=new byte[8192];int n;
                    while((n=in.read(b))!=-1){
                        total+=n;
                        if(total>size||total>MAX_APK)throw new IOException("Taille téléchargée incorrecte");
                        out.write(b,0,n);
                    }
                }
                if(total!=size||!hash.equals(sha256(temp)))
                    throw new SecurityException("Empreinte SHA-256 invalide");
                PackageInfo parsed=ctx.getPackageManager().getPackageArchiveInfo(temp.getAbsolutePath(),0);
                if(parsed==null||!ctx.getPackageName().equals(parsed.packageName) ||
                   (Build.VERSION.SDK_INT>=28?parsed.getLongVersionCode():parsed.versionCode)!=next ||
                   !sameSigner(ctx,temp))throw new SecurityException("Identité/signature APK invalide");
                if(target.exists()&&!target.delete())throw new IOException("Impossible de remplacer l'APK temporaire");
                if(!temp.renameTo(target))throw new IOException("Renommage atomique échoué");
            }finally{
                if(download!=null)download.disconnect();
                if(temp.exists())temp.delete();
            }
            prefs(ctx).edit().putLong("pending_version",next).putString("pending_sha256",hash).apply();
            if(Build.VERSION.SDK_INT>=26 && !ctx.getPackageManager().canRequestPackageInstalls()){
                setStatus(ctx,"Mise à jour vérifiée et prête : autorisation Android d'installation nécessaire.");
                return;
            }
            installVerified(ctx,target,next,hash);
        }catch(Exception ex){
            setStatus(ctx,"Mise à jour : "+ex.getClass().getSimpleName());
        }finally{if(req!=null)req.disconnect();}
    }
    public static void installReady(Context ctx){
        ctx=ctx.getApplicationContext();
        File f=new File(ctx.getFilesDir(),"bcp-update-next.apk");
        long code=prefs(ctx).getLong("pending_version",0);
        String digest=prefs(ctx).getString("pending_sha256","");
        if(!f.isFile()||code<=0)return;
        try{
            if(code<=currentCode(ctx)||!digest.equalsIgnoreCase(sha256(f))||!sameSigner(ctx,f))
                throw new SecurityException("Paquet de mise à jour non reconnu");
            if(Build.VERSION.SDK_INT>=26 && !ctx.getPackageManager().canRequestPackageInstalls()){
                setStatus(ctx,"Autorise les mises à jour de BCP dans les réglages Android.");
                return;
            }
            installVerified(ctx,f,code,digest);
        }catch(Exception e){setStatus(ctx,"Installation différée : "+e.getClass().getSimpleName());}
    }
    private static void installVerified(Context ctx,File f,long code,String digest) throws Exception {
        PackageInstaller installer=ctx.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams p=new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        p.setAppPackageName(ctx.getPackageName());
        p.setSize(f.length());
        if(Build.VERSION.SDK_INT>=31)
            p.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        int sessionId=installer.createSession(p);
        boolean committed=false;
        try(PackageInstaller.Session session=installer.openSession(sessionId)){
            try(InputStream in=new FileInputStream(f);
                OutputStream out=session.openWrite("base.apk",0,f.length())){
                byte[] data=new byte[16384];int n;
                while((n=in.read(data))!=-1)out.write(data,0,n);
                session.fsync(out);
            }
            Intent callback=new Intent(ctx,BCPUpdateReceiver.class);
            callback.setAction("com.blessing.rescuebridge.BCP_UPDATE_RESULT");
            callback.putExtra("expectedCode",code);
            int flags=PendingIntent.FLAG_UPDATE_CURRENT;
            if(Build.VERSION.SDK_INT>=31)flags|=PendingIntent.FLAG_MUTABLE;
            PendingIntent pi=PendingIntent.getBroadcast(ctx,sessionId,callback,flags);
            session.commit(pi.getIntentSender());
            committed=true;
            setStatus(ctx,"Installation automatique demandée à Android · version "+code);
        }finally{if(!committed)installer.abandonSession(sessionId);}
    }
}
