package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test

class ConversationPolicySafetyTest{
    @Test fun discussingMedicalPathologyIsNotMistakenForAnActualEmergency(){
        val academic=listOf(
            "Parle-moi de l'hémorragie en détail",
            "Cours sur les hémorragies",
            "Définis l'AVC",
            "Explique les causes d'une hémorragie digestive",
            "Je révise l'AVC",
            "Quels sont les signes d'un AVC ?",
            "Quelle est la prise en charge de l'hémorragie en stage ?",
            "Conduite à tenir devant une hémorragie dans un cas clinique",
            "Parle moi en détail de l'AVC",
            "Quelles sont les complications des anticoagulants ?",
            "Physiopathologie de l'hémorragie massive",
            "Exercice de simulation : urgence hémorragique"
        )
        academic.forEach{assertFalse("Academic question misrouted: "+it,ConversationPolicy.isUrgent(it))}
    }
    @Test fun currentRedFlagsStillReceiveImmediateSafetyGuidance(){
        val dangerous=listOf(
            "Je saigne beaucoup, que faire ?",
            "Je saigne que faire ?",
            "Je ne respire plus",
            "Je perds connaissance",
            "Douleur thoracique intense",
            "Mon ami saigne beaucoup",
            "Quelqu'un présente une hémorragie maintenant",
            "Je crois faire un AVC",
            "Saignement abondant"
        )
        dangerous.forEach{assertTrue("Real emergency missed: "+it,ConversationPolicy.isUrgent(it))}
        assertTrue(ConversationPolicy.firstAid("Je saigne beaucoup").contains("pression directe"))
    }
}
