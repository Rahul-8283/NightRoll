export type FaceDetectionResult = {
  success: boolean;
  facesCount: number;
  headEulerAngleY?: number;
  headEulerAngleX?: number;
  headEulerAngleZ?: number;
  leftEyeOpenProbability?: number;
  rightEyeOpenProbability?: number;
  smilingProbability?: number;
  faceAreaRatio?: number;
  brightness?: number;
  sharpness?: number;
  tooDark?: boolean;
  oneFace?: boolean;
  largeEnough?: boolean;
  sharpEnough?: boolean;
  error?: string;
};

export type CompressedFrameResult = {
  uri: string;
  sha256: string;
  width: number;
  height: number;
  sizeBytes: number;
};

export type ChallengeActionType = 'blink' | 'turn_left' | 'turn_right' | 'smile';
