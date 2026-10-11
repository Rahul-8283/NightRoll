import type { ExpoConfig } from 'expo/config';

// EAS sets EAS_BUILD_PROFILE during a cloud build; it is unset for `expo start` and for the
// production profile, so cleartext HTTP only ever reaches the development build (task 9.5).
const isDevelopmentBuild = process.env.EAS_BUILD_PROFILE === 'development';
// Release builds trust only the server's own certificate authority (Phase 12, task 2.7).
const isReleaseBuild = ['production', 'preview'].includes(process.env.EAS_BUILD_PROFILE ?? '');

const config: ExpoConfig = {
  name: 'NightRoll',
  slug: 'nightroll',
  version: '0.1.0',
  orientation: 'portrait',
  icon: './assets/images/icon.png',
  scheme: 'nightroll',
  userInterfaceStyle: 'dark',
  backgroundColor: '#0b0d13',
  android: {
    package: 'com.zerolatency.nightroll',
    permissions: [
      'INTERNET',
      'ACCESS_NETWORK_STATE',
      'CAMERA',
      'ACCESS_FINE_LOCATION',
      'ACCESS_WIFI_STATE',
      'CHANGE_WIFI_STATE',
      'NEARBY_WIFI_DEVICES',
    ],
    adaptiveIcon: {
      backgroundColor: '#0b0d13',
      foregroundImage: './assets/images/android-icon-foreground.png',
      backgroundImage: './assets/images/android-icon-background.png',
      monochromeImage: './assets/images/android-icon-monochrome.png',
    },
  },
  plugins: [
    'expo-router',
    'expo-secure-store',
    'expo-dev-client',
    ['expo-build-properties', { android: { minSdkVersion: 28 } }],
    [
      'expo-splash-screen',
      {
        backgroundColor: '#0b0d13',
        image: './assets/images/splash-icon.png',
        imageWidth: 76,
      },
    ],
    ...(isDevelopmentBuild ? ['./plugins/withDevCleartextHttp'] : []),
    ...(isReleaseBuild ? ['./plugins/withPinnedCa'] : []),
  ],
  experiments: {
    typedRoutes: true,
  },
};

export default config;
