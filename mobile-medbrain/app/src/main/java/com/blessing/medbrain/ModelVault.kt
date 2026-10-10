package com.blessing.medbrain

import android.content.Context
import android.net.Uri
import android.os.StatFs
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

data class ModelReceipt(val bytes:Long,val sha256:String)

/** Full local file integrity, rollback on failed import. Never stores weights in GitHub. */
object ModelVault {
    fun file(ctx:Context):File {
        val target=File(ctx.filesDir,"models/brain.gguf")
        if(!target.exists()){
            for(name in listOf("brain.previous","model-download.previous")){
                val backup=File(target.parentFile,name)
                val good=try{
                    backup.isFile&&backup.length()>10_000_000L&&
                    backup.inputStream().use{input->
                        val header=ByteArray(4)
                        input.read(header)==4&&String(header,Charsets.US_ASCII)=="GGUF"
                    }
                }catch(_:Exception){false}
                if(good && backup.renameTo(target))break
            }
        }
        return target
    }
    suspend fun import(ctx:Context,uri:Uri,onProgress:((Long,Long)->Unit)?=null):ModelReceipt=withContext(Dispatchers.IO) {
        val target=file(ctx)
        target.parentFile?.mkdirs()
        val part=File(target.parentFile,"brain.partial")
        val backup=File(target.parentFile,"brain.previous")
        val available=StatFs(target.parentFile!!.absolutePath).availableBytes
        val sourceSize=try {ctx.contentResolver.openAssetFileDescriptor(uri,"r")?.use{it.length}?:-1L} catch(_:Exception){-1L}
        require(sourceSize<0 || sourceSize+500_000_000L<available){"Espace insuffisant (réserve minimale 500 Mo)."}
        val digest=MessageDigest.getInstance("SHA-256")
        var length=0L
        try {
            ctx.contentResolver.openInputStream(uri).use {source->
                requireNotNull(source){"Impossible de lire le modèle"}
                part.outputStream().buffered().use {dest->
                    val buffer=ByteArray(65536)
                    while(true){
                        val n=source.read(buffer)
                        if(n<0)break
                        length+=n
                        require(length<4_000_000_000L){"Modèle >4 Go refusé"}
                        digest.update(buffer,0,n)
                        dest.write(buffer,0,n)
                        if(onProgress!=null && (length % (32L*1024L*1024L)) < n) {
                            withContext(Dispatchers.Main.immediate){onProgress(length,sourceSize)}
                        }
                    }
                }
            }
            require(length>10_000_000L){"Fichier trop petit pour un modèle GGUF"}
            part.inputStream().use {
                val magic=ByteArray(4);require(it.read(magic)==4 && String(magic,Charsets.US_ASCII)=="GGUF"){
                    "Ce fichier n'est pas un GGUF valide"
                }
            }
            if(backup.exists())backup.delete()
            if(target.exists())check(target.renameTo(backup)){"Impossible de sauvegarder l'ancien modèle"}
            try{check(part.renameTo(target)){"Impossible de finaliser le modèle"}}
            catch(e:Throwable){backup.renameTo(target);throw e}
            backup.delete()
            withContext(Dispatchers.Main.immediate){onProgress?.invoke(length,sourceSize)}
            val hash=digest.digest().joinToString(""){"%02x".format(it)}
            ctx.getSharedPreferences("medbrain",Context.MODE_PRIVATE).edit()
                .putString("model_sha256",hash).putLong("model_size",length).apply()
            ModelReceipt(length,hash)
        } finally {if(part.exists())part.delete()}
    }
    fun status(ctx:Context):String {
        val f=file(ctx)
        if(!f.exists())return "Aucun GGUF importé"
        val p=ctx.getSharedPreferences("medbrain",Context.MODE_PRIVATE)
        return "GGUF • ${f.length()/1048576} Mio • SHA-256 ${p.getString("model_sha256","non vérifié")?.take(16)}…"
    }
}
