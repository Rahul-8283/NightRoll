import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { colors } from '@/theme/colors';
import { fontAssets, fonts } from '@/theme/typography';

void SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts(fontAssets);

  // If the fonts fail to load the app still opens, in the system font.
  useEffect(() => {
    if (loaded || error) {
      void SplashScreen.hideAsync();
    }
  }, [loaded, error]);

  if (!loaded && !error) {
    return null;
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.ink1 },
          headerTintColor: colors.paper,
          headerTitleStyle: { fontFamily: fonts.bodySemi, fontSize: 17 },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: colors.ink1 },
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="welcome" options={{ headerShown: false }} />
        <Stack.Screen name="consent" options={{ title: 'Consent' }} />
        <Stack.Screen name="enroll" options={{ title: 'Enrollment' }} />
        <Stack.Screen name="mark" options={{ title: 'Mark attendance' }} />
        <Stack.Screen name="result" options={{ title: 'Result' }} />
        <Stack.Screen name="fallback" options={{ title: 'Ground-floor scanner' }} />
        <Stack.Screen name="settings" options={{ title: 'Settings' }} />
      </Stack>
    </>
  );
}
