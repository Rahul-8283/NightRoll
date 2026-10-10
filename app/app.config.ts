import type { ExpoConfig } from 'expo/config';

const config: ExpoConfig = {
  name: 'NightRoll',
  slug: 'nightroll',
  version: '0.1.0',
  orientation: 'portrait',
  icon: './assets/images/icon.png',
  scheme: 'nightroll',
  userInterfaceStyle: 'automatic',
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
      backgroundColor: '#E6F4FE',
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
        backgroundColor: '#208AEF',
        image: './assets/images/splash-icon.png',
        imageWidth: 76,
      },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
};

export default config;
