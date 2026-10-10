import { Link, router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import type { AttendanceStatus } from '@/api/attendance';
import { formatClockTime } from '@/attendance/format';
import { useAttendanceStatus } from '@/attendance/useAttendanceStatus';
import { Button } from '@/components/Button';
import { RoomWindow, type WindowLight } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { Wordmark } from '@/components/Wordmark';
import { config } from '@/config';
import { getEnrollment } from '@/state/enrollment';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';

type View_ = {
  light: WindowLight;
  glow: 'lamp' | 'moon';
  eyebrow: string;
  headline: string;
  detail: string;
  canMark: boolean;
};

function describe(status: AttendanceStatus | null): View_ {
  if (!status) {
    return {
      light: 'dark',
      glow: 'moon',
      eyebrow: 'No status yet',
      headline: 'Nothing to show',
      detail: 'Connect to the hostel Wi-Fi and try again.',
      canMark: false,
    };
  }
  switch (status.state) {
    case 'open':
      return {
        light: 'waiting',
        glow: 'lamp',
        eyebrow: 'Open now',
        headline: 'Attendance is open',
        detail: `Closes at ${formatClockTime(status.closes_at)}.`,
        canMark: true,
      };
    case 'scheduled':
      return {
        light: 'moon',
        glow: 'moon',
        eyebrow: 'Later tonight',
        headline: `Opens at ${formatClockTime(status.opens_at)}`,
        detail: 'Open NightRoll then to mark attendance.',
        canMark: false,
      };
    case 'marked':
      return {
        light: 'lit',
        glow: 'lamp',
        eyebrow: 'Done',
        headline: 'Marked present',
        detail: 'Nothing more to do tonight.',
        canMark: false,
      };
    case 'pending':
      return {
        light: 'moon',
        glow: 'moon',
        eyebrow: 'In review',
        headline: 'With the warden',
        detail: 'Your attendance is being checked by the warden.',
        canMark: false,
      };
    case 'off':
      return {
        light: 'dark',
        glow: 'moon',
        eyebrow: 'Off day',
        headline: 'No attendance tonight',
        detail: 'The warden has marked tonight as an off day.',
        canMark: false,
      };
    case 'closed':
      return {
        light: 'dark',
        glow: 'moon',
        eyebrow: 'Closed',
        headline: 'Tonight’s window has closed',
        detail: 'If you have not marked, see the warden.',
        canMark: false,
      };
  }
}

export default function HomeScreen() {
  const [studentId, setStudentId] = useState<string | null>(null);
  const [roomNumber, setRoomNumber] = useState<string | null>(null);
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
      setRoomNumber(enrollment.roomNumber);
      setCheckingEnrollment(false);
    });
  }, []);

  const { status, loading, isOffline, asOf, refresh } = useAttendanceStatus(studentId);
  const waiting = checkingEnrollment || (loading && !status);
  const view = describe(status);

  return (
    <Screen
      glow={waiting ? 'moon' : view.glow}
      edges={['top', 'bottom']}
      contentStyle={styles.content}
    >
      <View style={styles.topBar}>
        <Wordmark />
        <Link href="/settings" asChild>
          <Pressable accessibilityRole="link" hitSlop={12}>
            <Eyebrow style={styles.settings}>Settings</Eyebrow>
          </Pressable>
        </Link>
      </View>

      <View style={styles.centre}>
        {waiting ? (
          <>
            <RoomWindow light="dark" label="Your room window, dark" />
            <Eyebrow>One moment</Eyebrow>
            <Display>Checking tonight</Display>
          </>
        ) : (
          <>
            <RoomWindow light={view.light} label={`Your room window: ${view.headline}`} />
            <Eyebrow
              style={
                view.light === 'lit' || view.light === 'waiting' ? styles.eyebrowLamp : undefined
              }
            >
              {roomNumber ? `Room ${roomNumber} · ${view.eyebrow}` : view.eyebrow}
            </Eyebrow>
            <Display>{view.headline}</Display>
            <Body style={styles.detail}>{view.detail}</Body>
          </>
        )}
      </View>

      <View style={styles.foot}>
        {!waiting && view.canMark && <Button label="Mark attendance" href="/mark" />}
        {isOffline && (
          <View style={styles.notice}>
            <Body style={styles.noticeText}>
              You are offline. This is the last known status
              {asOf ? `, from ${formatClockTime(asOf)}` : ''}.
            </Body>
            <Button variant="quiet" label="Try again" onPress={refresh} />
          </View>
        )}
        {config.mockStatus && (
          <View style={styles.notice}>
            <Eyebrow style={styles.noticeText}>Sample status · not from the server</Eyebrow>
            <Button variant="quiet" label="Show next sample state" onPress={refresh} />
          </View>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: 'space-between', alignItems: 'stretch', gap: spacing.xl },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  settings: { color: colors.paper2 },
  centre: { alignItems: 'center', gap: spacing.md, paddingVertical: spacing.xl },
  eyebrowLamp: { color: colors.lamp },
  detail: { textAlign: 'center' },
  foot: { gap: spacing.md, minHeight: 52 },
  notice: {
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.card,
    borderWidth: 1,
    borderColor: colors.lineSoft,
    backgroundColor: colors.ink2,
  },
  noticeText: { textAlign: 'center' },
});
