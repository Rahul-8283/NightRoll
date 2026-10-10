import { Link, useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

export default function FallbackScreen() {
  const { reason } = useLocalSearchParams<{ reason?: string }>();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Use the ground-floor scanner</Text>
      <Text style={styles.reason}>
        {reason ?? 'NightRoll could not confirm your attendance from here tonight.'}
      </Text>
      <Text style={styles.body}>
        Head down and scan at the ground-floor desk as usual. The warden can also mark you
        present by hand if the scanner is down.
      </Text>
      <Link href="/" asChild>
        <Pressable style={styles.button}>
          <Text style={styles.buttonText}>Back to Home</Text>
        </Pressable>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.md },
  title: { fontSize: 22, fontWeight: '700', color: colors.text, textAlign: 'center' },
  reason: { fontSize: 16, color: colors.danger, textAlign: 'center' },
  body: { fontSize: 15, color: colors.muted, textAlign: 'center' },
  button: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  buttonText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
});
