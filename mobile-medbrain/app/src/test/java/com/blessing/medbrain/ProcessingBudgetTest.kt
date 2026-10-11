package com.blessing.medbrain
import org.junit.Assert.*
import org.junit.Test
class ProcessingBudgetTest {
 private val mb=1024L*1024L
 @Test fun protects256MiBHeap(){
  assertFalse(ProcessingBudget.mayOpenPdf(22*mb,false))
  assertFalse(ProcessingBudget.mayOpenPdf(95*mb,false))
  assertFalse(ProcessingBudget.mayOpenPdf(200*mb,true))
  assertTrue(ProcessingBudget.mayOpenPdf(160*mb,false))
 }
 @Test fun ocrUsesAdditionalMemoryGate(){
  assertTrue(ProcessingBudget.mayOpenPdf(110*mb,false))
  assertFalse(ProcessingBudget.mayRenderOcr(110*mb,false))
  assertTrue(ProcessingBudget.mayRenderOcr(180*mb,false))
 }
 @Test fun inferencePrioritySupersedesBackgroundBatch(){
  assertTrue(ProcessingBudget.yieldIngestion(250*mb,false,true))
  assertTrue(ProcessingBudget.yieldIngestion(20*mb,false,false))
  assertFalse(ProcessingBudget.yieldIngestion(250*mb,false,false))
 }
}
