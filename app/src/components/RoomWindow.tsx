import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, StyleSheet, View } from 'react-native';

import { colors } from '@/theme/colors';
import { radius } from '@/theme/spacing';

/**
 * lit      the light is on: marked present
 * waiting  the window is open and the room is waiting for you: a soft pulse
 * moon     cold outline: scheduled, or with the warden for review
 * ember    red outline: rejected
 * dark     nothing happening tonight
 */
export type WindowLight = 'lit' | 'waiting' | 'moon' | 'ember' | 'dark';

type Props = { light: WindowLight; size?: number; label: string };

/** The student's room, drawn as a four-pane window. The app's one signature element. */
export function RoomWindow({ light, size = 168, label }: Props) {
  const [pulse] = useState(() => new Animated.Value(1));
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
  }, []);

  useEffect(() => {
    if (light !== 'waiting' || reduceMotion) {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.45, duration: 1400, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 1400, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [light, reduceMotion, pulse]);

  const gap = Math.round(size * 0.045);
  const padding = Math.round(size * 0.06);
  const paneWidth = (size - padding * 2 - gap) / 2;
  const paneHeight = paneWidth * 1.25;
  const glowing = light === 'lit' || light === 'waiting';

  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={label}
      style={[
        styles.frame,
        { width: size, padding, gap, borderRadius: radius.window + 4 },
        glowing && { boxShadow: `0 0 ${light === 'lit' ? 64 : 40}px ${colors.lampGlow}` },
      ]}
    >
      {[0, 1].map((row) => (
        <View key={row} style={[styles.row, { gap }]}>
          {[0, 1].map((col) => (
            <Animated.View
              key={col}
              style={[
                styles.pane,
                { width: paneWidth, height: paneHeight },
                light === 'waiting' && { opacity: pulse },
                light === 'waiting' && styles.paneWaiting,
                light === 'moon' && styles.paneMoon,
                light === 'ember' && styles.paneEmber,
              ]}
            >
              {light === 'lit' && (
                <LinearGradient
                  colors={[colors.lampBright, colors.lamp, colors.lampDeep]}
                  style={StyleSheet.absoluteFill}
                />
              )}
            </Animated.View>
          ))}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { backgroundColor: colors.ink3, borderWidth: 1, borderColor: colors.line },
  row: { flexDirection: 'row' },
  pane: {
    borderRadius: radius.pane,
    backgroundColor: colors.ink1,
    borderWidth: 1,
    borderColor: 'transparent',
    overflow: 'hidden',
  },
  paneWaiting: { backgroundColor: 'rgba(245, 185, 92, 0.42)', borderColor: colors.lamp },
  paneMoon: { backgroundColor: colors.moonWash, borderColor: colors.moon },
  paneEmber: { backgroundColor: colors.emberWash, borderColor: colors.ember },
});
