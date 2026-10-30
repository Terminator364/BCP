package com.blessing.rescuebridge;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.util.Base64;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Locale;
import org.json.JSONObject;

/**
 * Android SAF -> Windows, per-phone authenticated, resumed streamed uploads.
 * No whole-file buffering, fixed 64 KiB RAM chunk, no total file-size cap.
 * Never activates an owner profile or bypasses Windows permissions.
 */
public final class BCPG4FileUploader {
    private static final int CHUNK=65536;
    private static final String PREF="bcp_g4_file_upload_resume";
    private static final String KEY="pending";
    private BCPG4FileUploader(){}

    public interface Progress {
        void onProgress(long sent,long total);
    }
    private static final class Fingerprint {
        final long size;
        final String sha;
        Fingerprint(long size,String sha){this.size=size;this.sha=sha;}
    }
    private static String hex(byte[] data){
        StringBuilder out=new StringBuilder(data.length*2);
        for(byte v:data)out.append(String.format(Locale.ROOT,"%02x",v&255));
        return out.toString();
    }
    private static InputStream open(Context ctx,Uri source) throws Exception {
        InputStream in=ctx.getContentResolver().openInputStream(source);
        if(in==null)throw new IOException("SOURCE_NOT_READABLE");
        return in;
    }
    private static Fingerprint fingerprint(Context ctx,Uri uri) throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        long count=0;
        byte[] buffer=new byte[CHUNK];
        try(InputStream in=open(ctx,uri)){
            int n;
            while((n=in.read(buffer))!=-1){
                if(n==0)continue;
                md.update(buffer,0,n);
                count+=n;
                if(count<0)throw new IOException("SOURCE_SIZE_OVERFLOW");
            }
        }
        return new Fingerprint(count,hex(md.digest()));
    }
    private static InputStream seekSource(Context ctx,Uri uri,long offset) throws Exception {
        InputStream in=open(ctx,uri);
        try{
            byte[] scratch=new byte[CHUNK];
            long skipped=0;
            while(skipped<offset){
                int n=in.read(scratch,0,(int)Math.min(scratch.length,offset-skipped));
                if(n<0)throw new IOException("SOURCE_TRUNCATED_SINCE_CHECKSUM");
                if(n>0)skipped+=n;
            }
            return in;
        }catch(Exception err){
            try{in.close();}catch(IOException ignored){}
            throw err;
        }
    }
    private static int readChunk(InputStream in,byte[] buffer,int limit) throws IOException {
        int filled=0;
        while(filled<limit){
            int n=in.read(buffer,filled,limit-filled);
            if(n<0)break;
            if(n>0)filled+=n;
        }
        return filled;
    }
    private static void writeCheckpoint(SharedPreferences prefs,JSONObject record){
        if(!prefs.edit().putString(KEY,record.toString()).commit())
            throw new IllegalStateException("UPLOAD_CHECKPOINT_NOT_PERSISTED");
    }
    private static long confirmedOffset(Context ctx,String uploadId,long total) throws Exception {
        JSONObject status=BCPG4DeviceEnrollment.ownerFiles(ctx,"status",
                new JSONObject().put("upload_id",uploadId));
        if(!"RECEIVING".equals(status.getString("state")))
            throw new SecurityException("UPLOAD_NO_LONGER_RECEIVING");
        long offset=status.getLong("offset");
        if(offset<0 || offset>total)
            throw new SecurityException("UPLOAD_OFFSET_OUT_OF_RANGE");
        return offset;
    }

    /**
     * Runs on a background thread. The caller must retain Android SAF read
     * permission for the picked URI, and choose a destination on their own PC.
     * A failed network request leaves an explicit resumable record rather than
     * replacing a document or generating a second transfer silently.
     */
    public static JSONObject upload(Context context,Uri source,String destination,
                                    boolean overwrite,String expectedOldSha,
                                    Progress progress) throws Exception {
        Context ctx=context.getApplicationContext();
        if(source==null || destination==null || destination.trim().isEmpty())
            throw new IllegalArgumentException("SOURCE_AND_DESTINATION_REQUIRED");
        if(overwrite && (expectedOldSha==null ||
                         !expectedOldSha.matches("[a-fA-F0-9]{64}")))
            throw new SecurityException("OVERWRITE_REQUIRES_OLD_SHA256");
        Fingerprint fp=fingerprint(ctx,source);
        SharedPreferences prefs=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE);
        String token=prefs.getString(KEY,null);
        String uploadId;
        long offset;
        if(token!=null){
            JSONObject old=new JSONObject(token);
            if(!old.getString("uri").equals(source.toString()) ||
               !old.getString("destination").equals(destination) ||
               old.getBoolean("overwrite")!=overwrite ||
               !old.getString("sha256").equals(fp.sha) ||
               old.getLong("bytes")!=fp.size ||
               !old.optString("old_sha","").equals(expectedOldSha==null?"":expectedOldSha.toLowerCase(Locale.ROOT)))
                throw new SecurityException("DIFFERENT_UPLOAD_PENDING_RESOLVE_FIRST");
            uploadId=old.getString("upload_id");
            if(!uploadId.matches("[0-9a-f]{32}"))
                throw new SecurityException("CORRUPTED_UPLOAD_CHECKPOINT");
            // If the final commit succeeded but the network lost the ACK,
            // complete locally after verifying the server's stored digest.
            JSONObject status=BCPG4DeviceEnrollment.ownerFiles(ctx,"status",
                new JSONObject().put("upload_id",uploadId));
            if(!destination.equals(status.getString("path")))
                throw new SecurityException("RESUMED_DESTINATION_MISMATCH");
            if("COMMITTED".equals(status.getString("state"))){
                if(!fp.sha.equals(status.optString("sha256")) ||
                   status.getLong("bytes")!=fp.size)
                    throw new SecurityException("COMMITTED_DIGEST_MISMATCH");
                if(!prefs.edit().remove(KEY).commit())
                    throw new IllegalStateException("COMMITTED_CHECKPOINT_NOT_CLEARED");
                return new JSONObject().put("status","COMMITTED")
                    .put("path",destination).put("bytes",fp.size).put("sha256",fp.sha);
            }
            if(!"RECEIVING".equals(status.getString("state")))
                throw new SecurityException("UPLOAD_NO_LONGER_RECEIVING");
            offset=status.getLong("offset");
            if(offset<0||offset>fp.size)
                throw new SecurityException("RESUMED_OFFSET_INVALID");
        }else{
            JSONObject request=new JSONObject().put("destination",destination)
                .put("overwrite",overwrite);
            if(overwrite)request.put("expected_old_sha",expectedOldSha.toLowerCase(Locale.ROOT));
            JSONObject started=BCPG4DeviceEnrollment.ownerFiles(ctx,"begin",request);
            uploadId=started.getString("upload_id");
            if(!uploadId.matches("[0-9a-f]{32}") || started.getLong("next_offset")!=0)
                throw new SecurityException("UNTRUSTED_UPLOAD_BEGIN_RESPONSE");
            offset=0;
            writeCheckpoint(prefs,new JSONObject()
                .put("uri",source.toString()).put("destination",destination)
                .put("overwrite",overwrite)
                .put("old_sha",expectedOldSha==null?"":expectedOldSha.toLowerCase(Locale.ROOT))
                .put("sha256",fp.sha).put("bytes",fp.size).put("upload_id",uploadId));
        }
        int failures=0;
        byte[] buffer=new byte[CHUNK];
        if(progress!=null)progress.onProgress(offset,fp.size);
        // Keep one stream open during healthy transfers. Re-open and seek
        // only after an actual network failure: O(n) rather than O(n²)
        // source reads, important for multi-gigabyte files and mobile power.
        InputStream current=seekSource(ctx,source,offset);
        try{
            while(offset<fp.size){
                int n=readChunk(current,buffer,(int)Math.min(CHUNK,fp.size-offset));
                if(n<=0)throw new IOException("SOURCE_CHANGED_WHILE_UPLOADING");
                byte[] chunk=Arrays.copyOf(buffer,n);
                String chunkSha=hex(MessageDigest.getInstance("SHA-256").digest(chunk));
                JSONObject args=new JSONObject()
                    .put("upload_id",uploadId).put("offset",offset)
                    .put("data_base64",Base64.encodeToString(chunk,Base64.NO_WRAP))
                    .put("chunk_sha256",chunkSha);
                try{
                    JSONObject ack=BCPG4DeviceEnrollment.ownerFiles(ctx,"append",args);
                    long next=ack.getLong("next_offset");
                    if(next!=offset+n)
                        throw new SecurityException("UPLOAD_ACK_OFFSET_INVALID");
                    offset=next;
                    failures=0;
                    if(progress!=null)progress.onProgress(offset,fp.size);
                }catch(Exception err){
                    failures++;
                    if(failures>3)throw err;
                    // Server may have saved the chunk before losing its reply.
                    // Read authoritative offset and never replay blindly.
                    offset=confirmedOffset(ctx,uploadId,fp.size);
                    current.close();
                    current=seekSource(ctx,source,offset);
                }
            }
        }finally{current.close();}
        JSONObject done=BCPG4DeviceEnrollment.ownerFiles(ctx,"commit",
                new JSONObject().put("upload_id",uploadId).put("sha256",fp.sha));
        if(!"COMMITTED".equals(done.getString("status")) ||
           !fp.sha.equals(done.getString("sha256")) ||
           done.getLong("bytes")!=fp.size)
            throw new SecurityException("UPLOAD_FINAL_ACK_INVALID");
        if(!prefs.edit().remove(KEY).commit())
            throw new IllegalStateException("UPLOAD_DONE_BUT_CHECKPOINT_NOT_CLEARED");
        return done;
    }
}
