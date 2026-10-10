package com.blessing.medbrain

/** Route dialogue intent before invoking document FTS or the slow local model. */
object DialoguePlanner {
    data class Route(val followUp:Boolean,val hasHistory:Boolean,val searchQuery:String?)
    private val followUpPattern=Regex(
        "^(?:donc|et donc|alors|et alors|puis|ensuite|et apres|apres|continue|continues|poursuis|reprends|la suite|vas y|et la suite|explique encore|developpe|plus de details|parle moi en detail|parles? moi en detail|tu t.es arrete|reviens au point|et les causes|et le traitement)(?:\\b|$)"
    )
    fun isFollowUp(raw:String):Boolean {
        val q=SearchPolicy.normalized(raw).replace(Regex("[^a-z0-9 ]+")," ")
            .replace(Regex("\\s+")," ").trim()
        return q.length<=110 && followUpPattern.containsMatchIn(q)
    }
    fun failedAnswer(text:String):Boolean {
        val t=SearchPolicy.normalized(text)
        return t.contains("moteur local n a pas termine") ||
            t.contains("inference indisponible") ||
            t.contains("modele n a pas fourni de reponse finale") ||
            t.contains("le moteur local a ete interrompu") ||
            t.contains("service neuronal non disponible") ||
            t.contains("aucune reponse produite par le modele")
    }
    fun route(question:String,history:List<KnowledgeStore.ChatMessage>):Route {
        val follow=isFollowUp(question)
        val previous=history.any { it.kind=="assistant"&&!failedAnswer(it.body) }
        return Route(follow,previous,if(follow)null else question)
    }
    fun prompt(question:String,history:List<KnowledgeStore.ChatMessage>,
               evidence:List<Passage>,mode:String):String {
        val route=route(question,history)
        val prior=history.asReversed()
        val assistant=prior.firstOrNull {
            it.kind=="assistant"&&!failedAnswer(it.body)&&
                ModelOutputPolicy.clean(it.body)!=ModelOutputPolicy.NO_FINAL
        }?.body.orEmpty()
        val topic=prior.firstOrNull {
            it.kind=="user"&&!isFollowUp(it.body)&&
                SearchPolicy.terms(it.body).isNotEmpty()
        }?.body.orEmpty()
        if(route.followUp){
            return ("Conversation suivie. Ne cherche pas un nouveau sujet documentaire.\n"+
                "Question antérieure : "+topic.take(170)+"\n"+
                "Dernière réponse utile (fin) : "+assistant.takeLast(650)+"\n"+
                "Demande actuelle : "+question.take(175)+"\n"+
                "Reprends exactement le fil. Si le contexte manque, dis-le. Ne répète pas les points précédents. Français, réponse directe. /no_think"
            ).take(1350)
        }
        val sources=if(mode=="general")"" else evidence.take(2).joinToString("\n") {
            "["+it.title.take(72)+", p. "+it.page+"] "+
                it.text.replace(Regex("\\s+")," ").take(330)
        }
        return (("Question: "+question.take(260)+"\n")+
            if(sources.isBlank())
                "Aucune source documentaire pertinente vérifiée. Réponds sans inventer de citation."
            else "Extraits retrouvés (ne cite que ces pages):\n"+sources+
                "\nAppuie-toi uniquement sur ces extraits pour attribuer des affirmations aux livres."
            ).take(1250)+"\nRéponds directement en français sans réflexion interne. /no_think"
    }
    fun fallback(evidence:List<Passage>,followUp:Boolean):String {
        if(evidence.isNotEmpty()&&!followUp) {
            val refs=evidence.take(2).joinToString("\n\n") {
                "• "+it.text.replace(Regex("\\s+")," ").take(330).trim()+
                    " — "+it.title+", p. "+it.page
            }
            return "Le modèle neuronal n'est pas disponible maintenant. Voici des passages réellement indexés, sans synthèse inventée :\n\n"+refs
        }
        return if(followUp)
            "Je n'ai pas réussi à produire la suite avec le modèle local. Le fil de discussion est conservé. Recharge le téléphone avant une nouvelle tentative; je n'attribue pas de sources hors sujet à ta relance."
        else
            "Le moteur neuronal n'a pas répondu à temps. La conversation et les livres sont conservés. Recharge le téléphone et réessaie; aucune réponse médicale non vérifiée n'a été inventée."
    }
}
