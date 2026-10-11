package com.blessing.medbrain
/** Display projection only. All conversation text remains intact in SQLite. */
object ChatWindowPolicy{
    fun preview(full:String,maxChars:Int=1700):String{
        val cap=maxChars.coerceIn(200,3200)
        return if(full.length<=cap)full else full.take(cap)+
            "\n\n… Affichage abrégé. Appuie sur « Voir le message complet »."
    }
}
