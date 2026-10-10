package com.blessing.medbrain

/** Evidence-first study material, no invented claims when a local LLM is absent. */
object StudyEngine {
    fun references(passages:List<Passage>)=passages.take(4).joinToString("\n\n"){"[${it.citation()}]\n${it.text.take(850)}"}
    /** Useful offline-first output while slow neural synthesis is pending. */
    fun quickEvidence(topic:String,passages:List<Passage>):String{
        if(passages.isEmpty())return "Aucun passage indexé suffisamment pertinent pour cette notion."
        return "📖 Références immédiatement disponibles — "+topic+"\n"+
            passages.take(4).mapIndexed{index,p->
                val excerpt=p.text.replace(Regex("\\s+")," ").take(460).trim()
                "\n"+(index+1)+". "+p.title+" · p. "+p.page+" ("+p.method+")\n"+excerpt
            }.joinToString("\n")
    }
    fun summaryPrompt(topic:String,passages:List<Passage>):String =
        "Thème : $topic\n\nSources vérifiées (ne pas inventer de page) :\n"+references(passages)+
        "\n\nRédige une fiche médicale structurée en français (définition, mécanismes, clinique, diagnostic, prise en charge selon les sources), signale explicitement les informations manquantes."
    fun examPrompt(topic:String,passages:List<Passage>):String =
        "Thème : $topic\n\nSources :\n"+references(passages)+
        "\n\nPose 5 questions ouvertes progressives et donne un corrigé séparé, appuyé exclusivement sur les passages. Pas de recommandations cliniques individuelles."
    fun correctionPrompt(question:String,response:String,passages:List<Passage>):String =
        "Question : $question\nRéponse de l'étudiant : $response\nDocuments :\n"+references(passages)+
        "\n\nCorrige point par point. Donne les éléments exacts, les omissions, les erreurs, les limites des documents. Cite les sources. N'attribue pas de score numérique s'il manque un barème."
}
