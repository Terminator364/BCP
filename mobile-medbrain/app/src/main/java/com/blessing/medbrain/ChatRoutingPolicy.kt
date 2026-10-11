package com.blessing.medbrain

/** Conversation first: never use book search for purely personal or general dialogue. */
object ChatRoutingPolicy {
    private val academic=Regex(
        "\\b(anatomie|anemie|hemorragie|saignement|avc|cardiaque|coeur|"+
        "poumon|pulmonaire|dyspnee|insuffisance|hypertension|"+
        "tension arterielle|hypotension|tachycardie|ecg|"+
        "pharmacologie|medicament|medicaments|antibiotique|antibiotiques|anticoagulant|anticoagulants|"+
        "biochimie|biologie clinique|hematologie|glycemie|diabete|"+
        "nfs|numeration formule sanguine|ionogramme|hypoglycemie|hyperglycemie|"+
        "thyroide|meningite|pneumonie|tuberculose|bronchiolite|pneumothorax|"+
        "asthme|bronchite|appendicite|peritonite|pancreatite|"+
        "hepatite|renal|renale|rein|syndrome nephrotique|paludisme|"+
        "obstetrique|gynecologie|grossesse|preeclampsie|eclampsie|"+
        "pediatrie|vaccin|tetanus|tetanos|choc septique|sepsis|"+
        "anamnese|auscultation|spirometrie|hemoglobine|"+
        "bilirubine|creatinine|uremie|hypoxemie|hyperkaliemie|"+
        "diagnostic|semiologie|physiopathologie|therapeutique|"+
        "chirurgie|fracture|maladie|maladies|pathologie|pathologies|"+
        "symptome|symptomes|traitement|traitements|cas clinique)\\b")
    private val sourceIntent=Regex(
        "\\b(mes livres|mes documents|ma bibliotheque|dans (le|les) livre|"+
        "source|sources|reference|references|cite|citation|page|pages|"+
        "cours medical|fiches medicales|dans medrebuild)\\b")
    fun searchDocuments(question:String,mode:String,followUp:Boolean):Boolean {
        if(mode=="general"||followUp)return false
        if(mode=="sources")return true
        val q=SearchPolicy.normalized(question).trim()
        if(q.isBlank()||ConversationPolicy.isGreeting(q)||
           ConversationPolicy.isModelQuestion(q))return false
        return academic.containsMatchIn(q)||sourceIntent.containsMatchIn(q)
    }
    fun quickPersonalResponse(question:String,version:String,modelAvailable:Boolean):String? {
        val q=SearchPolicy.normalized(question).replace(Regex("[^a-z0-9 ]")," ")
            .replace(Regex("\\s+")," ").trim()
        if(ConversationPolicy.isModelQuestion(q))
            return "Je suis MedBrain $version, ton application Android avec "+
                (if(modelAvailable)"Qwen GGUF local installé" else "moteur GGUF non actif")+
                ". Je ne suis pas ChatGPT. Mes livres sont indexés dans une bibliothèque "+
                "distincte : le modèle neuronal ne les mémorise pas dans ses poids."
        return when(q) {
            "hein","hein quoi","cad","c a d","donc quoi","tu sais quoi",
            "oft tu sais quoi","bref","ok","d accord","merci","merci beaucoup" ->
                "Je t'écoute. Précise ce que tu souhaites comprendre ou reprendre."
            "ca va","comment vas tu","tu vas bien" ->
                "Je suis disponible. Tu veux poursuivre notre discussion ou ouvrir un cours ?"
            else -> null
        }
    }
}
