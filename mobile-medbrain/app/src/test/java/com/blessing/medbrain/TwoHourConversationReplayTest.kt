package com.blessing.medbrain

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.SQLiteMode

/** 120 simulated minutes, real SQLite and dialogue policies. No neural model is emulated. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@SQLiteMode(SQLiteMode.Mode.NATIVE)
class TwoHourConversationReplayTest {
 @Test fun twoHourMixedUserSessionAndPersistence(){
  val ctx=ApplicationProvider.getApplicationContext<Context>()
  ctx.deleteDatabase("medbrain-v1.sqlite")
  KnowledgeStore(ctx).use{store->
   store.register("history","Histoire des hôpitaux","content://history")
   store.save("history",34,"Version des hôpitaux anciens et révolutionnaires.",
      34,34,"INDEXED")
   store.register("cardio","Cours de cardiologie","content://cardio")
   store.save("cardio",12,"L'insuffisance cardiaque cause une congestion pulmonaire.",
      12,12,"INDEXED")
   val ids=listOf(store.createThread(),store.createThread())
   val social=listOf("salut","tu es quelle version ?","ça va ?","merci",
      "j'ai une idée","tu sais quoi ?","hein ?","raconte une histoire")
   val clinic=listOf("Insuffisance cardiaque","Prééclampsie",
      "Anticoagulants","Physiopathologie de l'hémorragie",
      "Biochimie clinique","Syndrome néphrotique","Méningite",
      "Paludisme","ECG","Tétanos","Appendicite","Glycémie","Pédiatrie","Tension artérielle")
   var wrong=0
   repeat(120){minute->
    val phase=minute%30
    val cycle=minute/30
    val thread=ids[cycle%2]
    val q=when(phase){
      0->listOf("Explique l'insuffisance cardiaque","Explique la prééclampsie",
       "Parle-moi du paludisme","Explique le diabète")[cycle]
      1->"Et ses signes ?"
      2->"Continue au point 4"
      3->"tu es quelle version ?"
      4->"tu sais quoi ?"
      5->listOf("Et pour la pneumonie ?","Et pour la méningite ?",
       "Et pour la tuberculose ?","Et pour la bronchite ?")[cycle]
      6->"Ses complications ?"
      in 7..15->social[(phase-7+cycle*2)%social.size]
      else->listOf("Explique","Résume","Je veux comprendre","Parle-moi de")[cycle]+
       " "+clinic[phase-16]
    }
    val history=store.promptContext(thread)
    val follow=DialoguePlanner.route(q,history).followUp
    val search=ChatRoutingPolicy.searchDocuments(q,"auto",follow)
    val wants=phase==0||phase==5||phase>=16
    if(search!=wants || (phase==5 && follow) ||
       (phase in listOf(1,2,6) && !follow))wrong++
    if(!search && phase==3)assertTrue(store.retrieve("version").isNotEmpty())
    store.addChat("user",q,threadId=thread)
    // Explicit routing ACK, not simulated model-generated medical content.
    store.addChat("assistant",if(search)"[RETRIEVAL]" else "[CONVERSATION]",threadId=thread)
   }
   assertEquals("Wrong routes during two-hour replay",0,wrong)
   assertEquals(2,ids.size)
   assertEquals(2,store.documents().size)
   assertEquals(120,ids.sumOf{store.messages(it,200).size}/2)
  }
 }
 @Test fun originalTopicSurvivesSixtyFiveFollowupsAndRestart(){
  val ctx=ApplicationProvider.getApplicationContext<Context>()
  ctx.deleteDatabase("medbrain-v1.sqlite")
  val id=KnowledgeStore(ctx).use{db->
    val thread=db.createThread()
    db.addChat("user","Explique l'insuffisance cardiaque",threadId=thread)
    db.addChat("assistant","La congestion cardiaque est à expliquer.",threadId=thread)
    repeat(65){i->
      db.addChat("user","Continue étape "+i,threadId=thread)
      db.addChat("assistant","Partie "+i,threadId=thread)
    }
    thread
  }
  KnowledgeStore(ctx).use{db->
   val prompt=DialoguePlanner.prompt("Et pour la surveillance ?",
       db.promptContext(id),emptyList(),"auto")
   assertTrue("Lost initial topic: "+prompt,prompt.contains("insuffisance cardiaque"))
   assertEquals(132,db.messages(id,200).size)
  }
 }
 @Test fun inferenceFailureCannotServeAsUsefulPriorAnswer(){
   val history=listOf(
    KnowledgeStore.ChatMessage(1,"user","Le coeur","",1),
    KnowledgeStore.ChatMessage(2,"assistant",
        "Le modèle neuronal n'a pas produit de réponse fiable.","",2))
   assertFalse(DialoguePlanner.route("continue",history).hasHistory)
 }
}