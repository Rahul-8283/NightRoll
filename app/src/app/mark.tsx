import { router } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { fetchAttendanceStatus } from '@/api/attendance';
import { Button } from '@/components/Button';
import { LivenessCapture } from '@/components/LivenessCapture';
import { RoomWindow } from '@/components/RoomWindow';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import * as Environment from '@/modules/environment';
import type { ChallengeActionType } from '@/modules/face-detector';
import * as WifiScanner from '@/modules/wifi-scanner';
import {
  buildEnvelope,
  type ChallengeRecord,
  type FrameRecord,
  type WifiRecord,
} from '@/marking/envelope';
import { uploadAttendanceEnvelope } from '@/marking/uploader';
import { getEnrollment } from '@/state/enrollment';
import { colors } from '@/theme/colors';
import { spacing } from '@/theme/spacing';

type FlowStage =
  | 'checking_environment'
  | 'environment_blocked'
  | 'fetching_nonce'
  | 'face_check'
  | 'uploading'
  | 'error';

export default function MarkScreen() {
  const [stage, setStage] = useState<FlowStage>('checking_environment');
  const [retryKey, setRetryKey] = useState<number>(0);
  const [blockingIssue, setBlockingIssue] = useState<{
    code: string;
    message: string;
    instruction: string;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  const [studentId, setStudentId] = useState<string | null>(null);
  const [windowId, setWindowId] = useState<string | null>(null);
  const [nonce, setNonce] = useState<string | null>(null);
  const [challengeActions, setChallengeActions] = useState<ChallengeActionType[]>([
    'blink',
    'turn_left',
  ]);

  // Background Wi-Fi scan promise & result
  const wifiData = useRef<WifiRecord | null>(null);
  const envReport = useRef<Environment.EnvironmentReport | null>(null);

  // Initial environment check and session fetch
  useEffect(() => {
    let active = true;

    async function executeFlow() {
      try {
        const report = await Environment.check();
        if (!active) return;
        envReport.current = report;

        const issue = Environment.getBlockingIssue(report);
        if (issue) {
          setBlockingIssue(issue);
          setStage('environment_blocked');
          return;
        }

        setStage('fetching_nonce');

        const enrollment = await getEnrollment();
        if (!active) return;
        if (!enrollment?.studentId) {
          setErrorMessage('Student not enrolled. Please complete enrollment first.');
          setStage('error');
          return;
        }
        setStudentId(enrollment.studentId);

        // Start background Wi-Fi scan immediately (Task 4.2)
        const wifiScanStartTime = Date.now();
        const wifiScanPromise = (async (): Promise<WifiRecord> => {
          try {
            const [conn, scanRes] = await Promise.all([
              WifiScanner.currentConnection(),
              WifiScanner.scan(),
            ]);

            const scanAgeMs = scanRes.ageSeconds * 1000 + (Date.now() - wifiScanStartTime);

            return {
              connected: {
                bssid: conn.bssid || '00:00:00:00:00:00',
                rssi: conn.rssi || -60,
                band: conn.band || '5GHz',
              },
              scan_age_ms: scanAgeMs,
              scan: scanRes.networks.map((n) => ({
                bssid: n.bssid,
                rssi: n.rssi,
                band: n.band,
              })),
            };
          } catch {
            return {
              connected: { bssid: '00:00:00:00:00:00', rssi: -60, band: '5GHz' },
              scan_age_ms: 0,
              scan: [],
            };
          }
        })();

        // Fetch nonce and challenge from backend
        const status = await fetchAttendanceStatus(enrollment.studentId);
        if (!active) return;
        if (status.state !== 'open') {
          if (status.state === 'marked') {
            router.replace('/result?verdict=PRESENT');
            return;
          }
          setErrorMessage(
            status.state === 'closed'
              ? 'Tonight’s attendance window has closed.'
              : 'Attendance window is not currently open.',
          );
          setStage('error');
          return;
        }

        setWindowId(status.window_id);
        setNonce(status.nonce);

        if (status.challenge && status.challenge.length >= 2) {
          setChallengeActions(status.challenge as ChallengeActionType[]);
        }

        // Store Wi-Fi promise resolver
        wifiScanPromise.then((data) => {
          if (active) wifiData.current = data;
        });

        // Move to liveness & frame capture
        setStage('face_check');
      } catch (err: unknown) {
        if (!active) return;
        setErrorMessage(
          err instanceof Error ? err.message : 'Could not fetch attendance session from server',
        );
        setStage('error');
      }
    }

    void executeFlow();

    return () => {
      active = false;
    };
  }, [retryKey]);

  // Step 3: Handle completion of liveness challenge and frames
  const handleLivenessComplete = useCallback(
    async (captureResult: { challenge: ChallengeRecord[]; frames: FrameRecord[] }) => {
      setStage('uploading');

      try {
        // Run guard checks again just before upload (Task 1.3)
        const envAgain = await Environment.check();
        const midIssue = Environment.getBlockingIssue(envAgain);
        if (midIssue) {
          setBlockingIssue(midIssue);
          setStage('environment_blocked');
          return;
        }

        // Ensure Wi-Fi scan is ready
        let wifi = wifiData.current;
        if (!wifi) {
          const [conn, scanRes] = await Promise.all([
            WifiScanner.currentConnection(),
            WifiScanner.scan(),
          ]);
          wifi = {
            connected: {
              bssid: conn.bssid || '00:00:00:00:00:00',
              rssi: conn.rssi || -60,
              band: conn.band || '5GHz',
            },
            scan_age_ms: scanRes.ageSeconds * 1000,
            scan: scanRes.networks.map((n) => ({
              bssid: n.bssid,
              rssi: n.rssi,
              band: n.band,
            })),
          };
        }

        // Build submission envelope
        const envelope = await buildEnvelope({
          studentId: studentId!,
          windowId: windowId!,
          nonce: nonce!,
          challenge: captureResult.challenge,
          frames: captureResult.frames,
          wifi,
          environment: {
            vpn: envAgain.vpn,
            proxy: envAgain.proxy,
            mock_location: envAgain.mockLocation,
            developer_options: envAgain.developerOptions,
            on_wifi: envAgain.onWifi,
          },
        });

        // Upload to server (with 15s timeout and 1 automatic retry)
        const response = await uploadAttendanceEnvelope(envelope);

        const primaryReason = response.reasons?.[0];
        const reasonCode = primaryReason?.code ?? '';
        const reasonMessage = primaryReason?.message ?? '';
        const markTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        router.replace({
          pathname: '/result',
          params: {
            verdict: response.verdict,
            reasonCode,
            reasonMessage,
            retryAllowed: response.retry_allowed !== false ? 'true' : 'false',
            attemptsLeft: response.attempts_left?.toString() ?? '',
            markTime,
            windowId: windowId ?? '',
          },
        });
      } catch (err: unknown) {
        const errorText =
          err instanceof Error ? err.message : 'Could not reach the hostel server';
        router.replace({
          pathname: '/fallback',
          params: { reason: errorText },
        });
      }
    },
    [studentId, windowId, nonce],
  );

  const handleRetry = () => {
    setBlockingIssue(null);
    setErrorMessage('');
    setStage('checking_environment');
    setRetryKey((k) => k + 1);
  };

  // Environment Blocked View
  if (stage === 'environment_blocked' && blockingIssue) {
    return (
      <Screen glow="ember">
        <RoomWindow light="ember" label="Window not confirmed" />
        <Eyebrow style={styles.eyebrowEmber}>Phone check</Eyebrow>
        <Display>Attendance blocked</Display>
        <Body style={styles.centre}>{blockingIssue.message}</Body>
        <Body style={styles.instruction}>{blockingIssue.instruction}</Body>
        <View style={styles.controls}>
          <Button label="Try again" variant="primary" onPress={handleRetry} />
          <Button label="Back to Home" variant="quiet" href="/" />
        </View>
      </Screen>
    );
  }

  // Error View
  if (stage === 'error') {
    return (
      <Screen glow="ember">
        <RoomWindow light="dark" label="Attendance closed" />
        <Eyebrow style={styles.eyebrowEmber}>Session error</Eyebrow>
        <Display>Unable to mark</Display>
        <Body style={styles.centre}>{errorMessage}</Body>
        <View style={styles.controls}>
          <Button label="Try again" variant="primary" onPress={handleRetry} />
          <Button label="Back to Home" variant="quiet" href="/" />
        </View>
      </Screen>
    );
  }

  // Face Check: Camera & Liveness View
  if (stage === 'face_check') {
    return (
      <LivenessCapture
        challengeActions={challengeActions}
        onComplete={(res) => void handleLivenessComplete(res)}
        onCancel={() => router.back()}
      />
    );
  }

  // Progress Loading State: Checking phone or Uploading
  const progressText =
    stage === 'checking_environment'
      ? 'Checking phone environment...'
      : stage === 'fetching_nonce'
        ? 'Opening attendance session...'
        : 'Sending signed attendance...';

  return (
    <Screen glow="moon">
      <RoomWindow light="waiting" label="Your room window, waiting" />
      <Eyebrow style={styles.eyebrowLamp}>
        {stage === 'uploading' ? 'Sending' : 'Checking phone'}
      </Eyebrow>
      <Display>{progressText}</Display>
      <Body style={styles.centre}>
        {stage === 'uploading'
          ? 'Signing payload with hardware key and uploading frames.'
          : 'Validating network connection and security gates.'}
      </Body>
    </Screen>
  );
}

const styles = StyleSheet.create({
  centre: { textAlign: 'center' },
  instruction: { textAlign: 'center', color: colors.lampBright, fontWeight: '600' },
  eyebrowEmber: { color: colors.ember },
  eyebrowLamp: { color: colors.lamp },
  controls: { width: '100%', gap: spacing.sm, marginTop: spacing.lg },
});
