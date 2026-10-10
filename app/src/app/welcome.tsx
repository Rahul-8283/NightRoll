import { StyleSheet, View } from 'react-native';

import { Button } from '@/components/Button';
import { RoomWindow } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { Wordmark } from '@/components/Wordmark';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';

const PROOFS = [
  { title: 'It is you', detail: 'A quick face check with a blink or a turn.' },
  { title: 'You are in your room', detail: 'Your room’s own Wi-Fi, checked by the hostel.' },
  { title: 'It is your phone', detail: 'A key that lives only on this device.' },
];

export default function WelcomeScreen() {
  return (
    <Screen edges={['top', 'bottom']} contentStyle={styles.content}>
      <Wordmark size={26} />

      <View style={styles.hero}>
        <RoomWindow light="lit" size={132} label="A lit room window" />
        <Display>Mark attendance from your bed</Display>
        <Body style={styles.centre}>At 10 PM, on your phone. No walk to the ground floor.</Body>
      </View>

      <View style={styles.card}>
        <Eyebrow>What NightRoll checks</Eyebrow>
        {PROOFS.map((proof) => (
          <View key={proof.title} style={styles.proof}>
            <View style={styles.pane} />
            <View style={styles.proofText}>
              <Body style={styles.proofTitle}>{proof.title}</Body>
              <Body style={styles.proofDetail}>{proof.detail}</Body>
            </View>
          </View>
        ))}
      </View>

      <View style={styles.foot}>
        <Button label="Get started" href="/consent" />
        <Body style={[styles.centre, styles.small]}>
          Setup takes one visit to the warden’s desk.
        </Body>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { alignItems: 'stretch', justifyContent: 'space-between', gap: spacing.xl },
  hero: { alignItems: 'center', gap: spacing.md, paddingTop: spacing.md },
  centre: { textAlign: 'center' },
  card: {
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.card,
    borderWidth: 1,
    borderColor: colors.lineSoft,
    backgroundColor: colors.ink2,
  },
  proof: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
  pane: {
    width: 10,
    height: 13,
    marginTop: 5,
    borderRadius: 2,
    backgroundColor: colors.lamp,
    boxShadow: `0 0 10px ${colors.lampGlow}`,
  },
  proofText: { flex: 1 },
  proofTitle: { fontFamily: fonts.bodySemi, color: colors.paper },
  proofDetail: { fontSize: 15, lineHeight: 21 },
  foot: { gap: spacing.md },
  small: { fontSize: 14, color: colors.paper3 },
});
