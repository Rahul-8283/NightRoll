import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { formatClockTime } from '@/attendance/format';
import { useAttendanceStatus } from '@/attendance/useAttendanceStatus';
import { config } from '@/config';
import { getEnrollment } from '@/state/enrollment';
import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

export default function HomeScreen() {
  const [studentId, setStudentId] = useState<string | null>(null);
  const [checkingEnrollment, setCheckingEnrollment] = useState(!config.mockStatus);

  useEffect(() => {
    if (config.mockStatus) {
      return;
    }
    void getEnrollment().then((enrollment) => {
      if (!enrollment) {
        router.replace('/welcome');
        return;
      }
      setStudentId(enrollment.studentId);
      setCheckingEnrollment(false);
    });
  }, []);

  const { status, loading, isOffline, asOf, refresh } = useAttendanceStatus(studentId);

  if (checkingEnrollment || (loading && !status)) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>NightRoll</Text>
        <Text style={styles.note}>Loading tonight&apos;s status…</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>NightRoll</Text>
      <StatusBody status={status} />
      {isOffline && (
        <View style={styles.offlineBox}>
          <Text style={styles.offlineText}>
            Offline. Showing the last known status{asOf ? ` from ${formatClockTime(asOf)}` : ''}.
          </Text>
          <Pressable onPress={refresh} style={styles.retryButton}>
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

function StatusBody({ status }: { status: ReturnType<typeof useAttendanceStatus>['status'] }) {
  if (!status) {
    return <Text style={styles.note}>No status yet. Pull to retry once you have a connection.</Text>;
  }

  switch (status.state) {
    case 'open':
      return (
        <>
          <Text style={styles.note}>Attendance is open until {formatClockTime(status.closes_at)}.</Text>
          <Pressable style={styles.markButton} onPress={() => router.push('/mark')}>
            <Text style={styles.markButtonText}>Mark attendance</Text>
          </Pressable>
        </>
      );
    case 'scheduled':
      return (
        <Text style={styles.note}>
          Attendance opens at {formatClockTime(status.opens_at)}. Open NightRoll then.
        </Text>
      );
    case 'marked':
      return <Text style={styles.note}>Marked present tonight.</Text>;
    case 'pending':
      return <Text style={styles.note}>Your attendance is with the warden for review.</Text>;
    case 'off':
      return <Text style={styles.note}>Tonight is an off day. No attendance window is open.</Text>;
    case 'closed':
      return (
        <Text style={styles.note}>
          Tonight&apos;s window has closed. If you have not marked, see the warden.
        </Text>
      );
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.md },
  title: { fontSize: 28, fontWeight: '700', color: colors.text },
  note: { fontSize: 16, color: colors.muted, textAlign: 'center' },
  markButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: 12,
  },
  markButtonText: { color: '#fff', fontSize: 17, fontWeight: '600' },
  offlineBox: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: spacing.md,
    alignItems: 'center',
    gap: spacing.sm,
  },
  offlineText: { color: colors.warning, textAlign: 'center' },
  retryButton: { paddingVertical: spacing.xs, paddingHorizontal: spacing.md },
  retryText: { color: colors.primary, fontWeight: '600' },
});
