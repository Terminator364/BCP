package com.blessing.medbrain

/**
 * Source-grounded *lexical comparison*, NOT clinical grading.
 * Clinical negation, synonyms and reasoning quality need expert validation.
 */
object EvidenceRubric{
    data class Finding(val criterion:String,val indicative:Boolean,val commonTerms:List<String>)
    private val avoid=setOf(
        "dans","avec","pour","comme","sans","chez","cette","entre","alors",
        "avant","apres","peut","sont","avoir","etre","etant","cest",
        "lequel","laquelle","dont","leur","leurs","ainsi","parce",
        "plus","moins","tout","tous","toute","notamment","cause",
        "effet","selon","niveau","faire","mettre","point","nombre",
        "toujours","quelques","chaque","souvent","aussi")
    private fun terms(source:String):Set<String> =
        SearchPolicy.normalized(source).split(Regex("[^a-z0-9]+"))
            .asSequence().filter{it.length>=5 && it !in avoid}
            .take(80).toSet()
    fun findings(criterionTexts:List<String>,answer:String):List<Finding>{
        val written=terms(answer.take(3500))
        return criterionTexts.take(8).map{criterion->
            val tokens=terms(criterion)
            val matches=tokens.intersect(written)
            // A single generic shared term cannot establish criterion coverage.
            val minTerms=if(tokens.size<=2)tokens.size else
                maxOf(2, kotlin.math.ceil(tokens.size*0.55).toInt())
            Finding(criterion,tokens.isNotEmpty()&&matches.size>=minTerms,
                matches.toList().sorted().take(8))
        }
    }
    fun compare(criterionTexts:List<String>,answer:String):String {
        if(answer.isBlank())return "Rédige une réponse avant de demander une comparaison."
        val checks=findings(criterionTexts,answer)
        val mentioned=checks.filter{it.indicative}
        val unverified=checks.filterNot{it.indicative}
        return buildString {
            append("🔎 Comparaison formative des notions de la fiche\n")
            append("Méthode : rapprochement lexical prudent avec les repères originaux.\n\n")
            if(mentioned.isNotEmpty()){
                append("Notions possiblement évoquées (à vérifier dans le cours) :\n")
                mentioned.forEach{append("◦ ").append(it.criterion).append("\n")}
                append("\n")
            }
            if(unverified.isNotEmpty()){
                append("Notions non repérées clairement dans la formulation :\n")
                unverified.forEach{append("◦ ").append(it.criterion).append("\n")}
                append("\n")
            }
            append("⚠️ Les synonymes, négations et liens physiopathologiques ne sont ")
            append("pas validés automatiquement. Les correspondances ne sont ni des ")
            append("réponses certifiées correctes, ni une note. Vérifie la fiche originale.")
        }
    }
}
