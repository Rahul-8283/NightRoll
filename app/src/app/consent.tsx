import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';

import { Button } from '@/components/Button';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { Wordmark } from '@/components/Wordmark';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';

export const CURRENT_CONSENT_VERSION = '2026.1';

const DETAILS = [
  {
    title: 'What is collected',
    body: 'A numeric face template (mathematical vector), your phone’s Keystore public key, and nearby Wi-Fi network names and signal strengths.',
  },
  {
    title: 'What is never kept',
    body: 'Your enrollment photos are never stored. Frames are processed in memory and discarded immediately after template extraction.',
  },
  {
    title: 'Retention period',
    body: 'Nightly verification frames are stored in an encrypted audit bucket and permanently deleted after 24 hours.',
  },
  {
    title: 'Who can see your attendance',
    body: 'Only the hostel warden and administration can view your attendance records and room status.',
  },
  {
    title: 'Always voluntary',
    body: 'The ground-floor scanner remains available to anyone who does not wish to use the app.',
  },
];

export default function ConsentScreen() {
  const [agreed, setAgreed] = useState(false);

  return (
    <Screen edges={['top', 'bottom']} contentStyle={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Wordmark size={24} />

        <View style={styles.header}>
          <Eyebrow>Privacy & Consent</Eyebrow>
          <Display>How NightRoll works</Display>
          <Body style={styles.subtext}>
            Please review the plain-language privacy summary before enrolling your device.
          </Body>
        </View>

        <View style={styles.card}>
          {DETAILS.map((item) => (
            <View key={item.title} style={styles.item}>
              <Body style={styles.itemTitle}>{item.title}</Body>
              <Body style={styles.itemBody}>{item.body}</Body>
            </View>
          ))}
        </View>

        <Pressable
          style={styles.checkboxRow}
          onPress={() => setAgreed(!agreed)}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: agreed }}
        >
          <View style={[styles.checkbox, agreed && styles.checkboxActive]}>
            {agreed && <View style={styles.checkboxMark} />}
          </View>
          <Body style={styles.checkboxLabel}>
            I have read and agree to these terms. (Version {CURRENT_CONSENT_VERSION})
          </Body>
        </Pressable>

        <View style={styles.actions}>
          <Button
            label="I agree"
            variant="primary"
            disabled={!agreed}
            onPress={() => router.push('/enroll')}
          />
          <Button
            label="Back"
            variant="quiet"
            onPress={() => router.back()}
          />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { gap: spacing.lg, paddingBottom: spacing.xl },
  header: { gap: spacing.xs },
  subtext: { color: colors.paper2, fontSize: 15, lineHeight: 22 },
  card: {
    backgroundColor: colors.ink2,
    borderWidth: 1,
    borderColor: colors.lineSoft,
    borderRadius: radius.card,
    padding: spacing.lg,
    gap: spacing.md,
  },
  item: { gap: spacing.xs },
  itemTitle: { fontFamily: fonts.bodySemi, color: colors.paper, fontSize: 16 },
  itemBody: { color: colors.paper2, fontSize: 14, lineHeight: 20 },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.xs,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.line,
    backgroundColor: colors.ink3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxActive: {
    borderColor: colors.lamp,
    backgroundColor: colors.lampWash,
  },
  checkboxMark: {
    width: 12,
    height: 12,
    borderRadius: 3,
    backgroundColor: colors.lamp,
  },
  checkboxLabel: { flex: 1, fontSize: 14, color: colors.paper },
  actions: { gap: spacing.sm, marginTop: spacing.sm },
});
