import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

// Sample data: the real verdict and reason arrive from the backend in Phase 7.
const SAMPLE_RESULT = {
  verdict: 'PRESENT' as const,
  reason: 'Face match, room network and device key all checked out.',
};

export default function ResultScreen() {
  const isPresent = SAMPLE_RESULT.verdict === 'PRESENT';

  return (
    <View style={styles.container}>
      <Text style={[styles.verdict, isPresent ? styles.verdictOk : styles.verdictBad]}>
        {SAMPLE_RESULT.verdict}
      </Text>
      <Text style={styles.reason}>{SAMPLE_RESULT.reason}</Text>
      <Text style={styles.note}>Sample result. Built on the real verdict in Phase 7.</Text>
      <Link href={isPresent ? '/' : '/fallback'} asChild>
        <Pressable style={styles.button}>
          <Text style={styles.buttonText}>{isPresent ? 'Back to Home' : 'What do I do now?'}</Text>
        </Pressable>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.md },
  verdict: { fontSize: 26, fontWeight: '700' },
  verdictOk: { color: colors.success },
  verdictBad: { color: colors.danger },
  reason: { fontSize: 16, color: colors.text, textAlign: 'center' },
  note: { fontSize: 13, color: colors.muted, textAlign: 'center' },
  button: {
    marginTop: spacing.md,
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: 12,
  },
  buttonText: { color: '#fff', fontSize: 17, fontWeight: '600' },
});
