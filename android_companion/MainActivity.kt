package co.bumpspoof.companion

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val info = TextView(this).apply {
            text = """
BumpSpoof Companion

Status: Mock GPS active on :12345

Setup (one-time):
  Developer Options
  → Select mock location app
  → BumpSpoof Companion

Then connect USB + start BumpSpoof on PC.
            """.trimIndent()
            textSize = 15f
            setPadding(48, 96, 48, 48)
        }

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(info)
        }

        setContentView(layout)

        // Auto-start service
        startForegroundService(Intent(this, MockLocationService::class.java))
    }

    override fun onResume() {
        super.onResume()
        startForegroundService(Intent(this, MockLocationService::class.java))
    }
}
