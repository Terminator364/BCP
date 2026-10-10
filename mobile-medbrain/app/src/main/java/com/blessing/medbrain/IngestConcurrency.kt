package com.blessing.medbrain
import kotlinx.coroutines.sync.Semaphore
/** Avoid simultaneous PDFBox/OCR instances consuming available Galaxy phone RAM. */
object IngestConcurrency { val gate=Semaphore(1) }
