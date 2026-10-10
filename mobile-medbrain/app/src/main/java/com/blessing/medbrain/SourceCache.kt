package com.blessing.medbrain

import android.content.Context
import android.net.Uri
import android.os.StatFs
import java.io.File
import java.security.MessageDigest

/** Download/import each source once; repeated 4-page batches never redownload a cloud PDF. */
object SourceCache {
    fun getOrFetch(ctx:Context,id:String,source:Uri):File {
        val dir=File(ctx.filesDir,"source-cache")
        dir.mkdirs()
        val final=File(dir,"$id.pdf")
        if(final.isFile && final.length()>100)return final
        val tmp=File(dir,"$id.partial")
        val free=StatFs(dir.absolutePath).availableBytes
        require(free>800_000_000L){"Espace insuffisant, mise en pause pour protéger le téléphone"}
        val maxSize=minOf(650_000_000L,free-500_000_000L)
        try{
            var bytes=0L
            ctx.contentResolver.openInputStream(source).use {input->
                requireNotNull(input){"Source distante indisponible"}
                tmp.outputStream().buffered().use {out->
                    val chunk=ByteArray(65536)
                    while(true){
                        val n=input.read(chunk)
                        if(n<0)break
                        bytes+=n
                        require(bytes<=maxSize){"Livre trop volumineux pour le cache local autorisé"}
                        out.write(chunk,0,n)
                    }
                }
            }
            require(bytes>100L){"Fichier PDF vide"}
            check(tmp.renameTo(final)){"Impossible de mettre le PDF en cache"}
            return final
        }finally{if(tmp.exists())tmp.delete()}
    }
    fun release(ctx:Context,id:String) {
        File(File(ctx.filesDir,"source-cache"),"$id.pdf").delete()
    }
}
