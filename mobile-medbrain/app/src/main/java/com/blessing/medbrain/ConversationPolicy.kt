package com.blessing.medbrain

/** Fast, bounded routing before any model call. Clinical red flags never get buried behind retrieval. */
object ConversationPolicy {
    /**
     * Urgent personal symptom ≠ mention of a pathology in an academic question.
     * Preserve immediate first-aid replies for actual red flags.
     */
    fun isUrgent(question:String):Boolean{
        val q=SearchPolicy.normalized(question).replace(Regex("[^a-z0-9 ]+")," ")
            .replace(Regex("\\s+")," ").trim()
        if(q.isBlank())return false
        val personalDanger=listOf(
            "je saigne","je perds connaissance","je ne respire",
            "je suffoque","j etouffe","j ai du mal a respirer",
            "mon frere saigne","ma soeur saigne","mon enfant saigne",
            "ma mere saigne","mon pere saigne","mon ami saigne",
            "je suis en train de faire un avc","je crois faire un avc")
            .any{q.contains(it)}
        if(personalDanger)return true
        // Explicit real-person symptoms must never wait for GGUF inference.
        val realPerson=Regex("\\b(je|j ai|ma mere|mon pere|ma soeur|mon frere|mon enfant|mon ami|ma femme|mon mari)\\b")
            .containsMatchIn(q)
        val acute=Regex("\\b(douleur thoracique|hemorragie|convulse|convulsion|ne respire|ne repond plus|paralyse|paralysie|un cote du corps|saignement abondant)\\b")
            .containsMatchIn(q)
        if(realPerson&&acute)return true
        val lessonMarkers=Regex(
            "\\b(cours|fiche|revision|reviser|examens?|examen de medecine|devoir|"+
            "definition|definis|explique|physiopathologie|etiologie|"+
            "cas clinique|hypothetique|simulation|simule|theorique|"+
            "diagnostic differentiel|quelles? sont|quelle est|"+
            "parle moi|conduite a tenir|en stage)\\b")
        if(lessonMarkers.containsMatchIn(q))return false
        val clearAcute=listOf(
            "douleur thoracique intense","saignement abondant",
            "ne respire plus","perd connaissance","difficulte severe a respirer")
            .any{q.contains(it)}
        if(clearAcute)return true
        val now=Regex(
            "\\b(maintenant|en ce moment|tout de suite|actuellement|"+
            "devant moi|a l instant|vient de|urgence reelle)\\b"
        ).containsMatchIn(q)
        val critical=listOf(
            "hemorragie","saignement","saigne","avc",
            "empoisonnement","detresse respiratoire","douleur thoracique")
            .any{q.contains(it)}
        return now&&critical
    }
    fun isGreeting(question:String):Boolean {
        val clean=SearchPolicy.normalized(question).trim().replace(Regex("[!?.,;:]+"),"").trim()
        return Regex("^(bonjour|salut|hello|coucou|bonsoir|hey|eo)(\\s+(medbrain|ia|mon ami|bonjour|a toi|comment vas tu))?$").matches(clean)
    }
    fun isModelQuestion(question:String):Boolean {
        val clean=SearchPolicy.normalized(question).replace(Regex("[-_]+")," ")
        return clean.contains("quel modele")||clean.contains("comment tu fonctionnes")||
            clean.contains("tu sais faire quoi")||clean.contains("que peux tu faire")||
            Regex("\\b(tu es|t es|es tu) (quelle|quel) version\\b").containsMatchIn(clean)||
            clean.contains("ta version")||clean.contains("version de medbrain")||
            Regex("^(quel|quelle) version[?!., ]*$").matches(clean)||
            clean.contains("quel est ton modele")
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