package com.blessing.medbrain
import kotlinx.coroutines.sync.Semaphore
/** Avoid simultaneous PDFBox/OCR instances consuming available Galaxy phone RAM. */
object IngestConcurrency {
    val gate=Semaphore(1)
    /** Do not start the next PDF/OCR page while Qwen is actively inferring. */
    fun shouldYield(now:Long,inferenceUntil:Long):Boolean=now<inferenceUntil
}
