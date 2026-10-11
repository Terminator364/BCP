package com.blessing.medbrain

import android.content.Context
import android.widget.Button
import android.widget.EditText
import android.view.View
import android.view.ViewGroup
import androidx.test.core.app.ApplicationProvider
import androidx.work.testing.WorkManagerTestInitHelper
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.SQLiteMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@SQLiteMode(SQLiteMode.Mode.NATIVE)
class ChatUiRegressionTest {
 private fun views(root:View):List<View>{
  val all=mutableListOf(root)
  if(root is ViewGroup)for(i in 0 until root.childCount)
   all.addAll(views(root.getChildAt(i)))
  return all
 }
 @Test fun realScreenDoesNotAttachBiochemistryToVersionOrCasualChat(){
  val ctx=ApplicationProvider.getApplicationContext<Context>()
  ctx.deleteDatabase("medbrain-v1.sqlite")
  WorkManagerTestInitHelper.initializeTestWorkManager(ctx)
  ctx.getSharedPreferences("medbrain",Context.MODE_PRIVATE).edit()
      .putString("current_chat_thread","default").apply()
  KnowledgeStore(ctx).use{store->
   store.register("unrelated","Biochimie en 84 fiches","content://bio")
   store.save("unrelated",10,
     "La version expérimentale des ions enzymatiques dans la matière vivante est présentée.",
     10,10,"INDEXED","TEXT")
   store.register("unrelated-history","L'Hôpital de la Charité","content://history")
   store.save("unrelated-history",34,
     "Une version de l'histoire révolutionnaire de l'hôpital et ses controverses.",
     34,34,"INDEXED","TEXT")
  }
  val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
  fun all()=views(activity.window.decorView)
  all().filterIsInstance<Button>().first{
    it.contentDescription?.toString()=="Ouvrir Discuter"}.performClick()
  for(q in listOf("tu es quelle version ?","tu sais quoi","merci")){
   val entry=all().filterIsInstance<EditText>().first{
      it.hint?.toString()?.contains("Écris un message")==true}
   entry.setText(q)
   all().filterIsInstance<Button>().first{
     it.contentDescription?.toString()=="Envoyer le message"}.performClick()
  }
  val history=KnowledgeStore(ctx).use{it.messages()}
  assertEquals(6,history.size)
  assertTrue(history[1].body.contains("MedBrain"))
  history.filter{it.kind=="assistant"}.forEach{
   assertFalse(it.body.contains("Biochimie en 84 fiches"))
   assertFalse(it.body.contains("L'Hôpital de la Charité"))
   assertTrue(it.sources.isBlank())
  }
 }
 @Test fun sourceFallbackDoesNotDumpUnverifiedOcrFragments(){
  val suspicious=listOf(Passage("Pharmacologie médicale",48,
   "cs itúbilcurs lrzux GATAA EulEnt CULNvlSivaut.", "OCR"))
  val text=DialoguePlanner.fallback(suspicious,false,emptyList(),"hémorragie")
  assertTrue(text.contains("OCR à vérifier"))
  assertTrue(text.contains("Voir les passages sources"))
  assertFalse(text.contains("CULNvlSivaut"))
  val preview=StudyEngine.immediatePreview("hémorragie",emptyList(),suspicious)
  assertTrue(preview.contains("page 48"))
  assertFalse(preview.contains("CULNvlSivaut"))
 }
}
