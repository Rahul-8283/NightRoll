package expo.modules.facedetector

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import expo.modules.kotlin.Promise
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import kotlin.math.max
import kotlin.math.min

class FaceDetectorModule : Module() {
  private val context: Context
    get() = appContext.reactContext ?: throw CodedException("React context is not available")

  private val detector by lazy {
    val options = FaceDetectorOptions.Builder()
      .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
      .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
      .build()
    FaceDetection.getClient(options)
  }

  override fun definition() = ModuleDefinition {
    Name("FaceDetector")

    AsyncFunction("detect") { pathOrUri: String, promise: Promise ->
      val cleanPath = cleanFilePath(pathOrUri)
      val bitmap = try {
        BitmapFactory.decodeFile(cleanPath)
      } catch (_: Exception) {
        null
      }

      if (bitmap == null) {
        promise.resolve(
          mapOf(
            "success" to false,
            "error" to "Failed to decode image from path: $pathOrUri",
            "facesCount" to 0
          )
        )
        return@AsyncFunction
      }

      val brightness = calculateBrightness(bitmap)
      val sharpness = calculateSharpness(bitmap)
      val imageArea = bitmap.width * bitmap.height

      val inputImage = InputImage.fromBitmap(bitmap, 0)
      detector.process(inputImage)
        .addOnSuccessListener { faces ->
          val count = faces.size
          if (count == 0) {
            promise.resolve(
              mapOf(
                "success" to true,
                "facesCount" to 0,
                "brightness" to brightness,
                "sharpness" to sharpness,
                "tooDark" to (brightness < 40.0),
                "oneFace" to false,
                "largeEnough" to false,
                "sharpEnough" to (sharpness >= 15.0)
              )
            )
            return@addOnSuccessListener
          }

          val face = faces[0]
          val box = face.boundingBox
          val faceArea = max(0, box.width()) * max(0, box.height())
          val faceRatio = if (imageArea > 0) faceArea.toDouble() / imageArea.toDouble() else 0.0

          promise.resolve(
            mapOf(
              "success" to true,
              "facesCount" to count,
              "headEulerAngleY" to face.headEulerAngleY,
              "headEulerAngleX" to face.headEulerAngleX,
              "headEulerAngleZ" to face.headEulerAngleZ,
              "leftEyeOpenProbability" to (face.leftEyeOpenProbability ?: -1f),
              "rightEyeOpenProbability" to (face.rightEyeOpenProbability ?: -1f),
              "smilingProbability" to (face.smilingProbability ?: -1f),
              "faceAreaRatio" to faceRatio,
              "brightness" to brightness,
              "sharpness" to sharpness,
              "tooDark" to (brightness < 40.0),
              "oneFace" to (count == 1),
              "largeEnough" to (faceRatio >= 0.08),
              "sharpEnough" to (sharpness >= 15.0)
            )
          )
        }
        .addOnFailureListener { exc ->
          promise.resolve(
            mapOf(
              "success" to false,
              "error" to (exc.message ?: "ML Kit detection failed"),
              "facesCount" to 0
            )
          )
        }
    }

    AsyncFunction("compressAndHash") { pathOrUri: String, maxDimension: Int ->
      val cleanPath = cleanFilePath(pathOrUri)
      val original = BitmapFactory.decodeFile(cleanPath)
        ?: throw CodedException("Cannot decode image file at: $pathOrUri")

      val targetMax = if (maxDimension > 0) maxDimension else 720
      val width = original.width
      val height = original.height

      val scaledBitmap: Bitmap
      if (width > targetMax || height > targetMax) {
        val scale = targetMax.toFloat() / max(width, height).toFloat()
        val matrix = Matrix().apply { postScale(scale, scale) }
        scaledBitmap = Bitmap.createBitmap(original, 0, 0, width, height, matrix, true)
      } else {
        scaledBitmap = original
      }

      val baos = ByteArrayOutputStream()
      scaledBitmap.compress(Bitmap.CompressFormat.JPEG, 85, baos)
      val jpegBytes = baos.toByteArray()

      // Calculate SHA-256
      val md = MessageDigest.getInstance("SHA-256")
      val digest = md.digest(jpegBytes)
      val sha256Hex = digest.joinToString("") { "%02x".format(it) }

      // Save compressed file to cache directory
      val outFile = File(context.cacheDir, "frame_${System.currentTimeMillis()}_${sha256Hex.take(8)}.jpg")
      FileOutputStream(outFile).use { fos ->
        fos.write(jpegBytes)
      }

      mapOf(
        "uri" to outFile.toURI().toString(),
        "sha256" to sha256Hex,
        "width" to scaledBitmap.width,
        "height" to scaledBitmap.height,
        "sizeBytes" to jpegBytes.size
      )
    }
  }

  private fun cleanFilePath(pathOrUri: String): String {
    return if (pathOrUri.startsWith("file://")) {
      Uri.parse(pathOrUri).path ?: pathOrUri.removePrefix("file://")
    } else {
      pathOrUri
    }
  }

  private fun calculateBrightness(bitmap: Bitmap): Double {
    val step = max(1, bitmap.width / 50)
    var totalLum = 0.0
    var count = 0
    for (x in 0 until bitmap.width step step) {
      for (y in 0 until bitmap.height step step) {
        val pixel = bitmap.getPixel(x, y)
        val r = (pixel shr 16) and 0xFF
        val g = (pixel shr 8) and 0xFF
        val b = pixel and 0xFF
        totalLum += (0.299 * r + 0.587 * g + 0.114 * b)
        count++
      }
    }
    return if (count > 0) totalLum / count else 128.0
  }

  private fun calculateSharpness(bitmap: Bitmap): Double {
    // Fast variance-based edge contrast check
    val step = max(1, bitmap.width / 40)
    var diffSum = 0.0
    var count = 0
    for (x in 0 until (bitmap.width - step) step step) {
      for (y in 0 until (bitmap.height - step) step step) {
        val p1 = bitmap.getPixel(x, y) and 0xFF
        val p2 = bitmap.getPixel(x + step, y) and 0xFF
        val p3 = bitmap.getPixel(x, y + step) and 0xFF
        diffSum += (Math.abs(p1 - p2) + Math.abs(p1 - p3))
        count += 2
      }
    }
    return if (count > 0) diffSum / count else 50.0
  }
}
