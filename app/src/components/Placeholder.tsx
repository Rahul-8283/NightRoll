import { Link, type Href } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

type Props = {
  title: string;
  phase: string;
  /** Shown as a "Continue" link, so the real flow stays navigable while this is a shell. */
  nextRoute?: Href;
  nextLabel?: string;
};

// Stand-in for screens whose features are built in later phases.
export function Placeholder({ title, phase, nextRoute, nextLabel = 'Continue' }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.note}>Not built yet. Planned in {phase}.</Text>
      {nextRoute && (
        <Link href={nextRoute} asChild>
          <Pressable style={styles.button}>
            <Text style={styles.buttonText}>{nextLabel}</Text>
          </Pressable>
        </Link>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: spacing.md },
  title: { fontSize: 22, fontWeight: '600', color: colors.text },
  note: { fontSize: 15, color: colors.muted, textAlign: 'center' },
  button: { paddingVertical: spacing.sm, paddingHorizontal: spacing.lg },
  buttonText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
});
