package com.blessing.medbrain

object SourceVerification {
 fun trusted(items:List<Passage>):List<Passage> = items.filter { it.method == "TEXT" }
}
