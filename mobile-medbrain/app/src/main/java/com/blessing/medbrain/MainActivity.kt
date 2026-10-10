package com.blessing.medbrain

import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import dev.ffmpegkit.llama.Llama
import dev.ffmpegkit.llama.LlamaConfig
import dev.ffmpegkit.llama.LlamaModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

class MainActivity : ComponentActivity() {
    private lateinit var stats: TextView
    private lateinit var answer: TextView
    private lateinit var question: EditText
    private var model: LlamaModel? = null
    private var busy = false

    private val importDocument = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if(uri != null) {
            try {
                contentResolver.takePersistableUriPermission(uri, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (_: SecurityException) { }
            val name = displayName(uri)
            val id = sha256(uri.toString())
            KnowledgeStore(this).use { store -> store.register(id, name, uri.toString()) }
            val input = Data.Builder().putString("uri",uri.toString()).putString("id",id).build()
            val request = OneTimeWorkRequestBuilder<IngestWorker>().setInputData(input).build()
            WorkManager.getInstance(this).enqueueUniqueWork("learn-$id",ExistingWorkPolicy.KEEP,request)
            answer.text = "Import lancé : $name. Lecture par lots, avec reprise. Appuie sur « État » pour suivre."
            refresh()
        }
    }
    private val importModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if(uri != null && displayName(uri).lowercase().endsWith(".gguf")) {
            launchBusy("Import GGUF…") {
                val target = File(filesDir,"models/model.gguf")
                val temp = File(filesDir,"models/model.part")
                withContext(Dispatchers.IO) {
                    temp.parentFile?.mkdirs()
                    try {
                        contentResolver.openInputStream(uri).use { input ->
                            requireNotNull(input)
                            temp.outputStream().use { output -> input.copyTo(output,65536) }
                        }
                        require(temp.length() in 1000L..4_000_000_000L) { "Poids GGUF invalides ou >4 Go" }
                        if(target.exists()) target.delete()
                        check(temp.renameTo(target)) { "Impossible de finaliser le modèle" }
                    } catch (t: Throwable) { temp.delete(); throw t }
                }
                "Modèle GGUF importé : ${target.length()/1024/1024} Mio. Stocké uniquement sur cet appareil."
            }
        } else if (uri != null) answer.text = "Choisis un fichier .gguf valide."
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation=LinearLayout.VERTICAL
            setPadding(28,38,28,32)
        }
        fun label(t:String,size:Float=16f) = TextView(this).apply {
            text=t; textSize=size; setTextColor(0xff132B43.toInt()); setPadding(0,7,0,9)
        }
        fun action(t:String,perform:()->Unit) {
            root.addView(Button(this).apply { text=t; isAllCaps=false; setOnClickListener { perform() } })
        }
        root.addView(label("MEDBRAIN  ·  apprentissage local",23f))
        root.addView(label("Prototype alpha • aucune donnée envoyée à un serveur"))
        stats=label("");root.addView(stats)
        action("Importer un PDF ou texte (Drive / téléphone)") {
            importDocument.launch(arrayOf("application/pdf","text/plain","text/markdown"))
        }
        action("Charger mon modèle GGUF local") { importModel.launch(arrayOf("*/*")) }
        action("État de l'apprentissage") { refresh() }
        question=EditText(this).apply {
            hint="Question sur ta bibliothèque médicale"
            minLines=2;maxLines=5
        }
        root.addView(question)
        action("Questionner le cerveau local") { ask() }
        answer=label("Choisis un document, puis un modèle GGUF pour obtenir une réponse générée et sourcée.",15f)
        answer.setTextIsSelectable(true)
        root.addView(answer)
        val sc=ScrollView(this)
        sc.addView(root,ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT))
        setContentView(sc)
        refresh()
    }
    private fun displayName(uri:Uri): String {
        contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use {
            if(it.moveToFirst()) return it.getString(0) ?: "document"
        }
        return "document"
    }
    private fun refresh() {
        KnowledgeStore(this).use { store ->
            stats.text = store.counts()+"\n"+store.progress()
        }
    }
    private fun sha256(s:String):String = MessageDigest.getInstance("SHA-256")
        .digest(s.toByteArray(Charsets.UTF_8)).joinToString(""){"%02x".format(it)}
    private fun launchBusy(label:String, run:suspend ()->String) {
        if(busy) return
        busy=true;answer.text=label
        lifecycleScope.launch {
            try { answer.text=run() }
            catch(t:Throwable) { answer.text="Échec : ${t.message ?: t.javaClass.simpleName}" }
            finally { busy=false;refresh() }
        }
    }
    private fun ask() {
        val q=question.text.toString().trim()
        if(q.isEmpty()) { answer.text="Entre une question.";return }
        launchBusy("Recherche des sources et inférence locale…") {
            val sources = withContext(Dispatchers.IO) {
                KnowledgeStore(this@MainActivity).use { it.passages(q) }
            }
            if(sources.isEmpty()) return@launchBusy "Aucune source indexée pertinente. Importe d'abord un document et vérifie son état."
            val modelFile=File(filesDir,"models/model.gguf")
            if (!modelFile.exists()) return@launchBusy "Sources retrouvées :\n$sources\n\nPour une synthèse neuronale, charge ton GGUF."
            val llm=model ?: Llama.loadModel(modelFile.absolutePath,
                LlamaConfig(contextSize=2048,threads=4,gpuLayers=0,temperature=0.2f)).also { model=it }
            val response=Llama.complete(llm,
                prompt="QUESTION:\n$q\n\nEXTRAITS DE LA BIBLIOTHÈQUE:\n$sources",
                systemPrompt="Tu es un assistant d'étude médicale. Réponds en français uniquement à partir des extraits fournis, cite titre et numéro de page, distingue preuve et inférence. Si les extraits sont insuffisants, dis-le. Ne prétends jamais être un dispositif médical ni fournir une recommandation clinique individuelle.",
                maxTokens=400)
            "${response.text.trim()}\n\nSources consultées :\n$sources\n\nVitesse : ${"%.1f".format(response.tokensPerSecond)} tok/s"
        }
    }
    override fun onDestroy() {
        model?.let { Llama.releaseModel(it) }
        model=null
        super.onDestroy()
    }
}
