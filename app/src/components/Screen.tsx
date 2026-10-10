import { LinearGradient } from 'expo-linear-gradient';
import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, View, type ViewStyle } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

type Props = {
  children: ReactNode;
  /** Tints the light falling from the top of the screen. */
  glow?: 'lamp' | 'moon' | 'ember' | 'none';
  /** Screens with a navigation header skip the top inset; the header already covers it. */
  edges?: Edge[];
  contentStyle?: ViewStyle;
};

const GLOW = {
  lamp: ['rgba(245, 185, 92, 0.16)', 'rgba(245, 185, 92, 0.05)', 'rgba(245, 185, 92, 0)'],
  moon: ['rgba(169, 193, 232, 0.12)', 'rgba(169, 193, 232, 0.04)', 'rgba(169, 193, 232, 0)'],
  ember: ['rgba(238, 108, 77, 0.14)', 'rgba(238, 108, 77, 0.045)', 'rgba(238, 108, 77, 0)'],
} as const;

/** Every screen sits on the same night background, with a soft light from above. */
export function Screen({ children, glow = 'lamp', edges = ['bottom'], contentStyle }: Props) {
  return (
    <View style={styles.root}>
      {glow !== 'none' && (
        <LinearGradient
          pointerEvents="none"
          colors={GLOW[glow]}
          locations={[0, 0.45, 1]}
          style={styles.glow}
        />
      )}
      <SafeAreaView style={styles.safe} edges={edges}>
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle]}
          showsVerticalScrollIndicator={false}
        >
          {children}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.ink1 },
  glow: { position: 'absolute', top: 0, left: 0, right: 0, height: 520 },
  safe: { flex: 1 },
  content: {
    flexGrow: 1,
    padding: spacing.lg,
    gap: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
