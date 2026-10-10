import { config } from '@/config';
import { apiFetch } from './client';
import { toApiError } from './errors';
import type { CapturedFrame } from '@/components/FaceCapture';

export type EnrollmentResult = {
  student_id: string;
  room_id: string;
  room_number: string;
};

export type SubmitEnrollmentParams = {
  code: string;
  rollNumber: string;
  publicKey: string;
  keySecurityLevel: string;
  consentVersion: string;
  frames: CapturedFrame[];
};

export async function submitEnrollment({
  code,
  rollNumber,
  publicKey,
  keySecurityLevel,
  consentVersion,
  frames,
}: SubmitEnrollmentParams): Promise<EnrollmentResult> {
  const formData = new FormData();
  formData.append('code', code.trim().toUpperCase());
  formData.append('roll_number', rollNumber.trim());
  formData.append('public_key', publicKey);
  formData.append('key_security_level', keySecurityLevel);
  formData.append('consent_version', consentVersion);

  for (let i = 0; i < frames.length; i++) {
    const frame = frames[i];
    // In React Native / Expo, FormData files are passed as { uri, name, type }
    formData.append('frames', {
      uri: frame.uri,
      name: frame.name || `frame_${i + 1}.jpg`,
      type: frame.type || 'image/jpeg',
    } as unknown as Blob);
  }

  const url = new URL('/v1/enrollments', config.apiBaseUrl.endsWith('/') ? config.apiBaseUrl : `${config.apiBaseUrl}/`);

  const response = await fetch(url.toString(), {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw await toApiError(response.status, response);
  }

  return (await response.json()) as EnrollmentResult;
}

export type ScanNetworkInput = {
  bssid: string;
  rssi: number;
  band: string;
};

export type SpotScanInput = {
  networks: ScanNetworkInput[];
};

export type RoomFingerprintResult = {
  id: string;
  room_id: string;
  version: number;
  ap_count: number;
  age_seconds: number;
  reset_pending: boolean;
};

export async function submitRoomFingerprint(
  roomId: string,
  studentId: string,
  scans: SpotScanInput[]
): Promise<RoomFingerprintResult> {
  return apiFetch<RoomFingerprintResult>(`/v1/rooms/${roomId}/fingerprint`, {
    method: 'POST',
    signAs: studentId,
    body: { scans },
  });
}
