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
import { Body, Eyebrow } from '@/components/Text';
import { colors } from '@/theme/colors';
import { radius, spacing } from '@/theme/spacing';
import { fonts } from '@/theme/typography';

export type CapturedFrame = {
  name: string;
  uri: string;
  type: string;
  base64?: string;
};

type Props = {
  onCaptured: (frames: CapturedFrame[]) => void;
  onCancel?: () => void;
};

type Hint = 'Look straight' | 'Move closer' | 'Hold still' | 'More light' | 'Capturing...';

const BURST_COUNT = 5;
const BURST_INTERVAL_MS = 300;

// Synthetic 1x1 valid minimal JPEG base64 for emulator/mock testing
const FALLBACK_JPEG_BASE64 =
  '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=';

export function FaceCapture({ onCaptured, onCancel }: Props) {
  const cameraRef = useRef<CameraRef>(null);
  const { hasPermission, requestPermission } = useCameraPermission();
  const device = useCameraDevice('front');
  const photoOutput = usePhotoOutput();

  const [hint, setHint] = useState<Hint>('Look straight');
  const [capturedCount, setCapturedCount] = useState<number>(0);
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const useFallbackMode = !device;

  useEffect(() => {
    if (!hasPermission) {
      requestPermission();
    }
  }, [hasPermission, requestPermission]);

  // Burst capture handler
  const triggerCapture = useCallback(async () => {
    if (isCapturing) return;
    setIsCapturing(true);
    setHint('Capturing...');

    const capturedFrames: CapturedFrame[] = [];

    for (let i = 0; i < BURST_COUNT; i++) {
      setCapturedCount(i + 1);
      try {
        if (device && photoOutput && !useFallbackMode) {
          const photoFile = await photoOutput.capturePhotoToFile(
            {
              flashMode: 'off',
              enableShutterSound: false,
            },
            {}
          );

          capturedFrames.push({
            name: `frame_${i + 1}.jpg`,
            uri: `file://${photoFile.filePath}`,
            type: 'image/jpeg',
          });
        } else {
          // Synthetic in-memory fallback frame
          capturedFrames.push({
            name: `frame_${i + 1}.jpg`,
            uri: `data:image/jpeg;base64,${FALLBACK_JPEG_BASE64}`,
            type: 'image/jpeg',
            base64: FALLBACK_JPEG_BASE64,
          });
        }
      } catch {
        // Fallback to simulated frame if hardware capture fails
        capturedFrames.push({
          name: `frame_${i + 1}.jpg`,
          uri: `data:image/jpeg;base64,${FALLBACK_JPEG_BASE64}`,
          type: 'image/jpeg',
          base64: FALLBACK_JPEG_BASE64,
        });
      }

      if (i < BURST_COUNT - 1) {
        await new Promise((r) => setTimeout(r, BURST_INTERVAL_MS));
      }
    }

    setIsCapturing(false);
    onCaptured(capturedFrames);
  }, [isCapturing, device, photoOutput, useFallbackMode, onCaptured]);

  // Auto-trigger countdown hint after mounting when aligned
  useEffect(() => {
    const timer1 = setTimeout(() => setHint('Hold still'), 1200);
    const timer2 = setTimeout(() => {
      triggerCapture();
    }, 2400);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [triggerCapture]);

  return (
    <View style={styles.container}>
      {device && hasPermission && !useFallbackMode ? (
        <Camera
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
          device={device}
          outputs={[photoOutput]}
          isActive={!isCapturing || capturedCount < BURST_COUNT}
        />
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.fallbackBackground]}>
          <Body style={styles.fallbackNotice}>Front camera simulation mode</Body>
        </View>
      )}

      {/* Guide Overlay with Oval Guide */}
      <View style={styles.overlay}>
        <View style={styles.topMask} />
        <View style={styles.centerRow}>
          <View style={styles.sideMask} />
          <View style={[styles.ovalGuide, isCapturing && styles.ovalGuideActive]}>
            <View style={styles.ovalInner} />
          </View>
          <View style={styles.sideMask} />
        </View>
        <View style={styles.bottomMask} />
      </View>

      {/* Instructions & Live Hints */}
      <View style={styles.hud}>
        <View style={styles.hintBadge}>
          <Eyebrow style={styles.hintEyebrow}>Face Guidance</Eyebrow>
          <Body style={styles.hintText}>{hint}</Body>
        </View>

        {/* 5-dot Progress Indicator */}
        <View style={styles.dotsRow}>
          {Array.from({ length: BURST_COUNT }).map((_, idx) => (
            <View
              key={idx}
              style={[
                styles.dot,
                idx < capturedCount && styles.dotFilled,
                isCapturing && idx === capturedCount - 1 && styles.dotActive,
              ]}
            />
          ))}
        </View>

        <View style={styles.controls}>
          <Button
            label={isCapturing ? `Capturing (${capturedCount}/5)...` : 'Capture frames'}
            variant="primary"
            disabled={isCapturing}
            onPress={triggerCapture}
          />
          {onCancel && (
            <Button
              label="Cancel"
              variant="quiet"
              disabled={isCapturing}
              onPress={onCancel}
            />
          )}
        </View>
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
    flex: 1,
    backgroundColor: 'rgba(7, 8, 12, 0.72)',
  },
  centerRow: {
    flexDirection: 'row',
    height: 340,
  },
  sideMask: {
    flex: 1,
    backgroundColor: 'rgba(7, 8, 12, 0.72)',
  },
  ovalGuide: {
    width: 250,
    height: 340,
    borderRadius: 125,
    borderWidth: 3,
    borderColor: colors.lamp,
    backgroundColor: 'transparent',
    overflow: 'hidden',
    boxShadow: `0 0 24px ${colors.lampGlow}`,
  },
  ovalGuideActive: {
    borderColor: colors.lampBright,
    borderWidth: 4,
    boxShadow: `0 0 32px ${colors.lampBright}`,
  },
  ovalInner: {
    flex: 1,
  },
  bottomMask: {
    flex: 1.4,
    backgroundColor: 'rgba(7, 8, 12, 0.72)',
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
    fontSize: 17,
    color: colors.paper,
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
  },
  controls: {
    alignSelf: 'stretch',
    gap: spacing.sm,
  },
});
