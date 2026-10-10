package com.blessing.medbrain

/** Route dialogue intent before invoking document FTS or the slow local model. */
object DialoguePlanner {
    data class Route(val followUp:Boolean,val hasHistory:Boolean,val searchQuery:String?)
    private val followUpPattern=Regex(
        "^(?:donc|et donc|alors|et alors|puis|ensuite|et apres|apres|continue|continues|poursuis|reprends|la suite|vas y|et la suite|explique encore|developpe|plus de details|parle moi en detail|parles? moi en detail|tu t.es arrete|reviens au point|et les causes|et le traitement)(?:\\b|$)"
    )
    private val genericClinicalFacets=setOf(
        "signe","signes","symptome","symptomes","cause","causes","diagnostic",
        "traitement","traitements","examen","examens","prise","charge",
        "complication","complications","pronostic","physiopathologie","mecanisme",
        "mecanismes","formes","stade","stades","etapes","point","points",
        "surveillance","details","detail","suite","risques","consequences",
        "parle","precise","preciser","explique","decris","developpe",
        "role","choix","quand","facteur","facteurs","risque")
    private val referential=setOf(
        "son","sa","ses","leur","leurs","celui","celle","ceux","celles",
        "ce","cet","cette","ces","cela","ca","ceci","lui","elle","elles",
        "ils","eux","elles","les","en","y")
    private val sentenceOpeners=Regex(
        "^(?:et |mais |alors |ensuite |maintenant )?(?:quel|quels|quelle|quelles|comment|pourquoi|peux|peut|explique|decris|precise|et |dis |les )"
    )
    /**
     * Interpret references to the ACTIVE conversation. This is a small open grammar,
     * not a table of canned medical responses; explicit topics win over ellipses.
     */
    fun isFollowUp(raw:String):Boolean {
        val q=SearchPolicy.normalized(raw).replace(Regex("[^a-z0-9 ]+")," ")
            .replace(Regex("\\s+")," ").trim()
        if(q.isBlank()||q.length>180)return false
        if(q.startsWith("et chez ")||q.startsWith("et pour ")||
            q.startsWith("qu en est il chez "))return true
        val words=q.split(" ")
        val concepts=SearchPolicy.terms(q).filterNot{it in genericClinicalFacets}
        val deictic=words.any{it in referential}
        val explicit=concepts.isNotEmpty() &&
            Regex("\\b(?:de|du|des|pour|chez|sur) (?:la |le |les |l )?[a-z]{4,}").containsMatchIn(q) &&
            !Regex("\\b(?:de|du|des) (?:ce|cet|cette|ces|son|sa|ses|leur|leurs)\\b").containsMatchIn(q)
        if(explicit && (followUpPattern.containsMatchIn(q)||sentenceOpeners.containsMatchIn(q)))
            return false
        if(followUpPattern.containsMatchIn(q))return true
        if(words.size>25)return false
        if(deictic && concepts.size<=1 && sentenceOpeners.containsMatchIn(q))return true
        val pureFacet=SearchPolicy.terms(q).isNotEmpty() && concepts.isEmpty()
        return pureFacet && sentenceOpeners.containsMatchIn(q)
    }
    fun failedAnswer(text:String):Boolean {
        val t=SearchPolicy.normalized(text).replace(Regex("[^a-z0-9 ]+")," ")
            .replace(Regex("\\s+")," ").trim()
        return t.contains("moteur local n a pas termine") ||
            t.contains("inference indisponible") ||
            t.contains("modele n a pas fourni de reponse finale") ||
            t.contains("le moteur local a ete interrompu") ||
            t.contains("service neuronal non disponible") ||
            t.contains("aucune reponse produite par le modele") ||
            t.contains("je n ai pas reussi a produire la suite") ||
            t.contains("le moteur neuronal n est pas disponible") ||
            t.contains("batterie faible")
    }
    fun route(question:String,history:List<KnowledgeStore.ChatMessage>):Route {
        val follow=isFollowUp(question)
        val previous=history.any { it.kind=="assistant"&&!failedAnswer(it.body) }
        return Route(follow,previous,if(follow)null else question)
    }
    fun prompt(question:String,history:List<KnowledgeStore.ChatMessage>,
               evidence:List<Passage>,mode:String,
               curated:List<CardioCurriculum.Fiche> = emptyList()):String {
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
        val pdf=if(mode=="general")emptyList() else
            evidence.take(if(curated.isEmpty())2 else 1).map{
                "["+it.title.take(72)+", p. "+it.page+"] "+
                it.text.replace(Regex("\\s+")," ").take(330)
            }
        val curatedRefs=if(mode=="general")emptyList() else curated.take(1).map{f->
            "[MedRebuild · Google Docs · Tome "+f.tome+" · "+f.title.take(60)+
                " · repère : "+f.sourceLocator.take(70)+"] "+
                CardioCurriculum.excerpt(f,question,345)
        }
        val sources=(curatedRefs+pdf).joinToString("\n")
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
