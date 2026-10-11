package com.blessing.medbrain

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.SQLiteMode

/**
 * 120 minutes accelerated, 120 user turns and 120 synthetic acknowledgements.
 * The synthetic actor intentionally does NOT claim to reproduce Qwen.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@SQLiteMode(SQLiteMode.Mode.NATIVE)
class AdversarialTwoHourReplayTest {
 @Test fun topicSwitchesMetaInterruptionsAndSimulatedEngineFailureSurviveRestart(){
  val ctx=ApplicationProvider.getApplicationContext<Context>()
  ctx.deleteDatabase("medbrain-v1.sqlite")
  var thread=""
  KnowledgeStore(ctx).use { db->
   thread=db.createThread()
   db.register("realCardio","Tome de cardiologie","content://cardio")
   db.save("realCardio",4,"L'insuffisance cardiaque provoque une congestion pulmonaire.",
     4,4,"INDEXED","TEXT")
   db.register("distraction","Histoire du développement des hôpitaux","content://history")
   db.save("distraction",8,"Le mot version figure dans ce document sur les hôpitaux.",
     8,8,"INDEXED","TEXT")
   val topics=listOf("Insuffisance cardiaque","Pneumonie",
     "Paludisme","Prééclampsie","Méningite","Diabète")
   repeat(120){minute->
    val group=minute/20
    val phase=minute%20
    val q=when(phase){
     0->"Explique "+topics[group]
     1->"Et ses signes ?"
     2->"Continue au point 4"
     3->"Pourquoi ?"
     4->"Je n'ai pas compris"
     5->"tu es quelle version ?"
     6->"merci"
     7->"Et les complications ?"
     8->"Parle-moi du traitement ?"
     9->"Donne moi un exemple"
     10->"Et chez les nourrissons ?"
     11->"Tu sais quoi ?"
     12->"Explique-le autrement"
     13->"Fais une synthèse de ce que tu viens de dire"
     14->"À quoi cela sert ?"
     15->"Et pour la tuberculose ?"
     16->"Et ses symptômes ?"
     17->"Peux tu m'en parler plus en détail ?"
     18->"Quelle est ta version ?"
     else->"Et les complications ?"
    }
    val historical=db.promptContext(thread)
    val decision=DialoguePlanner.route(q,historical)
    val search=ChatRoutingPolicy.searchDocuments(q,"auto",decision.followUp)
    val expected=phase==0||phase==15
    assertEquals("Minute "+minute+" unexpected source lookup for "+q,expected,search)
    if(phase in listOf(1,2,3,4,7,8,9,10,12,13,14,16,17,19)){
     assertTrue("Minute "+minute+" lost topic: "+q,decision.followUp)
     assertTrue("Minute "+minute+" asked FTS to search ellipsis: "+q,!search)
    }
    if(phase in listOf(5,18)){
     val product=ChatRoutingPolicy.quickPersonalResponse(q,"0.5.1",true)
     assertTrue("Missing real version in answer: "+q,product?.contains("0.5.1")==true)
     assertTrue("Metadata query used a book",!search)
    }
    db.addChat("user",q,threadId=thread)
    // Stubbed response: demonstrates persistence under interleaved slow/failing inference.
    val answer=when(phase){
     5,18->"Je suis MedBrain 0.5.1."
     6->"Avec plaisir."
     11->"Je t'écoute, continue."
     17->"Le moteur neuronal n'a pas produit de réponse fiable."
     else->"Résumé simulé de session, minute "+minute+"."
    }
    db.addChat("assistant",answer,threadId=thread)
    assertTrue("Original books unexpectedly deleted",db.documents().size==2)
   }
   db.readableDatabase.rawQuery("SELECT COUNT(*) FROM chats WHERE thread_id=?",
      arrayOf(thread)).use{c->
    assertTrue(c.moveToFirst())
    assertEquals(240,c.getInt(0))
   }
  }
  KnowledgeStore(ctx).use{db->
   assertEquals(2,db.documents().size)
   val last=db.messages(thread,1).lastOrNull()
   assertEquals("assistant",last?.kind)
   assertEquals(180,db.promptContext(thread).size)
   assertEquals(200,db.messages(thread,200).size)
   assertTrue(db.retrieve("cardiaque").any{it.title=="Tome de cardiologie"})
  }
 }
 @Test fun partialRunCannotDuplicateLastUserMessage(){
  val ctx=ApplicationProvider.getApplicationContext<Context>()
  ctx.deleteDatabase("medbrain-v1.sqlite")
  val thread=KnowledgeStore(ctx).use{db->
   val id=db.createThread()
   db.addChat("user","Continue au point 4",threadId=id)
   id
  }
  KnowledgeStore(ctx).use{db->
   val pending=ConversationRecoveryPolicy.pending(db.messages(thread,4),false)
   assertEquals("Continue au point 4",pending?.body)
   assertTrue(ConversationRecoveryPolicy.canRetry(pending,"Continue au point 4"))
   db.addChat("assistant","Suite relancée après redémarrage.",threadId=thread)
   assertEquals(2,db.messages(thread,10).size)
   assertNull(ConversationRecoveryPolicy.pending(db.messages(thread,4),false))
  }
 }
 @Test fun fakeReasoningAndOcrAreNeverTreatedAsVerifiedMedicalAnswer(){
  val raw="Wait, the user might be a layperson. I should outline the steps first."
  assertEquals(ModelOutputPolicy.NO_FINAL,ModelOutputPolicy.clean(raw))
  val noisy=Passage("Pharmacologie",48,"GATAA 0sfl qbarn mngr.","OCR")
  val honest=Passage("Cardiologie",12,"La congestion pulmonaire accompagne l'insuffisance.","TEXT")
  assertEquals(listOf(honest),SourceVerification.trusted(listOf(noisy,honest)))
  val fallback=DialoguePlanner.fallback(listOf(noisy),false,emptyList(),"cardiologie")
  assertFalse(fallback.contains("GATAA"))
  assertTrue(fallback.contains("OCR"))
 }
}
