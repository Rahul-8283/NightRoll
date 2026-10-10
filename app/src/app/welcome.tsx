import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

export default function WelcomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>NightRoll</Text>
      <Text style={styles.body}>
        Mark attendance from your bed at 10 PM, right from your phone. No walk to the ground
        floor.
      </Text>
      <Text style={styles.body}>
        NightRoll still proves it is really you, in your own room, on your own phone: a quick
        face check, your room&apos;s own Wi-Fi, and a key that lives only on this device.
      </Text>
      <Text style={styles.body}>
        Set up takes one visit to the warden&apos;s desk. After that, marking is one tap a
        night.
      </Text>
      <Link href="/consent" asChild>
        <Pressable style={styles.button}>
          <Text style={styles.buttonText}>Get started</Text>
        </Pressable>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.md },
  title: { fontSize: 28, fontWeight: '700', color: colors.text },
  body: { fontSize: 15, color: colors.muted, textAlign: 'center' },
  button: {
    marginTop: spacing.md,
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: 12,
  },
  buttonText: { color: '#fff', fontSize: 17, fontWeight: '600' },
});
