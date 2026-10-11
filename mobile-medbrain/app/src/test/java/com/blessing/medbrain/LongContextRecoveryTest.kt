package com.blessing.medbrain

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.SQLiteMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@SQLiteMode(SQLiteMode.Mode.NATIVE)
class LongContextRecoveryTest {
 @Test fun medicalOriginalTopicStillExistsAfter110ContinuedTurns(){
  val ctx=ApplicationProvider.getApplicationContext<Context>()
  ctx.deleteDatabase("medbrain-v1.sqlite")
  val first=KnowledgeStore(ctx).use{db->
   val a=db.createThread()
   val b=db.createThread()
   db.addChat("user","Explique l'insuffisance cardiaque",threadId=a)
   db.addChat("assistant","La congestion peut entraîner une dyspnée.",threadId=a)
   db.addChat("user","Parlons du roman fantastique",threadId=b)
   db.addChat("assistant","Le roman commence dans une ville.",threadId=b)
   repeat(110){i->
    db.addChat("user","Continue au point "+i,threadId=a)
    db.addChat("assistant","Étape "+i,threadId=a)
   }
   a to b
  }
  KnowledgeStore(ctx).use{db->
   val h=db.promptContext(first.first)
   assertTrue(h.size<=180)
   assertTrue("Clinical topic lost after 110 turns",
      h.any{it.body.contains("insuffisance cardiaque")})
   assertFalse("Cross-thread topic leak",
      h.any{it.body.contains("roman fantastique")})
   val p=DialoguePlanner.prompt("Et les complications ?",h,emptyList(),"auto")
   assertTrue("Incomplete long-context prompt: "+p,p.contains("insuffisance cardiaque"))
   assertTrue(p.contains("Et les complications"))
   assertEquals(222,db.messages(first.first,200).size+22)
  }
 }
 @Test fun latestGeneralSubjectOverridesAnOldMedicalTopic(){
  val history=listOf(
    KnowledgeStore.ChatMessage(1,"user","Explique l'insuffisance cardiaque","",1),
    KnowledgeStore.ChatMessage(2,"assistant","La congestion pulmonaire.","",2),
    KnowledgeStore.ChatMessage(3,"user","Parlons de philosophie éthique","",3),
    KnowledgeStore.ChatMessage(4,"assistant","On peut comparer les écoles de pensée.","",4),
    KnowledgeStore.ChatMessage(5,"user","Merci","",5),
    KnowledgeStore.ChatMessage(6,"assistant","Avec plaisir.","",6)
  )
  val p=DialoguePlanner.prompt("Pourquoi ?",history,emptyList(),"auto")
  assertTrue(p.contains("Question antérieure : Parlons de philosophie"))
  assertFalse(p.contains("Question antérieure : Explique l'insuffisance cardiaque"))
  assertTrue(p.contains("écoles de pensée"))
 }
 @Test fun productVersionAndCourtesyCannotDisplaceLastMeaningfulSubject(){
  assertFalse(DialoguePlanner.isTopicBearing("Tu es quelle version ?"))
  assertFalse(DialoguePlanner.isTopicBearing("Merci"))
  assertTrue(DialoguePlanner.isTopicBearing("Parlons de poésie"))
  assertTrue(DialoguePlanner.isTopicBearing("Explique la méningite"))
 }
}
