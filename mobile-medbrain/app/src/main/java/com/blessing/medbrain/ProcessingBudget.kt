package com.blessing.medbrain
/** Conservative Java heap budget before large PDFBox/OCR allocations. */
object ProcessingBudget {
 private const val MB=1024L*1024L
 fun heapHeadroom(runtime:Runtime=Runtime.getRuntime()):Long =
  runtime.maxMemory()-(runtime.totalMemory()-runtime.freeMemory())
 fun mayOpenPdf(bytes:Long,lowMemory:Boolean):Boolean =
  !lowMemory&&bytes>=96*MB
 fun mayRenderOcr(bytes:Long,lowMemory:Boolean):Boolean =
  !lowMemory&&bytes>=128*MB
 fun yieldIngestion(bytes:Long,lowMemory:Boolean,inferenceActive:Boolean):Boolean =
  inferenceActive||!mayOpenPdf(bytes,lowMemory)
}
