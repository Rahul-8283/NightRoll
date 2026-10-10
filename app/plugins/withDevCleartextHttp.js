const { withAndroidManifest } = require('@expo/config-plugins');

/**
 * Allows plaintext HTTP to the LAN, so EXPO_PUBLIC_API_BASE_URL can point at the laptop's
 * http:// address while testing (task 9.4-9.5). Call this only for the development build
 * profile; release builds (Phase 12) talk to a real HTTPS backend and must not carry this.
 */
function withDevCleartextHttp(config) {
  return withAndroidManifest(config, (config) => {
    const application = config.modResults.manifest.application?.[0];
    if (application) {
      application.$['android:usesCleartextTraffic'] = 'true';
    }
    return config;
  });
}

module.exports = withDevCleartextHttp;
