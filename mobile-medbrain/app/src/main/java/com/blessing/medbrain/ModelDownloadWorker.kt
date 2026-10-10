package com.blessing.medbrain

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.StatFs
import androidx.work.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** Opt-in, Wi-Fi-only GGUF installer with SHA256 verification; never downloads silently. */
class ModelDownloadWorker(ctx:Context, params:WorkerParameters):CoroutineWorker(ctx,params) {
    companion object {
        const val SOURCE="https://huggingface.co/Antigma/Qwen3-1.7B-GGUF/resolve/main/qwen3-1.7b-q4_k_m.gguf"
        const val SHA="a7f6720f68f4a4567ebf7e3257041dd0b72077b518efe56890aec3516b59b9de"
    }
    private val channel="medbrain_download_v1"
    private fun info(message:String):ForegroundInfo {
        val manager=applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(channel,"Modèle MedBrain",NotificationManager.IMPORTANCE_LOW))
        val note=Notification.Builder(applicationContext,channel)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("MedBrain — Qwen3 1.7B")
            .setContentText(message).setOngoing(true).build()
        return ForegroundInfo(1097,note,ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }
    override suspend fun doWork():Result=withContext(Dispatchers.IO){
        val target=ModelVault.file(applicationContext)
        val part=File(target.parentFile,"model-download.partial")
        target.parentFile?.mkdirs()
        val available=StatFs(target.parentFile!!.absolutePath).availableBytes
        if(available < 1_850_000_000L){
            return@withContext Result.failure(workDataOf("error" to "Prévoir au moins 1,85 Go d'espace libre pour le téléchargement et la réserve."))
        }
        try{
            setForeground(info("Connexion Wi-Fi, reprise du téléchargement"))
            var offset=if(part.exists())part.length() else 0L
            if(offset>1_800_000_000L){part.delete();offset=0L}
            val connection=URL(SOURCE).openConnection() as HttpURLConnection
            connection.connectTimeout=20000
            connection.readTimeout=45000
            connection.setRequestProperty("User-Agent","MedBrainPersonal/0.4")
            if(offset>0)connection.setRequestProperty("Range","bytes=$offset-")
            connection.instanceFollowRedirects=true
            connection.connect()
            val code=connection.responseCode
            require(code==200||code==206){"Téléchargement indisponible, serveur HTTP $code"}
            val append=code==206&&offset>0
            if(!append){offset=0L;part.delete()}
            val rawTotal=connection.contentLengthLong
            val total=if(rawTotal>0)rawTotal+offset else -1L
            var nextReport=offset
            connection.inputStream.use{input->
                java.io.FileOutputStream(part,append).buffered().use{out->
                    val buffer=ByteArray(65536)
                    var received=offset
                    while(true){
                        if(isStopped)throw InterruptedException("Téléchargement interrompu ; reprise possible")
                        val n=input.read(buffer)
                        if(n<0)break
                        received+=n
                        require(received<=1_800_000_000L){"Réponse trop volumineuse"}
                        out.write(buffer,0,n)
                        if(received>=nextReport){
                            setProgress(workDataOf("copied" to received,"total" to total))
                            if(received% (128L*1024*1024)<65536)setForeground(info("${received/1048576} Mio récupérés"))
                            nextReport=received+16L*1024*1024
                        }
                    }
                }
            }
            connection.disconnect()
            val digest=MessageDigest.getInstance("SHA-256")
            part.inputStream().buffered().use{input->
                val bytes=ByteArray(65536)
                while(true){
                    val n=input.read(bytes)
                    if(n<0)break
                    digest.update(bytes,0,n)
                }
            }
            val hash=digest.digest().joinToString(""){"%02x".format(it)}
            require(hash.equals(SHA,true)){"Empreinte incorrecte : modèle rejeté, aucune installation."}
            val backup=File(target.parentFile,"model-download.previous")
            if(backup.exists())backup.delete()
            if(target.exists())check(target.renameTo(backup)){"Sauvegarde du modèle précédent impossible"}
            try{check(part.renameTo(target)){"Finalisation GGUF impossible"}}
            catch(e:Throwable){backup.renameTo(target);throw e}
            backup.delete()
            applicationContext.getSharedPreferences("medbrain",Context.MODE_PRIVATE).edit()
                .putString("model_sha256",hash).putLong("model_size",target.length()).apply()
            KnowledgeStore(applicationContext).use{it.event("MODEL_DOWNLOADED",hash.take(18))}
            Result.success(workDataOf("sha256" to hash,"bytes" to target.length()))
        }catch(e:Throwable){
            val message=e.javaClass.simpleName+": "+(e.message?:"")
            try{KnowledgeStore(applicationContext).use{it.event("MODEL_DOWNLOAD_ERROR",message.take(200))}}catch(_:Exception){}
            if(e is InterruptedException)return@withContext Result.failure(workDataOf("error" to message.take(180)))
            if(runAttemptCount<2 && (e is java.io.IOException))Result.retry()
            else Result.failure(workDataOf("error" to message.take(180)))
        }
    }
}
