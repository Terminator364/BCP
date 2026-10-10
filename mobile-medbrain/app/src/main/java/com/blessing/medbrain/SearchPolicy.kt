package com.blessing.medbrain

import java.text.Normalizer
import java.util.Locale

/** Search intent and evidence ranking independent of model inference. */
object SearchPolicy {
    private val stop=setOf("quelle","quelles","quels","quel","est","sont","comment","pourquoi",
        "dans","avec","sans","entre","quelle","taille","combien","avoir","peux","peut","vous",
        "nous","leur","leurs","cette","celui","celle","donne","dites","moi","notre","votre",
        "deux","pour","fait","fais","plus","moins","chez","tout","tous","une","des","les",
        "son","ses","sur","par","que","qui","quoi","quelques","cest","estce","jai")
    fun normalized(s:String):String=Normalizer.normalize(s.lowercase(Locale.ROOT)
        .replace("œ","oe").replace("æ","ae"),Normalizer.Form.NFD)
        .replace(Regex("\\p{M}+"),"")
    fun terms(q:String):List<String> {
        // "taille" remains a medically meaningful measurement intent, other common question words do not.
        val raw=Regex("[a-z0-9]{3,}").findAll(normalized(q)).map{it.value}.toList()
        return raw.filter{it !in stop || it=="taille"}.distinct().take(9)
    }
    fun expand(terms:List<String>):List<String> = terms.flatMap {
        when(it){
            "coeur","coeurs"->listOf("coeur","cardiaque","myocarde","cardiologie")
            "cardiaque"->listOf("cardiaque","coeur","myocarde")
            "tension"->listOf("tension","arterielle","pression")
            else->listOf(it)
        }
    }
    /**
     * Precision first: intersect concepts before a bounded broad fallback.
     * The FTS4 tokenizer receives only normalized alphanumeric tokens, never raw user SQL.
     * A broad OR scan alone would lose relevant pages behind early unrelated hits.
     */
    fun candidateQueries(question:String):List<String> {
        val groups=terms(question).take(6).map { token ->
            "(" + expand(listOf(token)).distinct().joinToString(" OR ") { "$it*" } + ")"
        }
        if(groups.isEmpty())return emptyList()
        if(groups.size==1)return groups
        val strict=groups.take(3).joinToString(" AND ")
        val pair=groups.take(2).joinToString(" AND ")
        val broad=groups.joinToString(" OR ")
        return listOf(strict,pair,broad).distinct()
    }
    fun firstPosition(terms:List<String>,text:String):Int{
        val norm=normalized(text)
        return expand(terms).map{norm.indexOf(it)}.filter{it>=0}.minOrNull()?:0
    }
    fun score(question:String,title:String,body:String):Double{
        val terms=terms(question)
        if(terms.isEmpty())return 0.0
        val norm=normalized(body)
        val book=normalized(title)
        val families=terms.map{
            when(it){
                "coeur","coeurs","cardiaque" -> listOf("coeur","cardiaque","myocarde","cardiologie")
                else -> listOf(it)
            }
        }
        val positions=families.map{fam->fam.map{norm.indexOf(it)}.filter{it>=0}.minOrNull()?:-1}
        val matched=positions.count{it>=0}
        if(terms.size>=2 && matched<2) return 0.0
        if(terms.size==1 && matched==0) return 0.0
        val present=positions.filter{it>=0}
        val near=if(present.size>1)present.maxOrNull()!!-present.minOrNull()!! else 0
        if(terms.size>=2 && near>420 && terms.none{book.contains(it)})return 0.0
        // Reject fetal obstetrics false positives when asking about general cardiac measurements.
        if(terms.any{it=="coeur"||it=="cardiaque"} && terms.contains("taille") &&
            book.contains("obstetrique") && !book.contains("cardio"))return 0.0
        val titleHits=families.count{fam->fam.any{book.contains(it)}}
        return matched*3.0 + titleHits*1.2 + if(near<120)2.0 else if(near<260)0.8 else 0.0
    }
}