import { StyleSheet, Text as RNText, type TextProps } from 'react-native';

import { colors } from '@/theme/colors';
import { fonts } from '@/theme/typography';

/** Big serif line: one per screen, saying the state in plain words. */
export function Display({ style, ...props }: TextProps) {
  return <RNText accessibilityRole="header" {...props} style={[styles.display, style]} />;
}

export function Title({ style, ...props }: TextProps) {
  return <RNText accessibilityRole="header" {...props} style={[styles.title, style]} />;
}

export function Body({ style, ...props }: TextProps) {
  return <RNText {...props} style={[styles.body, style]} />;
}

/** Small tracked capitals in mono: labels, times, room numbers. */
export function Eyebrow({ style, ...props }: TextProps) {
  return <RNText {...props} style={[styles.eyebrow, style]} />;
}

const styles = StyleSheet.create({
  display: {
    fontFamily: fonts.display,
    fontSize: 38,
    lineHeight: 42,
    letterSpacing: -0.6,
    color: colors.paper,
    textAlign: 'center',
  },
  title: {
    fontFamily: fonts.displayMedium,
    fontSize: 24,
    lineHeight: 29,
    letterSpacing: -0.2,
    color: colors.paper,
  },
  body: {
    fontFamily: fonts.body,
    fontSize: 16,
    lineHeight: 24,
    color: colors.paper2,
  },
  eyebrow: {
    fontFamily: fonts.mono,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.8,
    textTransform: 'uppercase',
    color: colors.paper3,
  },
});
