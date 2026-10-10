import { StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/colors';
import { fonts } from '@/theme/typography';

/** The mark is a single window with one pane lit. */
export function Wordmark({ size = 22 }: { size?: number }) {
  return (
    <View style={styles.row} accessible accessibilityRole="header" accessibilityLabel="NightRoll">
      <View style={styles.mark}>
        <View style={styles.markRow}>
          <View style={[styles.pane, styles.paneLit]} />
          <View style={styles.pane} />
        </View>
        <View style={styles.markRow}>
          <View style={styles.pane} />
          <View style={styles.pane} />
        </View>
      </View>
      <Text style={[styles.name, { fontSize: size }]}>
        Night<Text style={styles.roll}>Roll</Text>
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  mark: {
    padding: 3,
    gap: 2,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.ink3,
  },
  markRow: { flexDirection: 'row', gap: 2 },
  pane: { width: 7, height: 9, borderRadius: 1.5, backgroundColor: colors.ink1 },
  paneLit: { backgroundColor: colors.lamp },
  name: { fontFamily: fonts.displayMedium, color: colors.paper, letterSpacing: -0.3 },
  roll: { fontFamily: fonts.displayItalic, color: colors.lamp },
});
