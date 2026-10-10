import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import * as DeviceKey from '@/modules/device-key';
import { clearEnrollment, getEnrollment } from '@/state/enrollment';
import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

type KeyInfo =
  | { kind: 'available'; securityLevel: DeviceKey.SecurityLevel; hasKey: boolean }
  | { kind: 'unavailable'; message: string };

const DEV_BUILD_NEEDED: KeyInfo = {
  kind: 'unavailable',
  message: 'Device key info needs a development build.',
};

export default function SettingsScreen() {
  const [roomNumber, setRoomNumber] = useState<string | null>(null);
  const [keyInfo, setKeyInfo] = useState<KeyInfo | null>(() => (DeviceKey.isAvailable() ? null : DEV_BUILD_NEEDED));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void getEnrollment().then((enrollment) => setRoomNumber(enrollment?.roomNumber ?? null));

    if (!DeviceKey.isAvailable()) {
      return;
    }
    void (async () => {
      try {
        const [hasKey, securityLevel] = await Promise.all([DeviceKey.exists(), DeviceKey.securityLevel()]);
        setKeyInfo({ kind: 'available', hasKey, securityLevel });
      } catch (error) {
        setKeyInfo({ kind: 'unavailable', message: error instanceof Error ? error.message : 'Unknown error' });
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
    <View style={styles.container}>
      <Text style={styles.title}>Settings</Text>

      <View style={styles.row}>
        <Text style={styles.label}>Room</Text>
        <Text style={styles.value}>{roomNumber ?? 'Not enrolled'}</Text>
      </View>

      <View style={styles.row}>
        <Text style={styles.label}>Device key</Text>
        {keyInfo === null && <ActivityIndicator />}
        {keyInfo?.kind === 'available' && (
          <Text style={styles.value}>
            {keyInfo.hasKey ? `Present (${keyInfo.securityLevel})` : 'Not generated'}
          </Text>
        )}
        {keyInfo?.kind === 'unavailable' && <Text style={styles.valueMuted}>{keyInfo.message}</Text>}
      </View>

      {keyInfo?.kind === 'available' && keyInfo.securityLevel === 'software' && (
        <Text style={styles.warning}>
          This phone has no secure hardware for the key. It still works, but is weaker proof.
        </Text>
      )}

      <Pressable style={styles.dangerButton} onPress={reEnroll} disabled={busy}>
        <Text style={styles.dangerButtonText}>{busy ? 'Working…' : 'Re-enroll this device'}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: spacing.lg, gap: spacing.md },
  title: { fontSize: 24, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  label: { fontSize: 15, color: colors.muted },
  value: { fontSize: 15, color: colors.text, fontWeight: '600' },
  valueMuted: { fontSize: 13, color: colors.muted, flex: 1, textAlign: 'right' },
  warning: { fontSize: 13, color: colors.warning },
  dangerButton: {
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: 10,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  dangerButtonText: { color: colors.danger, fontSize: 16, fontWeight: '600' },
});
