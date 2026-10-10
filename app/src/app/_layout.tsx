import { Stack } from 'expo-router';

export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: 'NightRoll' }} />
      <Stack.Screen name="welcome" options={{ title: 'Welcome' }} />
      <Stack.Screen name="consent" options={{ title: 'Consent' }} />
      <Stack.Screen name="enroll" options={{ title: 'Enrollment' }} />
      <Stack.Screen name="mark" options={{ title: 'Marking' }} />
      <Stack.Screen name="result" options={{ title: 'Result' }} />
      <Stack.Screen name="fallback" options={{ title: 'Fallback' }} />
      <Stack.Screen name="settings" options={{ title: 'Settings' }} />
    </Stack>
  );
}
