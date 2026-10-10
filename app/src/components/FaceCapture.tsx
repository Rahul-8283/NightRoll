import type { ComponentType } from 'react';

import { CameraUnavailable } from '@/components/CameraUnavailable';

export type CapturedFrame = {
  name: string;
  uri: string;
  type: string;
  base64?: string;
};

export type FaceCaptureProps = {
  onCaptured: (frames: CapturedFrame[]) => void;
  onCancel?: () => void;
};

// The camera is a native module. Expo Go does not contain it, and importing it there throws, which would
// take the whole app down at launch. Load it only if it exists.
let Camera: ComponentType<FaceCaptureProps> | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  Camera = require('./camera/FaceCaptureCamera').FaceCaptureCamera;
} catch {
  Camera = null;
}

export function FaceCapture(props: FaceCaptureProps) {
  if (Camera) {
    return <Camera {...props} />;
  }
  return (
    <CameraUnavailable
      title="Enrollment needs the NightRoll build"
      detail="Expo Go has no camera module or device key. Install the NightRoll development build on an Android phone to enroll."
      onCancel={props.onCancel}
    />
  );
}
