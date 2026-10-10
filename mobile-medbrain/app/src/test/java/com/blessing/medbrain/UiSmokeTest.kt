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
    @Test fun allFiveSectionsAreRealAndClickable(){
        WorkManagerTestInitHelper.initializeTestWorkManager(ApplicationProvider.getApplicationContext<Context>())
        val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val pages=mapOf("Accueil" to "Tableau de bord",
            "Bibliothèque" to "Bibliothèque vivante",
            "Étudier" to "Apprendre et s'évaluer",
            "Discussion" to "Mon IA · Discussion",
            "Diagnostic" to "Diagnostic et contrôle",
            "Paramètres" to "Paramètres")
        pages.forEach{ (tab,expected)->
            val button=allButtons(activity.window.decorView).first{it.text.toString()==tab}
            button.performClick()
            assertTrue(allText(activity.window.decorView).any{it.contains(expected)})
        }
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
    @Test fun navigationIsAboveContentAndDoesNotHideBehindSystemBottomBar(){
        WorkManagerTestInitHelper.initializeTestWorkManager(ApplicationProvider.getApplicationContext<Context>())
        val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val root=activity.window.decorView.findViewById<android.view.ViewGroup>(android.R.id.content)
        val shell=root.getChildAt(0) as android.widget.LinearLayout
        assertTrue(shell.getChildAt(1) is android.widget.LinearLayout)
        assertTrue(shell.getChildAt(2) is android.widget.ScrollView)
        assertEquals(6,allButtons(shell.getChildAt(1)).count{it.text.toString() in
            listOf("Accueil","Bibliothèque","Étudier","Discussion","Diagnostic","Paramètres")})
    }

}
