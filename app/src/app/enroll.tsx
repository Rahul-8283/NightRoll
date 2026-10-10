import { useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { router } from 'expo-router';

import { submitEnrollment, submitRoomFingerprint, type SpotScanInput } from '@/api/enrollment';
import { Button } from '@/components/Button';
import { FaceCapture, type CapturedFrame } from '@/components/FaceCapture';
import { Screen } from '@/components/Screen';
import { Body, Display, Eyebrow } from '@/components/Text';
import { Wordmark } from '@/components/Wordmark';
import * as DeviceKey from '@/modules/device-key';
import * as WifiScanner from '@/modules/wifi-scanner';
import { setEnrollment } from '@/state/enrollment';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';
import { CURRENT_CONSENT_VERSION } from './consent';

type Step = 'CODE_INPUT' | 'FACE_CAPTURE' | 'UPLOADING' | 'PROMPT_ROOM_SCAN' | 'ROOM_SCAN' | 'DONE';

const SPOTS = [
  { index: 0, name: 'The Bed', hint: 'Stand next to your bed.' },
  { index: 1, name: 'The Desk', hint: 'Stand next to your study desk.' },
  { index: 2, name: 'Near the Door', hint: 'Stand near the room door.' },
];

export default function EnrollScreen() {
  const [step, setStep] = useState<Step>('CODE_INPUT');
  const [rollNumber, setRollNumber] = useState('');
  const [code, setCode] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // Enrolled student data
  const [enrolledStudentId, setEnrolledStudentId] = useState('');
  const [enrolledRoomId, setEnrolledRoomId] = useState('');
  const [enrolledRoomNumber, setEnrolledRoomNumber] = useState('');

  // Room scan state
  const [currentSpotIndex, setCurrentSpotIndex] = useState(0);
  const [collectedScans, setCollectedScans] = useState<SpotScanInput[]>([]);
  const [countdown, setCountdown] = useState(0);
  const [locationEnabled, setLocationEnabled] = useState(true);

  // Step 1: Validate inputs and ensure Keystore device key
  const handleProceedToCamera = async () => {
    if (!rollNumber.trim()) {
      setErrorMessage('Please enter your roll number.');
      return;
    }
    if (!code.trim() || code.trim().length !== 8) {
      setErrorMessage('Please enter the 8-character enrollment code from the warden.');
      return;
    }

    setErrorMessage('');
    try {
      const keyExists = await DeviceKey.exists();
      if (!keyExists) {
        await DeviceKey.generate();
      }
      setStep('FACE_CAPTURE');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to prepare device key';
      setErrorMessage(msg);
    }
  };

  // Step 2 & 3: Handle captured face burst and upload
  const handleFramesCaptured = async (frames: CapturedFrame[]) => {
    setStep('UPLOADING');
    setStatusMessage('Preparing device public key and sending frames...');
    setErrorMessage('');

    try {
      let pubKey = await DeviceKey.getPublicKey();
      if (!pubKey) {
        pubKey = await DeviceKey.generate();
      }
      const secLevel = await DeviceKey.securityLevel();

      setStatusMessage('Extracting biometric template on server...');
      const result = await submitEnrollment({
        code: code.trim(),
        rollNumber: rollNumber.trim(),
        publicKey: pubKey,
        keySecurityLevel: secLevel,
        consentVersion: CURRENT_CONSENT_VERSION,
        frames,
      });

      // Save identity locally in SecureStore
      await setEnrollment({
        studentId: result.student_id,
        roomId: result.room_id,
        roomNumber: result.room_number,
      });

      setEnrolledStudentId(result.student_id);
      setEnrolledRoomId(result.room_id);
      setEnrolledRoomNumber(result.room_number);
      setStep('PROMPT_ROOM_SCAN');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Enrollment failed';
      setErrorMessage(msg);
      // Allow student to retake face capture without losing the code
      setStep('CODE_INPUT');
    }
  };

  // Step 4 -> 5: Start Room Scan
  const handleStartRoomScan = async () => {
    const locOn = await WifiScanner.isLocationEnabled();
    setLocationEnabled(locOn);
    setCurrentSpotIndex(0);
    setCollectedScans([]);
    setStep('ROOM_SCAN');
  };

  // Step 5: Execute scan at current spot with 30s countdown
  const handleScanCurrentSpot = async () => {
    try {
      setStatusMessage(`Scanning Wi-Fi at ${SPOTS[currentSpotIndex].name}...`);
      const scanRes = await WifiScanner.scan();

      const newScan: SpotScanInput = {
        networks: scanRes.networks.map((n) => ({
          bssid: n.bssid,
          rssi: n.rssi,
          band: n.band,
        })),
      };

      const updatedScans = [...collectedScans, newScan];
      setCollectedScans(updatedScans);

      if (currentSpotIndex < SPOTS.length - 1) {
        // Wait 30s before next scan due to Android limits
        const nextIndex = currentSpotIndex + 1;
        setCurrentSpotIndex(nextIndex);
        setCountdown(30);

        const interval = setInterval(() => {
          setCountdown((prev) => {
            if (prev <= 1) {
              clearInterval(interval);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      } else {
        // All 3 scans completed, submit to backend
        setStatusMessage('Building room Wi-Fi fingerprint...');
        await submitRoomFingerprint(enrolledRoomId, enrolledStudentId, updatedScans);
        setStep('DONE');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Wi-Fi scan failed';
      Alert.alert('Scan Issue', msg);
    }
  };

  // View: Camera Mode
  if (step === 'FACE_CAPTURE') {
    return (
      <FaceCapture
        onCaptured={handleFramesCaptured}
        onCancel={() => setStep('CODE_INPUT')}
      />
    );
  }

  return (
    <Screen edges={['top', 'bottom']} contentStyle={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Wordmark size={24} />

        {/* Step 1: Code & Roll Input */}
        {step === 'CODE_INPUT' && (
          <View style={styles.section}>
            <View style={styles.header}>
              <Eyebrow>Step 1 of 3</Eyebrow>
              <Display>Enter your code</Display>
              <Body style={styles.subtext}>
                Enter your roll number and the 8-character enrollment code issued by the warden.
              </Body>
            </View>

            {errorMessage ? (
              <View style={styles.errorBanner}>
                <Body style={styles.errorText}>{errorMessage}</Body>
              </View>
            ) : null}

            <View style={styles.form}>
              <View style={styles.inputGroup}>
                <Body style={styles.label}>Roll Number</Body>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. TEST001"
                  placeholderTextColor={colors.paper3}
                  value={rollNumber}
                  onChangeText={setRollNumber}
                  autoCapitalize="characters"
                  autoCorrect={false}
                />
              </View>

              <View style={styles.inputGroup}>
                <Body style={styles.label}>Warden One-Time Code</Body>
                <TextInput
                  style={[styles.input, styles.codeInput]}
                  placeholder="8 characters"
                  placeholderTextColor={colors.paper3}
                  value={code}
                  onChangeText={(val) => setCode(val.toUpperCase())}
                  maxLength={8}
                  autoCapitalize="characters"
                  autoCorrect={false}
                />
              </View>
            </View>

            <View style={styles.actions}>
              <Button label="Continue to Face Capture" variant="primary" onPress={handleProceedToCamera} />
              <Button label="Back" variant="quiet" onPress={() => router.back()} />
            </View>
          </View>
        )}

        {/* Step 3: Uploading */}
        {step === 'UPLOADING' && (
          <View style={[styles.section, styles.centerSection]}>
            <ActivityIndicator size="large" color={colors.lamp} />
            <Display style={styles.centerText}>Enrolling Device</Display>
            <Body style={[styles.subtext, styles.centerText]}>{statusMessage}</Body>
          </View>
        )}

        {/* Step 4: Prompt Room Scan */}
        {step === 'PROMPT_ROOM_SCAN' && (
          <View style={styles.section}>
            <View style={styles.header}>
              <Eyebrow>Face & Key Registered</Eyebrow>
              <Display>Room Wi-Fi Fingerprint</Display>
              <Body style={styles.subtext}>
                You are enrolled in Room {enrolledRoomNumber}. To mark attendance from your bed, NightRoll needs to map your room’s Wi-Fi fingerprint at 3 spots.
              </Body>
            </View>

            <View style={styles.card}>
              <Body style={styles.cardTitle}>3 Quick Measurements</Body>
              <Body style={styles.cardItem}>1. Next to your bed</Body>
              <Body style={styles.cardItem}>2. Next to your desk</Body>
              <Body style={styles.cardItem}>3. Near your room door</Body>
            </View>

            <View style={styles.actions}>
              <Button label="Start room scan now" variant="primary" onPress={handleStartRoomScan} />
              <Button label="Scan my room later" variant="quiet" onPress={() => router.replace('/')} />
            </View>
          </View>
        )}

        {/* Step 5: Room Scan Active */}
        {step === 'ROOM_SCAN' && (
          <View style={styles.section}>
            <View style={styles.header}>
              <Eyebrow>
                Spot {currentSpotIndex + 1} of {SPOTS.length}
              </Eyebrow>
              <Display>{SPOTS[currentSpotIndex].name}</Display>
              <Body style={styles.subtext}>{SPOTS[currentSpotIndex].hint}</Body>
            </View>

            {!locationEnabled && (
              <View style={styles.errorBanner}>
                <Body style={styles.errorText}>
                  Please turn on location in phone settings. Android requires location to detect nearby Wi-Fi networks.
                </Body>
              </View>
            )}

            <View style={styles.card}>
              <Body style={styles.cardTitle}>Scans Collected: {collectedScans.length} / 3</Body>
              {countdown > 0 ? (
                <View style={styles.countdownBox}>
                  <Body style={styles.countdownTitle}>Waiting for Android scan cooldown...</Body>
                  <Display style={styles.countdownNumber}>{countdown}s</Display>
                  <Body style={styles.countdownSub}>Moving to next spot: {SPOTS[currentSpotIndex].name}</Body>
                </View>
              ) : (
                <Body style={styles.cardItem}>Ready to scan {SPOTS[currentSpotIndex].name}. Hold phone steady.</Body>
              )}
            </View>

            <View style={styles.actions}>
              <Button
                label={countdown > 0 ? `Please wait (${countdown}s)` : `Scan ${SPOTS[currentSpotIndex].name}`}
                variant="primary"
                disabled={countdown > 0}
                onPress={handleScanCurrentSpot}
              />
              <Button label="Scan later" variant="quiet" onPress={() => router.replace('/')} />
            </View>
          </View>
        )}

        {/* Step 6: Complete */}
        {step === 'DONE' && (
          <View style={[styles.section, styles.centerSection]}>
            <View style={styles.successIcon}>
              <View style={styles.successInner} />
            </View>
            <Display style={styles.centerText}>Fully Enrolled!</Display>
            <Body style={[styles.subtext, styles.centerText]}>
              Consent recorded, face template stored, device key registered, and room Wi-Fi fingerprint mapped for Room {enrolledRoomNumber}.
            </Body>
            <View style={styles.actions}>
              <Button label="Go to Window" variant="primary" onPress={() => router.replace('/')} />
            </View>
          </View>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { gap: spacing.lg, paddingBottom: spacing.xl },
  section: { gap: spacing.lg },
  centerSection: { alignItems: 'center', justifyContent: 'center', minHeight: 400 },
  header: { gap: spacing.xs },
  subtext: { color: colors.paper2, fontSize: 15, lineHeight: 22 },
  centerText: { textAlign: 'center' },
  form: { gap: spacing.md },
  inputGroup: { gap: spacing.xs },
  label: { fontFamily: fonts.bodySemi, color: colors.paper, fontSize: 14 },
  input: {
    height: 52,
    borderRadius: radius.control,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.ink2,
    paddingHorizontal: spacing.md,
    color: colors.paper,
    fontSize: 16,
    fontFamily: fonts.mono,
  },
  codeInput: {
    letterSpacing: 4,
    fontSize: 20,
    textAlign: 'center',
  },
  errorBanner: {
    backgroundColor: colors.emberWash,
    borderWidth: 1,
    borderColor: colors.ember,
    borderRadius: radius.control,
    padding: spacing.md,
  },
  errorText: { color: colors.ember, fontSize: 14 },
  card: {
    backgroundColor: colors.ink2,
    borderWidth: 1,
    borderColor: colors.lineSoft,
    borderRadius: radius.card,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  cardTitle: { fontFamily: fonts.bodySemi, color: colors.paper, fontSize: 16 },
  cardItem: { color: colors.paper2, fontSize: 14 },
  countdownBox: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    gap: spacing.xs,
  },
  countdownTitle: { color: colors.paper3, fontSize: 13 },
  countdownNumber: { color: colors.lamp, fontSize: 36, fontFamily: fonts.mono },
  countdownSub: { color: colors.paper2, fontSize: 14 },
  successIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.lampWash,
    borderWidth: 2,
    borderColor: colors.lamp,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    boxShadow: `0 0 24px ${colors.lampGlow}`,
  },
  successInner: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.lamp,
  },
  actions: { gap: spacing.sm, marginTop: spacing.md, alignSelf: 'stretch' },
});
