package com.blessing.medbrain

/** Original MedRebuild teaching evidence, not neural reasoning or automated grading. */
object CardioPractice {
    fun match(id:String?,topic:String,fiches:List<CardioCurriculum.Fiche>):CardioCurriculum.Fiche?{
        if(id.isNullOrBlank()||topic.isBlank())return null
        val exact=SearchPolicy.normalized(topic.trim())
        return fiches.firstOrNull{it.id==id && SearchPolicy.normalized(it.title.trim())==exact}
    }
    fun source(f:CardioCurriculum.Fiche):String =
        "MedRebuild cardiologie Tome "+f.tome+"\nFiche : "+f.title+
        "\nDocument : "+f.sourceTitle+"\nRepère : "+f.sourceLocator+
        "\nSource Google Docs : pas de fausse page PDF."
    fun questions(f:CardioCurriculum.Fiche):String =
        "Rappel actif : "+f.title+"\nQuestions issues de la fiche originale :\n\n"+
        f.recall.mapIndexed{i,s->(i+1).toString()+". "+s}.joinToString("\n\n")+
        "\n\nRéponds avant de consulter le corrigé original."
    fun comparison(f:CardioCurriculum.Fiche,answer:String):String{
        if(answer.isBlank())return "Écris une réponse avant la comparaison."
        return "Comparaison documentaire : "+f.title+"\nTa réponse :\n"+
            answer.take(2500)+"\n\nRepères du cours original :\n"+
            f.essential.take(8).joinToString("\n"){"• "+it}+
            "\n\nCeci est une grille de comparaison, pas une correction automatique ni une note clinique."
    }
}
