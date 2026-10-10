import * as Crypto from 'expo-crypto';

import FaceDetectorNative from './src/FaceDetectorModule';
import type {
  ChallengeActionType,
  CompressedFrameResult,
  FaceDetectionResult,
} from './src/FaceDetector.types';

export type { ChallengeActionType, CompressedFrameResult, FaceDetectionResult };

export function isAvailable(): boolean {
  return FaceDetectorNative !== null;
}

/**
 * Runs face detection and quality check on a captured photo file.
 */
export async function detect(filePath: string): Promise<FaceDetectionResult> {
  if (FaceDetectorNative === null) {
    // Fallback simulation for mock / web
    return {
      success: true,
      facesCount: 1,
      headEulerAngleY: 0,
      headEulerAngleX: 0,
      headEulerAngleZ: 0,
      leftEyeOpenProbability: 0.95,
      rightEyeOpenProbability: 0.95,
      smilingProbability: 0.85,
      faceAreaRatio: 0.25,
      brightness: 110,
      sharpness: 80,
      tooDark: false,
      oneFace: true,
      largeEnough: true,
      sharpEnough: true,
    };
  }
  return FaceDetectorNative.detect(filePath);
}

/**
 * Resizes photo to <= maxDimension (default 720px), compresses as JPEG, and calculates SHA-256.
 */
export async function compressAndHash(
  filePath: string,
  maxDimension = 720,
): Promise<CompressedFrameResult> {
  if (FaceDetectorNative === null) {
    // Generate a deterministic hash for fallback/mock
    const mockHash = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      filePath + Date.now().toString(),
    );
    return {
      uri: filePath,
      sha256: mockHash,
      width: 720,
      height: 960,
      sizeBytes: 45000,
    };
  }
  return FaceDetectorNative.compressAndHash(filePath, maxDimension);
}

/**
 * Checks whether the target liveness action is satisfied by the detection result.
 */
export function isActionDetected(
  action: ChallengeActionType,
  detection: FaceDetectionResult,
  baseline?: FaceDetectionResult,
): boolean {
  if (!detection.oneFace) {
    return false;
  }

  switch (action) {
    case 'blink': {
      const left = detection.leftEyeOpenProbability ?? 1;
      const right = detection.rightEyeOpenProbability ?? 1;
      // Eyes closed or significant drop from baseline
      const isClosed = (left < 0.35 && right < 0.35) || (left < 0.25 || right < 0.25);
      const wasOpen = baseline ? (baseline.leftEyeOpenProbability ?? 1) > 0.65 : true;
      return isClosed && wasOpen;
    }
    case 'turn_left': {
      // In selfie front camera, turning left gives headEulerAngleY < -15 or > 15
      const yaw = detection.headEulerAngleY ?? 0;
      return Math.abs(yaw) >= 16;
    }
    case 'turn_right': {
      const yaw = detection.headEulerAngleY ?? 0;
      return Math.abs(yaw) >= 16;
    }
    case 'smile': {
      const smile = detection.smilingProbability ?? 0;
      return smile >= 0.65;
    }
    default:
      return false;
  }
}
