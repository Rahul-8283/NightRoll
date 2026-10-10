package expo.modules.devicekey

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyInfo
import android.security.keystore.KeyProperties
import android.security.keystore.StrongBoxUnavailableException
import android.util.Base64
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.interfaces.ECPublicKey

private const val ALIAS = "nightroll_device_key"
private const val KEYSTORE = "AndroidKeyStore"

class KeyAlreadyExistsException :
  CodedException("Call delete() before generate() to replace an existing device key.")

class NoDeviceKeyException : CodedException("No device key exists. Call generate() first.")

class DeviceKeyModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("DeviceKey")

    AsyncFunction("generate") {
      val store = keyStore()
      if (store.containsAlias(ALIAS)) {
        throw KeyAlreadyExistsException()
      }
      generateKeyPair()
      publicKeyBase64(store) ?: throw NoDeviceKeyException()
    }

    AsyncFunction("getPublicKey") {
      publicKeyBase64(keyStore())
    }

    AsyncFunction("sign") { data: ByteArray ->
      val store = keyStore()
      if (!store.containsAlias(ALIAS)) {
        throw NoDeviceKeyException()
      }
      val privateKey = store.getKey(ALIAS, null)
      val signature = Signature.getInstance("SHA256withECDSA")
      signature.initSign(privateKey as java.security.PrivateKey)
      signature.update(data)
      Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }

    AsyncFunction("exists") {
      keyStore().containsAlias(ALIAS)
    }

    AsyncFunction("delete") {
      val store = keyStore()
      if (store.containsAlias(ALIAS)) {
        store.deleteEntry(ALIAS)
      }
    }

    AsyncFunction("securityLevel") {
      securityLevel(keyStore())
    }
  }

  private fun keyStore(): KeyStore {
    val store = KeyStore.getInstance(KEYSTORE)
    store.load(null)
    return store
  }

  /**
   * StrongBox is preferred; many phones lack it, so a second attempt without it falls back to
   * the trusted execution environment. No user-authentication requirement, so marking stays a
   * one-tap action; the face check is what proves identity.
   */
  private fun generateKeyPair() {
    try {
      generateKeyPair(strongBox = true)
    } catch (_: StrongBoxUnavailableException) {
      generateKeyPair(strongBox = false)
    }
  }

  private fun generateKeyPair(strongBox: Boolean) {
    val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, KEYSTORE)
    val specBuilder =
      KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
        .setAlgorithmParameterSpec(java.security.spec.ECGenParameterSpec("secp256r1"))
        .setDigests(KeyProperties.DIGEST_SHA256)
        .setUserAuthenticationRequired(false)
    if (strongBox && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
      specBuilder.setIsStrongBoxBacked(true)
    }
    generator.initialize(specBuilder.build())
    generator.generateKeyPair()
  }

  private fun publicKeyBase64(store: KeyStore): String? {
    if (!store.containsAlias(ALIAS)) {
      return null
    }
    val certificate = store.getCertificate(ALIAS) ?: return null
    val publicKey = certificate.publicKey as ECPublicKey
    val factory = KeyFactory.getInstance(KeyProperties.KEY_ALGORITHM_EC)
    val encoded = factory.getKeySpec(publicKey, java.security.spec.X509EncodedKeySpec::class.java).encoded
    return Base64.encodeToString(encoded, Base64.NO_WRAP)
  }

  private fun securityLevel(store: KeyStore): String {
    if (!store.containsAlias(ALIAS)) {
      return "software"
    }
    val privateKey = store.getKey(ALIAS, null)
    val factory = java.security.KeyFactory.getInstance(privateKey.algorithm, KEYSTORE)
    val keyInfo = factory.getKeySpec(privateKey, KeyInfo::class.java) as KeyInfo
    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
      return when (keyInfo.securityLevel) {
        android.security.keystore.KeyProperties.SECURITY_LEVEL_STRONGBOX -> "strongbox"
        android.security.keystore.KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT -> "tee"
        else -> "software"
      }
    }
    return if (keyInfo.isInsideSecureHardware) "tee" else "software"
  }
}
