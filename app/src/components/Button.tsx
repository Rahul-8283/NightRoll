import { router, type Href } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { Pressable, StyleSheet, Text, View, type PressableProps } from 'react-native';

import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';

type Variant = 'primary' | 'quiet' | 'danger';

type Props = {
  label: string;
  variant?: Variant;
  onPress?: PressableProps['onPress'];
  /** Navigates instead of calling onPress. */
  href?: Href;
  disabled?: boolean;
};

/** `primary` is the lit one: at most one per screen. */
export function Button({ label, variant = 'primary', onPress, href, disabled }: Props) {
  return (
    <Pressable
      accessibilityRole={href ? 'link' : 'button'}
      accessibilityState={{ disabled: !!disabled }}
      onPress={href ? () => router.push(href) : onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        variant === 'primary' && styles.primary,
        variant === 'quiet' && styles.quiet,
        variant === 'danger' && styles.danger,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}
    >
      {variant === 'primary' && (
        <LinearGradient colors={[colors.lampBright, colors.lamp]} style={StyleSheet.absoluteFill} />
      )}
      <View style={styles.inner}>
        <Text
          style={[
            styles.label,
            variant === 'primary' && styles.labelPrimary,
            variant === 'danger' && styles.labelDanger,
          ]}
        >
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 52,
    alignSelf: 'stretch',
    borderRadius: radius.control,
    borderWidth: 1,
    overflow: 'hidden',
    justifyContent: 'center',
  },
  inner: { paddingVertical: spacing.md, paddingHorizontal: spacing.lg, alignItems: 'center' },
  primary: { borderColor: colors.lamp, boxShadow: `0 8px 28px ${colors.lampGlow}` },
  quiet: { borderColor: colors.line, backgroundColor: colors.ink3 },
  danger: { borderColor: 'rgba(238, 108, 77, 0.45)', backgroundColor: colors.emberWash },
  pressed: { opacity: 0.82, transform: [{ scale: 0.99 }] },
  disabled: { opacity: 0.45 },
  label: { fontFamily: fonts.bodySemi, fontSize: 17, color: colors.paper },
  labelPrimary: { color: colors.onLamp },
  labelDanger: { color: colors.ember },
});
