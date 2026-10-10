package com.blessing.medbrain

import android.content.Context
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter

/** Local-only exception receipt persisted across app restart. */
object CrashReporter {
    @Volatile private var ready=false
    fun install(ctx:Context) {
        if(ready)return
        synchronized(this) {
            if(ready)return
            val previous=Thread.getDefaultUncaughtExceptionHandler()
            val path=File(ctx.filesDir,"crash-receipt.log")
            Thread.setDefaultUncaughtExceptionHandler {thread,error->
                try {
                    val stack=StringWriter().also { out ->error.printStackTrace(PrintWriter(out)) }.toString()
                    path.appendText("\n"+System.currentTimeMillis()+" ["
                        +thread.name.take(60)+"] "+stack.take(7000)+"\n")
                    if(path.length()>85000L){
                        val tail=path.readText().takeLast(55000)
                        path.writeText(tail)
                    }
                } catch(_:Throwable) {}
                previous?.uncaughtException(thread,error)
            }
            ready=true
        }
    }
    fun headline(ctx:Context):String {
        val log=summary(ctx)
        if(log.startsWith("Aucun crash"))return "Aucun arrêt inattendu enregistré dans l'application."
        val lines=log.lines()
        val last=lines.lastOrNull { line ->
            line.contains("OutOfMemoryError") || line.contains("FATAL EXCEPTION") ||
            line.contains("Exception:") || line.contains("Error:") 
        }?.trim()
        val main=last?:lines.lastOrNull{it.contains(" [") && it.contains("] ")}?.trim()
        return if(main.isNullOrBlank())"Incident enregistré. Tu peux exporter le journal complet pour analyse."
            else ("Dernier incident détecté : "+main.take(235)+
                "\\nUne reprise et le rapport complet sont disponibles ci-dessous.")
    }
    fun summary(ctx:Context):String {
        return try {
            val f=File(ctx.filesDir,"crash-receipt.log")
            if(!f.exists())"Aucun crash Java enregistré depuis l'installation de cette version."
            else f.readText().takeLast(8500)
        } catch(e:Exception) {"Journal inaccessible : "+e.javaClass.simpleName}
    }
}
