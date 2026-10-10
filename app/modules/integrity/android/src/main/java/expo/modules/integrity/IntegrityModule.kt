package expo.modules.integrity

import android.content.Context
import com.google.android.play.core.integrity.IntegrityManager
import com.google.android.play.core.integrity.IntegrityManagerFactory
import com.google.android.play.core.integrity.IntegrityTokenRequest
import com.google.android.play.core.integrity.model.IntegrityErrorCode
import com.google.android.play.core.integrity.IntegrityServiceException
import expo.modules.kotlin.Promise
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class IntegrityModule : Module() {
  private val context: Context
    get() = appContext.reactContext ?: throw CodedException("React context is not available")

  private var integrityManager: IntegrityManager? = null
  private var cloudProjectNumber: Long = 0L

  override fun definition() = ModuleDefinition {
    Name("Integrity")

    AsyncFunction("prepare") { projectNumberStr: String ->
      try {
        cloudProjectNumber = projectNumberStr.toLongOrNull() ?: 0L
        integrityManager = IntegrityManagerFactory.create(context.applicationContext)
        true
      } catch (_: Exception) {
        false
      }
    }

    AsyncFunction("requestToken") { requestHash: String, promise: Promise ->
      val manager = integrityManager ?: IntegrityManagerFactory.create(context.applicationContext).also {
        integrityManager = it
      }

      val requestBuilder = IntegrityTokenRequest.builder().setRequestHash(requestHash)
      if (cloudProjectNumber > 0L) {
        requestBuilder.setCloudProjectNumber(cloudProjectNumber)
      }

      val request = requestBuilder.build()
      manager.requestIntegrityToken(request)
        .addOnSuccessListener { response ->
          promise.resolve(
            mapOf(
              "token" to response.token(),
              "errorCode" to null
            )
          )
        }
        .addOnFailureListener { exception ->
          val errorCode = if (exception is IntegrityServiceException) {
            "INTEGRITY_${exception.errorCode}"
          } else {
            exception.message ?: "UNKNOWN_INTEGRITY_ERROR"
          }
          promise.resolve(
            mapOf(
              "token" to null,
              "errorCode" to errorCode
            )
          )
        }
    }
  }
}
