package expo.modules.wifiscanner

import android.content.Context
import android.location.LocationManager
import android.net.wifi.ScanResult
import android.net.wifi.WifiManager
import android.os.Build
import android.os.SystemClock
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.security.MessageDigest

class WifiServiceUnavailableException : CodedException("Wi-Fi service is unavailable on this device.")

class WifiScannerModule : Module() {
  private val context: Context
    get() = appContext.reactContext ?: throw CodedException("React context is not available")

  private val wifiManager: WifiManager
    get() = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
      ?: throw WifiServiceUnavailableException()

  private val locationManager: LocationManager
    get() = context.applicationContext.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
      ?: throw CodedException("Location service is unavailable")

  override fun definition() = ModuleDefinition {
    Name("WifiScanner")

    AsyncFunction("isLocationEnabled") {
      isLocationEnabledInternal()
    }

    AsyncFunction("currentConnection") {
      val info = wifiManager.connectionInfo
      val bssid = info?.bssid ?: ""
      val rawSsid = info?.ssid ?: ""
      val rssi = info?.rssi ?: -127
      val freq = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) info?.frequency ?: 0 else 0
      val band = frequencyToBand(freq)
      val ssidHash = hashSsid(rawSsid)

      mapOf(
        "bssid" to bssid,
        "ssidHash" to ssidHash,
        "rssi" to rssi,
        "frequency" to freq,
        "band" to band
      )
    }

    AsyncFunction("scan") {
      val locationOn = isLocationEnabledInternal()

      var scanSuccess = false
      try {
        scanSuccess = wifiManager.startScan()
      } catch (_: Exception) {
        scanSuccess = false
      }

      val rawResults: List<ScanResult> = try {
        wifiManager.scanResults ?: emptyList()
      } catch (_: Exception) {
        emptyList()
      }

      val nowUptimeMicros = SystemClock.elapsedRealtime() * 1000L
      var maxAgeSeconds = 0

      val networks = rawResults.map { result ->
        val ageMicros = if (result.timestamp > 0) (nowUptimeMicros - result.timestamp) else 0L
        val ageSec = (ageMicros / 1_000_000L).toInt().coerceAtLeast(0)
        if (ageSec > maxAgeSeconds) {
          maxAgeSeconds = ageSec
        }

        mapOf(
          "bssid" to (result.BSSID ?: ""),
          "ssidHash" to hashSsid(result.SSID),
          "rssi" to result.level,
          "frequency" to result.frequency,
          "band" to frequencyToBand(result.frequency)
        )
      }

      val isStale = maxAgeSeconds > 30

      mapOf(
        "networks" to networks,
        "ageSeconds" to maxAgeSeconds,
        "stale" to isStale,
        "freshScanTriggered" to scanSuccess,
        "locationEnabled" to locationOn
      )
    }
  }

  private fun isLocationEnabledInternal(): Boolean {
    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
      locationManager.isLocationEnabled
    } else {
      locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
        locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    }
  }

  private fun frequencyToBand(freq: Int): String {
    return when (freq) {
      in 2400..2500 -> "2.4GHz"
      in 4900..5900 -> "5GHz"
      in 5925..7125 -> "6GHz"
      else -> if (freq > 4000) "5GHz" else "2.4GHz"
    }
  }

  private fun hashSsid(ssid: String?): String {
    if (ssid.isNullOrEmpty() || ssid == "<unknown ssid>") return ""
    val clean = ssid.removeSurrounding("\"")
    val md = MessageDigest.getInstance("SHA-256")
    val digest = md.digest(clean.toByteArray(Charsets.UTF_8))
    return digest.joinToString("") { "%02x".format(it) }
  }
}
