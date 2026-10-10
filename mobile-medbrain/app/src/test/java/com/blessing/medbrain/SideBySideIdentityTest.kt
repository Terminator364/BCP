package com.blessing.medbrain

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class SideBySideIdentityTest {
    @Test fun packageIdentityIsDistinctFromPreviouslyInstalledApp(){
        val ctx=ApplicationProvider.getApplicationContext<Context>()
        assertEquals("com.blessing.medbrain.personal",ctx.packageName)
        assertNotEquals("com.blessing.medbrain",ctx.packageName)
    }
}
