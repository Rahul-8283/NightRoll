// Web build. Metro picks this file on web, so the native camera never enters the bundle.
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

export function FaceCapture({ onCancel }: FaceCaptureProps) {
  return (
    <CameraUnavailable
      title="Enrollment needs the phone"
      detail="Face capture only works in the NightRoll Android app. Open it on your phone to enroll."
      onCancel={onCancel}
    />
  );
}
