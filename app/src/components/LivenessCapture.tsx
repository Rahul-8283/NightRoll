import type { ComponentType } from 'react';

import { CameraUnavailable } from '@/components/CameraUnavailable';
import type { ChallengeRecord, FrameRecord } from '@/marking/envelope';
import type { ChallengeActionType } from '@/modules/face-detector';

export type LivenessCaptureProps = {
  challengeActions: ChallengeActionType[];
  onComplete: (data: { challenge: ChallengeRecord[]; frames: FrameRecord[] }) => void;
  onCancel?: () => void;
};

// See FaceCapture: the camera is loaded only where the native module exists.
let Camera: ComponentType<LivenessCaptureProps> | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  Camera = require('./camera/LivenessCaptureCamera').LivenessCaptureCamera;
} catch {
  Camera = null;
}

export function LivenessCapture(props: LivenessCaptureProps) {
  if (Camera) {
    return <Camera {...props} />;
  }
  return (
    <CameraUnavailable
      title="Marking needs the NightRoll build"
      detail="Expo Go has no camera module. Install the NightRoll development build on an Android phone to mark attendance."
      onCancel={props.onCancel}
    />
  );
}
