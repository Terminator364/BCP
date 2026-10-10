package com.blessing.medbrain

import android.widget.Button
import android.widget.TextView
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class UiSmokeTest {
    @Test fun allFiveSectionsAreRealAndClickable(){
        val activity=Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val pages=mapOf("Accueil" to "Tableau de bord",
            "Bibliothèque" to "Bibliothèque vivante",
            "Étudier" to "Apprendre et s'évaluer",
            "Interroger" to "Interroger mon IA",
            "Diagnostic" to "Diagnostic et contrôle")
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
}
