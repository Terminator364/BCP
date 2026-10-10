package com.blessing.medbrain

import android.widget.Button
import android.widget.TextView
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.testing.WorkManagerTestInitHelper
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.SQLiteMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@SQLiteMode(SQLiteMode.Mode.NATIVE)
class UiSmokeTest {
    @Test fun allPrimarySpacesAreReachable(){
        WorkManagerTestInitHelper.initializeTestWorkManager(ApplicationProvider.getApplicationContext<Context>())
        val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val pages=mapOf("Accueil" to "Aujourd\'hui",
            "Livres" to "Bibliothèque vivante",
            "Étudier" to "Mes études médicales",
            "Discuter" to "Discussion")
        pages.forEach{ (tab,expected)->
            val button=allButtons(activity.window.decorView).first{it.contentDescription?.toString()=="Ouvrir "+tab}
            button.performClick()
            assertTrue("Unreachable $tab",allText(activity.window.decorView).any{it.contains(expected)})
        }
        val more=allButtons(activity.window.decorView).first{it.contentDescription?.toString()=="Menu complet"}
        more.performClick()
        assertNotNull(org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog())
    }
    private fun allButtons(root:android.view.View):List<Button> {
        val out=mutableListOf<Button>()
        if(root is Button)out.add(root)
        if(root is android.view.ViewGroup) for(i in 0 until root.childCount)out.addAll(allButtons(root.getChildAt(i)))
        return out
    }
    private fun allText(root:android.view.View):List<String> {
        val out=mutableListOf<String>()
        if(root is TextView)out.add(root.text.toString())
        if(root is android.view.ViewGroup) for(i in 0 until root.childCount)out.addAll(allText(root.getChildAt(i)))
        return out
    }
    @Test fun medRebuildCardiologyReaderAndOfflineRecallAreReachable(){
        WorkManagerTestInitHelper.initializeTestWorkManager(
            ApplicationProvider.getApplicationContext<Context>())
        val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
        allButtons(activity.window.decorView).first{
            it.contentDescription?.toString()=="Ouvrir Étudier"
        }.performClick()
        allButtons(activity.window.decorView).first{
            it.text.toString().contains("156 fiches MedRebuild")
        }.performClick()
        assertTrue(allText(activity.window.decorView).any{
            it.contains("collection pédagogique MedRebuild")
        })
        allButtons(activity.window.decorView).first{
            it.text.toString().contains("Sémiologie cardiovasculaire : du symptôme au syndrome")
        }.performClick()
        assertTrue(allText(activity.window.decorView).any{
            it.contains("La sémiologie est")
        })
        allButtons(activity.window.decorView).first{
            it.text.toString().contains("M'entraîner sans regarder")
        }.performClick()
        assertTrue(allText(activity.window.decorView).any{
            it.contains("Rappel actif — sans regarder")
        })
        assertFalse(allText(activity.window.decorView).any{it=="Cours original"})
    }
    @Test fun pinnedComposerRemainsOutsideScrollableContent(){
        WorkManagerTestInitHelper.initializeTestWorkManager(ApplicationProvider.getApplicationContext<Context>())
        val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val root=activity.window.decorView.findViewById<android.view.ViewGroup>(android.R.id.content)
        val shell=root.getChildAt(0) as android.widget.LinearLayout
        assertTrue(shell.getChildAt(1) is android.widget.ScrollView)
        assertTrue(shell.getChildAt(2) is android.widget.LinearLayout)
        assertTrue(shell.getChildAt(3) is android.widget.LinearLayout)
        assertEquals(5,allButtons(shell.getChildAt(3)).size)
        assertTrue(allButtons(shell.getChildAt(2)).any{it.contentDescription?.toString()=="Envoyer le message"})
    }
}
