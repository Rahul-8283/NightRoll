package expo.modules.environment

import android.content.Context
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.provider.Settings
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class EnvironmentModule : Module() {
  private val context: Context
    get() = appContext.reactContext ?: throw CodedException("React context is not available")

  private val connectivityManager: ConnectivityManager?
    get() = context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager

  private val locationManager: LocationManager?
    get() = context.applicationContext.getSystemService(Context.LOCATION_SERVICE) as? LocationManager

  override fun definition() = ModuleDefinition {
    Name("Environment")

    AsyncFunction("checkEnvironment") {
      val isVpn = checkVpn()
      val hasProxy = checkProxy()
      val isMockLocation = checkMockLocation()
      val isDevOptions = checkDeveloperOptions()
      val isOnWifi = checkOnWifi()
      val isLocEnabled = checkLocationEnabled()

      mapOf(
        "vpn" to isVpn,
        "proxy" to hasProxy,
        "mockLocation" to isMockLocation,
        "developerOptions" to isDevOptions,
        "onWifi" to isOnWifi,
        "locationEnabled" to isLocEnabled
      )
    }
  }

  private fun checkVpn(): Boolean {
    val cm = connectivityManager ?: return false
    val activeNet = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
      cm.activeNetwork
    } else {
      null
    }

    if (activeNet != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
      val caps = cm.getNetworkCapabilities(activeNet) ?: return false
      return caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ||
        !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
    }

    // Fallback for older versions or all networks
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
      val networks = cm.allNetworks
      for (net in networks) {
        val caps = cm.getNetworkCapabilities(net)
        if (caps != null && (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ||
            !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN))) {
          return true
        }
      }
    }
    return false
  }

  private fun checkProxy(): Boolean {
    val host = System.getProperty("http.proxyHost")
    if (!host.isNullOrEmpty()) return true

    val cm = connectivityManager
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && cm?.defaultProxy != null) {
      return true
    }

    val globalProxy = try {
      Settings.Global.getString(context.contentResolver, Settings.Global.HTTP_PROXY)
    } catch (_: Exception) {
      null
    }
    return !globalProxy.isNullOrEmpty()
  }

  private fun checkMockLocation(): Boolean {
    // Check developer setting for mock locations (API < 23)
    val mockSetting = try {
      @Suppress("DEPRECATION")
      Settings.Secure.getString(context.contentResolver, Settings.Secure.ALLOW_MOCK_LOCATION)
    } catch (_: Exception) {
      null
    }
    if (mockSetting != null && mockSetting != "0") {
      return true
    }

    val lm = locationManager ?: return false
    val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
    for (provider in providers) {
      try {
        val loc = lm.getLastKnownLocation(provider) ?: continue
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
          if (loc.isMock) return true
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR2) {
          @Suppress("DEPRECATION")
          if (loc.isFromMockProvider) return true
        }
      } catch (_: SecurityException) {
        // Ignored if permission not granted yet
      }
    }
    return false
  }

  private fun checkDeveloperOptions(): Boolean {
    return try {
      Settings.Global.getInt(context.contentResolver, Settings.Global.DEVELOPMENT_SETTINGS_ENABLED, 0) != 0
    } catch (_: Exception) {
      false
    }
  }

  private fun checkOnWifi(): Boolean {
    val cm = connectivityManager ?: return false
    val activeNet = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
      cm.activeNetwork
    } else {
      null
    } ?: return false

    val caps = cm.getNetworkCapabilities(activeNet) ?: return false
    return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
  }

  private fun checkLocationEnabled(): Boolean {
    val lm = locationManager ?: return false
    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
      lm.isLocationEnabled
    } else {
      lm.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
        lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    }
  }
}
