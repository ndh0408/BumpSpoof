package co.bumpspoof.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.location.Criteria
import android.location.Location
import android.location.LocationManager
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket

/**
 * MockLocationService
 *
 * Foreground service that:
 *  1. Registers GPS_PROVIDER as a test provider
 *  2. Listens on TCP :12345 for JSON location frames from the PC app
 *  3. Injects each frame into LocationManager.setTestProviderLocation()
 *
 * JSON frame format:
 *  {"lat":10.123,"lon":106.456,"alt":12.0,"accuracy":7.5,"bearing":90.0,"speed":2.5}
 *
 * Setup (device side, once):
 *  Developer Options → Select mock location app → BumpSpoof Companion
 */
class MockLocationService : Service() {

    companion object {
        private const val PROVIDER   = LocationManager.GPS_PROVIDER
        private const val PORT       = 12345
        private const val CHANNEL_ID = "bumpspoof"
        private const val NOTIF_ID   = 1
    }

    private lateinit var locationManager: LocationManager
    private var running = false
    private var serverThread: Thread? = null

    // ── lifecycle ─────────────────────────────────────────────────────────────

    override fun onCreate() {
        super.onCreate()
        locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        createChannel()
        startForeground(NOTIF_ID, buildNotif())
        setupProvider()
        startServer()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int =
        START_STICKY

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        running = false
        removeProvider()
        super.onDestroy()
    }

    // ── mock provider ─────────────────────────────────────────────────────────

    private fun setupProvider() {
        try { locationManager.removeTestProvider(PROVIDER) } catch (_: Exception) {}
        locationManager.addTestProvider(
            PROVIDER,
            /* requiresNetwork     */ false,
            /* requiresSatellite   */ false,
            /* requiresCell        */ false,
            /* hasMonetaryCost     */ false,
            /* supportsAltitude    */ true,
            /* supportsSpeed       */ true,
            /* supportsBearing     */ true,
            /* powerRequirement    */ Criteria.POWER_LOW,
            /* accuracy            */ Criteria.ACCURACY_FINE
        )
        locationManager.setTestProviderEnabled(PROVIDER, true)
    }

    private fun removeProvider() {
        try { locationManager.removeTestProvider(PROVIDER) } catch (_: Exception) {}
    }

    // ── TCP server ────────────────────────────────────────────────────────────

    private fun startServer() {
        running = true
        serverThread = Thread {
            try {
                ServerSocket(PORT).use { server ->
                    while (running) {
                        try {
                            val client = server.accept()
                            Thread { handleClient(client) }.apply { isDaemon = true }.start()
                        } catch (e: Exception) {
                            if (running) e.printStackTrace()
                        }
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }.apply { isDaemon = true; start() }
    }

    private fun handleClient(socket: Socket) {
        try {
            val reader = BufferedReader(InputStreamReader(socket.getInputStream()))
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                line?.trim()?.takeIf { it.isNotEmpty() }?.let { injectLocation(JSONObject(it)) }
            }
        } catch (_: Exception) {
        } finally {
            try { socket.close() } catch (_: Exception) {}
        }
    }

    // ── location injection ────────────────────────────────────────────────────

    private fun injectLocation(json: JSONObject) {
        val loc = Location(PROVIDER).apply {
            latitude  = json.getDouble("lat")
            longitude = json.getDouble("lon")
            altitude  = json.optDouble("alt",      10.0)
            accuracy  = json.optDouble("accuracy",  8.0).toFloat()
            bearing   = json.optDouble("bearing",   0.0).toFloat()
            speed     = json.optDouble("speed",     0.0).toFloat()
            time               = System.currentTimeMillis()
            elapsedRealtimeNanos = SystemClock.elapsedRealtimeNanos()

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                bearingAccuracyDegrees          = 1.0f
                speedAccuracyMetersPerSecond    = 0.5f
                verticalAccuracyMeters          = 2.0f
            }
        }

        try {
            locationManager.setTestProviderLocation(PROVIDER, loc)
        } catch (_: Exception) {
            // provider was removed externally; re-add and retry once
            setupProvider()
            try { locationManager.setTestProviderLocation(PROVIDER, loc) } catch (_: Exception) {}
        }
    }

    // ── notification ──────────────────────────────────────────────────────────

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(
                CHANNEL_ID, "BumpSpoof", NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }

    @Suppress("DEPRECATION")
    private fun buildNotif(): Notification {
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            Notification.Builder(this, CHANNEL_ID)
        else
            Notification.Builder(this)

        return builder
            .setContentTitle("BumpSpoof Companion")
            .setContentText("Mock GPS active · listening :$PORT")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .build()
    }
}
