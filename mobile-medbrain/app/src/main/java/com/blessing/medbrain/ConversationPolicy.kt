package com.blessing.medbrain

/** Fast, bounded routing before any model call. Clinical red flags never get buried behind retrieval. */
object ConversationPolicy {
    fun isUrgent(question:String):Boolean{
        val q=SearchPolicy.normalized(question)
        val dangerous=listOf("je saigne beaucoup","je saigne","hemorragie","saignement abondant",
            "douleur thoracique intense","je ne respire","difficulte a respirer",
            "je perds connaissance","perte de connaissance","avc","empoisonnement")
        return dangerous.any{q.contains(it)}
    }
    fun isGreeting(question:String):Boolean {
        val clean=SearchPolicy.normalized(question).trim().replace(Regex("[!?.,;:]+"),"").trim()
        return Regex("^(bonjour|salut|hello|coucou|bonsoir|hey|eo)(\\s+(medbrain|ia|mon ami|bonjour|a toi|comment vas tu))?$").matches(clean)
    }
    fun isModelQuestion(question:String):Boolean {
        val clean=SearchPolicy.normalized(question)
        return clean.contains("quel modele")||clean.contains("comment tu fonctionnes")||
            clean.contains("tu sais faire quoi")||clean.contains("que peux tu faire")
    }
    fun modelExplanation(available:Boolean):String =
        if(available) "Je suis MedBrain, ton assistant local. Je peux discuter, étudier tes références et citer les pages récupérées. Je suis un petit modèle : mes réponses peuvent être inexactes, surtout en médecine."
        else "Je suis MedBrain. J'indexe tes documents et je peux retrouver des passages cités. Pour générer librement du texte, il faut importer ou activer le modèle GGUF dans Paramètres. Je ne prétends pas connaître ce que je n'ai pas lu."
    fun firstAid(question:String):String {
        val q=SearchPolicy.normalized(question)
        return if(q.contains("saign")||q.contains("hemorrag")){
            "⚠️ Un saignement important ou qui ne s'arrête pas peut être une urgence. " +
            "Exerce une pression directe et continue sur la plaie avec un linge propre et demande immédiatement une aide médicale. " +
            "En cas de malaise, sang abondant ou blessure profonde, fais contacter les secours locaux. " +
            "Si tu étudies un cas clinique plutôt qu'une situation réelle, précise-le et je pourrai détailler la conduite à tenir."
        }else {
            "⚠️ Les symptômes décrits peuvent indiquer une urgence. " +
            "Demande immédiatement une évaluation médicale ou contacte les secours locaux. " +
            "Pour un exercice de médecine, précise qu'il s'agit d'un cas simulé pour obtenir une analyse pédagogique."
        }
    }
}