import { requireNativeModule } from 'expo-modules-core';
import { Platform } from 'react-native';

import type { CompressedFrameResult, FaceDetectionResult } from './FaceDetector.types';

type FaceDetectorNativeType = {
  detect(filePath: string): Promise<FaceDetectionResult>;
  compressAndHash(filePath: string, maxDimension: number): Promise<CompressedFrameResult>;
};

let FaceDetectorNative: FaceDetectorNativeType | null = null;
if (Platform.OS !== 'web') {
  try {
    FaceDetectorNative = requireNativeModule<FaceDetectorNativeType>('FaceDetector');
  } catch {
    FaceDetectorNative = null;
  }
}

export default FaceDetectorNative;
