package com.blessing.medbrain

import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan

/** Lightweight offline renderer. Persisted SQLite message source is never modified. */
object MedicalMarkdown {
    fun render(source:String):CharSequence {
        val output=SpannableStringBuilder()
        val lines=source.split("\n")
        lines.forEachIndexed{index,line->
            val match=Regex("^(#{1,3})\\s+").find(line)
            val body=if(match!=null)line.substring(match.value.length) else line
            val start=output.length
            inline(body,output)
            if(match!=null && output.length>start){
                output.setSpan(StyleSpan(Typeface.BOLD),start,output.length,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                output.setSpan(RelativeSizeSpan(if(match.groupValues[1].length==1)1.16f else 1.08f),
                    start,output.length,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
            if(index!=lines.lastIndex)output.append('\n')
        }
        return output
    }
    private fun inline(line:String,out:SpannableStringBuilder){
        var i=0
        while(i<line.length){
            val isBold=line.startsWith("**",i)
            val isCode=line[i]==0x60.toChar()
            val delimiter=when {
                isBold->"**"
                isCode->0x60.toChar().toString()
                else->null
            }
            if(delimiter!=null){
                val end=line.indexOf(delimiter,i+delimiter.length)
                if(end>i+delimiter.length){
                    val begin=out.length
                    out.append(line.substring(i+delimiter.length,end))
                    if(isBold)out.setSpan(StyleSpan(Typeface.BOLD),
                        begin,out.length,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    else out.setSpan(TypefaceSpan("monospace"),
                        begin,out.length,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    i=end+delimiter.length
                    continue
                }
            }
            out.append(line[i])
            i++
        }
    }
}
