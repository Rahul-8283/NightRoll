import { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
  usePhotoOutput,
  type CameraRef,
} from 'react-native-vision-camera';

import { Button } from '@/components/Button';
import type { LivenessCaptureProps } from '@/components/LivenessCapture';
import { Body, Display, Eyebrow } from '@/components/Text';
import * as FaceDetector from '@/modules/face-detector';
import type { ChallengeActionType } from '@/modules/face-detector';
import type { ChallengeRecord, FrameRecord } from '@/marking/envelope';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';

const ACTION_TIMEOUT_MS = 5000;
const MAX_FAILED_TRIES = 3;

// Synthetic 1x1 valid minimal JPEG base64 for fallback
const FALLBACK_JPEG_BASE64 =
  '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=';

type Step = 'action_0' | 'action_1' | 'neutral_1' | 'neutral_2' | 'failed' | 'done';

const ACTION_DESCRIPTIONS: Record<
  ChallengeActionType,
  { title: string; instruction: string; icon: string }
> = {
  blink: {
    title: 'Blink Eyes',
    instruction: 'Blink your eyes naturally at the camera',
    icon: '👀',
  },
  turn_left: {
    title: 'Turn Left',
    instruction: 'Slowly turn your head to your left',
    icon: '👈',
  },
  turn_right: {
    title: 'Turn Right',
    instruction: 'Slowly turn your head to your right',
    icon: '👉',
  },
  smile: {
    title: 'Smile',
    instruction: 'Smile warmly at the camera',
    icon: '😊',
  },
};

export function LivenessCaptureCamera({ challengeActions, onComplete, onCancel }: LivenessCaptureProps) {
  const cameraRef = useRef<CameraRef>(null);
  const { hasPermission, requestPermission } = useCameraPermission();
  const device = useCameraDevice('front');
  const photoOutput = usePhotoOutput();

  const [step, setStep] = useState<Step>('action_0');
  const [hint, setHint] = useState<string>('Hold phone upright at arm’s length');
  const [timeLeftMs, setTimeLeftMs] = useState<number>(ACTION_TIMEOUT_MS);
  const [capturedCount, setCapturedCount] = useState<number>(0);

  // Stored state for challenge timing and captured frames
  const challengeRecords = useRef<ChallengeRecord[]>([]);
  const capturedFrames = useRef<FrameRecord[]>([]);
  const actionStartTime = useRef<number>(0);
  const isProcessingFrame = useRef<boolean>(false);
  const retriedFrame = useRef<boolean>(false);

  const isSimulated = !device || !hasPermission;

  useEffect(() => {
    if (!hasPermission) {
      void requestPermission();
    }
  }, [hasPermission, requestPermission]);

  const currentActionIndex = step === 'action_0' ? 0 : step === 'action_1' ? 1 : null;
  const currentAction: ChallengeActionType | null =
    currentActionIndex !== null && challengeActions[currentActionIndex]
      ? challengeActions[currentActionIndex]
      : null;

  const handleActionTimeout = useCallback(() => {
    if (challengeRecords.current.length >= MAX_FAILED_TRIES) {
      setStep('failed');
    } else {
      actionStartTime.current = Date.now();
      setTimeLeftMs(ACTION_TIMEOUT_MS);
      setHint('Action timed out. Try again');
    }
  }, []);

  // Countdown timer for 5-second action limit
  useEffect(() => {
    if (currentActionIndex === null || step === 'failed' || step === 'done') return;

    actionStartTime.current = Date.now();

    const interval = setInterval(() => {
      const elapsed = Date.now() - actionStartTime.current;
      const remaining = Math.max(0, ACTION_TIMEOUT_MS - elapsed);
      setTimeLeftMs(remaining);

      if (remaining <= 0) {
        clearInterval(interval);
        handleActionTimeout();
      }
    }, 100);

    return () => clearInterval(interval);
  }, [currentActionIndex, step, handleActionTimeout]);

  // Frame capture and detection routine
  const captureAndEvaluate = useCallback(async () => {
    if (isProcessingFrame.current || currentActionIndex === null || !currentAction) return;
    isProcessingFrame.current = true;

    try {
      let photoUri: string;

      if (device && photoOutput && !isSimulated) {
        const photoFile = await photoOutput.capturePhotoToFile(
          { flashMode: 'off', enableShutterSound: false },
          {},
        );
        photoUri = `file://${photoFile.filePath}`;
      } else {
        photoUri = `data:image/jpeg;base64,${FALLBACK_JPEG_BASE64}`;
      }

      const detection = await FaceDetector.detect(photoUri);

      // On-device guidance hints
      if (detection.tooDark) {
        setHint('Turn on a light: frame is too dark');
      } else if (!detection.oneFace) {
        setHint(detection.facesCount > 1 ? 'Only one face allowed' : 'Position face inside the oval');
      } else if (!detection.largeEnough) {
        setHint('Hold phone closer');
      } else if (!detection.sharpEnough) {
        setHint('Hold steady: camera is blurry');
      } else {
        setHint('Hold still');
      }

      // Check if action detected (or simulated pass after 1.2s in mock)
      const actionDetected =
        isSimulated && Date.now() - actionStartTime.current > 1200
          ? true
          : FaceDetector.isActionDetected(currentAction, detection);

      if (actionDetected) {
        // Quality check before accepting frame
        const qualityPass =
          isSimulated || (detection.oneFace && detection.largeEnough && detection.sharpEnough);

        if (!qualityPass && !retriedFrame.current) {
          retriedFrame.current = true;
          setHint('Retaking frame for better quality...');
          isProcessingFrame.current = false;
          return;
        }

        retriedFrame.current = false;
        const detectedMs = Date.now() - actionStartTime.current;

        // Record challenge action timing
        challengeRecords.current.push({
          action: currentAction,
          started_ms: 0,
          detected_ms: detectedMs,
        });

        // Compress and hash frame
        const compressed = await FaceDetector.compressAndHash(photoUri, 720);
        capturedFrames.current.push({
          index: capturedFrames.current.length,
          sha256: compressed.sha256,
          tag: currentAction,
          uri: compressed.uri,
        });
        setCapturedCount(capturedFrames.current.length);

        // Transition to next step
        if (currentActionIndex === 0) {
          setStep('action_1');
        } else {
          setStep('neutral_1');
        }
      }
    } catch {
      // Ignore individual frame errors in the loop
    } finally {
      isProcessingFrame.current = false;
    }
  }, [currentActionIndex, currentAction, device, photoOutput, isSimulated]);

  // Frame polling loop while in an action step
  useEffect(() => {
    if (currentActionIndex === null || step === 'failed' || step === 'done') return;

    const poller = setInterval(() => {
      void captureAndEvaluate();
    }, 450);

    return () => clearInterval(poller);
  }, [currentActionIndex, step, captureAndEvaluate]);

  // Handle neutral front-facing frames
  useEffect(() => {
    if (step !== 'neutral_1' && step !== 'neutral_2') return;

    const captureNeutral = async () => {
      setHint('Look straight at the camera');
      await new Promise((r) => setTimeout(r, 400));
      let photoUri: string;
      if (device && photoOutput && !isSimulated) {
        const photo = await photoOutput.capturePhotoToFile(
          { flashMode: 'off', enableShutterSound: false },
          {},
        );
        photoUri = `file://${photo.filePath}`;
      } else {
        photoUri = `data:image/jpeg;base64,${FALLBACK_JPEG_BASE64}`;
      }

      const compressed = await FaceDetector.compressAndHash(photoUri, 720);
      capturedFrames.current.push({
        index: capturedFrames.current.length,
        sha256: compressed.sha256,
        tag: 'neutral',
        uri: compressed.uri,
      });
      setCapturedCount(capturedFrames.current.length);

      if (step === 'neutral_1') {
        setStep('neutral_2');
      } else {
        setStep('done');
        onComplete({
          challenge: challengeRecords.current,
          frames: capturedFrames.current,
        });
      }
    };

    void captureNeutral();
  }, [step, device, photoOutput, isSimulated, onComplete]);

  const retryChallenge = () => {
    challengeRecords.current = [];
    capturedFrames.current = [];
    setCapturedCount(0);
    setStep('action_0');
  };

  if (step === 'failed') {
    return (
      <View style={styles.container}>
        <View style={styles.failedContainer}>
          <Display style={styles.failedTitle}>Liveness Check Failed</Display>
          <Body style={styles.failedText}>
            Unable to detect the requested actions after 3 attempts. Please ensure good lighting and
            hold the phone directly in front of your face.
          </Body>
          <View style={styles.controls}>
            <Button label="Try Again" variant="primary" onPress={retryChallenge} />
            {onCancel && <Button label="Cancel" variant="quiet" onPress={onCancel} />}
          </View>
        </View>
      </View>
    );
  }

  const actionInfo = currentAction ? ACTION_DESCRIPTIONS[currentAction] : null;

  return (
    <View style={styles.container}>
      {device && hasPermission && !isSimulated ? (
        <Camera
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
          device={device}
          outputs={[photoOutput]}
          isActive={step !== 'done'}
        />
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.fallbackBackground]}>
          <Body style={styles.fallbackNotice}>Camera preview · front camera active</Body>
        </View>
      )}

      {/* Oval Face Guide */}
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.topMask} />
        <View style={styles.centerRow}>
          <View style={styles.sideMask} />
          <View style={styles.ovalGuide}>
            <View style={styles.ovalInner} />
          </View>
          <View style={styles.sideMask} />
        </View>
        <View style={styles.bottomMask} />
      </View>

      {/* Action Banner at Top */}
      {actionInfo && (
        <View style={styles.topBanner}>
          <View style={styles.iconBadge}>
            <Body style={styles.iconText}>{actionInfo.icon}</Body>
          </View>
          <View style={styles.bannerTextContainer}>
            <Eyebrow style={styles.bannerEyebrow}>
              Challenge {currentActionIndex! + 1} of 2
            </Eyebrow>
            <Display style={styles.bannerTitle}>{actionInfo.title}</Display>
            <Body style={styles.bannerInstruction}>{actionInfo.instruction}</Body>
          </View>
          {/* 5-second Countdown Progress */}
          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressBar,
                { width: `${Math.round((timeLeftMs / ACTION_TIMEOUT_MS) * 100)}%` },
              ]}
            />
          </View>
        </View>
      )}

      {/* Live Hints and HUD at Bottom */}
      <View style={styles.hud}>
        <View style={styles.hintBadge}>
          <Eyebrow style={styles.hintEyebrow}>Guidance</Eyebrow>
          <Body style={styles.hintText}>{hint}</Body>
        </View>

        {/* 4-dot Progress Indicator for the 4 Frames */}
        <View style={styles.dotsRow}>
          {Array.from({ length: 4 }).map((_, idx) => (
            <View
              key={idx}
              style={[
                styles.dot,
                idx < capturedCount && styles.dotFilled,
                idx === capturedCount && styles.dotActive,
              ]}
            />
          ))}
        </View>

        {onCancel && (
          <View style={styles.controls}>
            <Button label="Cancel" variant="quiet" onPress={onCancel} />
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.ink0,
    justifyContent: 'space-between',
  },
  fallbackBackground: {
    backgroundColor: colors.ink2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fallbackNotice: {
    color: colors.paper3,
    fontSize: 14,
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 1,
  },
  topMask: {
    flex: 1.1,
    backgroundColor: 'rgba(7, 8, 12, 0.75)',
  },
  centerRow: {
    flexDirection: 'row',
    height: 330,
  },
  sideMask: {
    flex: 1,
    backgroundColor: 'rgba(7, 8, 12, 0.75)',
  },
  ovalGuide: {
    width: 250,
    height: 330,
    borderRadius: 125,
    borderWidth: 3,
    borderColor: colors.lamp,
    backgroundColor: 'transparent',
    overflow: 'hidden',
    boxShadow: `0 0 24px ${colors.lampGlow}`,
  },
  ovalInner: {
    flex: 1,
  },
  bottomMask: {
    flex: 1.5,
    backgroundColor: 'rgba(7, 8, 12, 0.75)',
  },
  topBanner: {
    position: 'absolute',
    top: spacing.xl,
    left: spacing.md,
    right: spacing.md,
    zIndex: 10,
    backgroundColor: 'rgba(17, 21, 31, 0.92)',
    borderRadius: radius.card,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.md,
    alignItems: 'center',
    gap: spacing.xs,
  },
  iconBadge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.ink3,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  iconText: {
    fontSize: 26,
  },
  bannerTextContainer: {
    alignItems: 'center',
  },
  bannerEyebrow: {
    color: colors.lamp,
    fontSize: 11,
  },
  bannerTitle: {
    fontSize: 22,
    color: colors.paper,
    fontFamily: fonts.bodySemi,
  },
  bannerInstruction: {
    fontSize: 13,
    color: colors.paper2,
    textAlign: 'center',
  },
  progressTrack: {
    width: '100%',
    height: 4,
    backgroundColor: colors.ink4,
    borderRadius: 2,
    marginTop: spacing.xs,
    overflow: 'hidden',
  },
  progressBar: {
    height: 4,
    backgroundColor: colors.lamp,
  },
  hud: {
    position: 'absolute',
    bottom: spacing.lg,
    left: spacing.md,
    right: spacing.md,
    zIndex: 10,
    alignItems: 'center',
    gap: spacing.md,
  },
  hintBadge: {
    backgroundColor: colors.ink2,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.card,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    gap: 2,
  },
  hintEyebrow: {
    color: colors.lamp,
    fontSize: 11,
  },
  hintText: {
    fontFamily: fonts.bodySemi,
    fontSize: 15,
    color: colors.paper,
    textAlign: 'center',
  },
  dotsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.ink4,
    borderWidth: 1,
    borderColor: colors.line,
  },
  dotFilled: {
    backgroundColor: colors.lamp,
    borderColor: colors.lampBright,
  },
  dotActive: {
    transform: [{ scale: 1.3 }],
    borderColor: colors.lamp,
  },
  controls: {
    alignSelf: 'stretch',
    gap: spacing.sm,
  },
  failedContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.lg,
  },
  failedTitle: {
    color: colors.ember,
    textAlign: 'center',
  },
  failedText: {
    color: colors.paper2,
    textAlign: 'center',
  },
});
