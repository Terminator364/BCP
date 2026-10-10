package com.blessing.medbrain

/** Fast, bounded routing before any model call. Clinical red flags never get buried behind retrieval. */
object ConversationPolicy {
    fun isUrgent(question:String):Boolean{
        val q=SearchPolicy.normalized(question)
        val dangerous=listOf("je saigne beaucoup","hemorragie","saignement abondant",
            "douleur thoracique intense","je ne respire","difficulte a respirer",
            "je perds connaissance","perte de connaissance","avc","empoisonnement")
        return dangerous.any{q.contains(it)}
    }
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