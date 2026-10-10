import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { Button } from '@/components/Button';
import { Screen } from '@/components/Screen';
import { Body, Eyebrow } from '@/components/Text';

import * as DeviceKey from '@/modules/device-key';
import { clearEnrollment, getEnrollment } from '@/state/enrollment';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';

type KeyInfo =
  | { kind: 'available'; securityLevel: DeviceKey.SecurityLevel; hasKey: boolean }
  | { kind: 'unavailable'; message: string };

const DEV_BUILD_NEEDED: KeyInfo = {
  kind: 'unavailable',
  message: 'Device key info needs a development build.',
};

export default function SettingsScreen() {
  const [roomNumber, setRoomNumber] = useState<string | null>(null);
  const [keyInfo, setKeyInfo] = useState<KeyInfo | null>(() =>
    DeviceKey.isAvailable() ? null : DEV_BUILD_NEEDED,
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void getEnrollment().then((enrollment) => setRoomNumber(enrollment?.roomNumber ?? null));

    if (!DeviceKey.isAvailable()) {
      return;
    }
    void (async () => {
      try {
        const [hasKey, securityLevel] = await Promise.all([
          DeviceKey.exists(),
          DeviceKey.securityLevel(),
        ]);
        setKeyInfo({ kind: 'available', hasKey, securityLevel });
      } catch (error) {
        setKeyInfo({
          kind: 'unavailable',
          message: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    })();
  }, []);

  const reEnroll = async () => {
    setBusy(true);
    try {
      if (DeviceKey.isAvailable() && (await DeviceKey.exists())) {
        await DeviceKey.deleteKey();
      }
      await clearEnrollment();
      router.replace('/welcome');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen glow="moon" contentStyle={styles.content}>
      <View style={styles.card}>
        <View style={styles.row}>
          <Eyebrow>Room</Eyebrow>
          <Body style={styles.value}>{roomNumber ?? 'Not enrolled'}</Body>
        </View>

        <View style={[styles.row, styles.rowLast]}>
          <Eyebrow>Device key</Eyebrow>
          {keyInfo === null && <ActivityIndicator color={colors.lamp} />}
          {keyInfo?.kind === 'available' && (
            <Body style={styles.value}>
              {keyInfo.hasKey ? `Present (${keyInfo.securityLevel})` : 'Not generated'}
            </Body>
          )}
          {keyInfo?.kind === 'unavailable' && (
            <Body style={styles.valueMuted}>{keyInfo.message}</Body>
          )}
        </View>
      </View>

      {keyInfo?.kind === 'available' && keyInfo.securityLevel === 'software' && (
        <Body style={styles.warning}>
          This phone has no secure hardware for the key. It still works, but is weaker proof.
        </Body>
      )}

      <View style={styles.danger}>
        <Body>
          Re-enrolling removes this phone’s key and your room details. You will need a new code from
          the warden.
        </Body>
        <Button
          variant="danger"
          label={busy ? 'Working…' : 'Re-enroll this device'}
          onPress={reEnroll}
          disabled={busy}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: 'flex-start', alignItems: 'stretch', gap: spacing.lg },
  card: {
    paddingHorizontal: spacing.lg,
    borderRadius: radius.card,
    borderWidth: 1,
    borderColor: colors.lineSoft,
    backgroundColor: colors.ink2,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSoft,
  },
  rowLast: { borderBottomWidth: 0 },
  value: { fontFamily: fonts.bodySemi, color: colors.paper },
  valueMuted: { flex: 1, textAlign: 'right', fontSize: 14, lineHeight: 20, color: colors.paper3 },
  warning: { color: colors.lamp },
  danger: { gap: spacing.md, marginTop: spacing.md },
});
