// Web build. Metro picks this file on web, so the native camera never enters the bundle.
import { CameraUnavailable } from '@/components/CameraUnavailable';
import type { ChallengeRecord, FrameRecord } from '@/marking/envelope';
import type { ChallengeActionType } from '@/modules/face-detector';

export type LivenessCaptureProps = {
  challengeActions: ChallengeActionType[];
  onComplete: (data: { challenge: ChallengeRecord[]; frames: FrameRecord[] }) => void;
  onCancel?: () => void;
};

export function LivenessCapture({ onCancel }: LivenessCaptureProps) {
  return (
    <CameraUnavailable
      title="Marking needs the phone"
      detail="The liveness check uses the phone camera. Open NightRoll on your Android phone to mark attendance."
      onCancel={onCancel}
    />
  );
}
