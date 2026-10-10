import * as Crypto from 'expo-crypto';

import * as DeviceKey from '@/modules/device-key';
import * as Integrity from '@/modules/integrity';

export type ChallengeRecord = {
  action: string;
  started_ms: number;
  detected_ms: number;
};

export type FrameRecord = {
  index: number;
  sha256: string;
  tag: string; // e.g. "blink", "turn_right", "neutral"
  uri: string;
};

export type WifiRecord = {
  connected: {
    bssid: string;
    rssi: number;
    band: string;
  };
  scan_age_ms: number;
  scan: {
    bssid: string;
    rssi: number;
    band: string;
  }[];
};

export type EnvironmentRecord = {
  vpn: boolean;
  proxy: boolean;
  mock_location: boolean;
  developer_options: boolean;
  on_wifi: boolean;
};

export type CorePayload = {
  v: number;
  student_id: string;
  window_id: string;
  nonce: string;
  client_time: string;
  challenge: ChallengeRecord[];
  frames: {
    index: number;
    sha256: string;
    tag: string;
  }[];
  wifi: WifiRecord;
  environment: EnvironmentRecord;
  app_version: string;
};

export type BuiltEnvelope = {
  payloadString: string;
  payloadHash: string;
  signature: string;
  integrityToken: string;
  integrityError?: string;
  frames: FrameRecord[];
};

/** Convert UTF-8 string to bytes reliably */
export function utf8ToBytes(input: string): Uint8Array {
  const utf8 = unescape(encodeURIComponent(input));
  const bytes = new Uint8Array(utf8.length);
  for (let i = 0; i < utf8.length; i += 1) {
    bytes[i] = utf8.charCodeAt(i);
  }
  return bytes;
}

/** Formats a Date object to RFC3339 / ISO 8601 with local timezone offset */
export function formatLocalIsoTime(date: Date = new Date()): string {
  const pad = (n: number) => Math.floor(Math.abs(n)).toString().padStart(2, '0');
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  const seconds = pad(date.getSeconds());

  const offsetMinutes = -date.getTimezoneOffset();
  const offsetSign = offsetMinutes >= 0 ? '+' : '-';
  const offsetHours = pad(Math.floor(Math.abs(offsetMinutes) / 60));
  const offsetMins = pad(Math.abs(offsetMinutes) % 60);

  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${offsetSign}${offsetHours}:${offsetMins}`;
}

/**
 * Builds the signed submission envelope strictly following Phase 7 section 6.
 *
 * Rules:
 * - Serialise the core payload once to a single UTF-8 string `payloadString`.
 * - Never serialise twice. The exact signed string and sent string are the same variable.
 * - Compute payload_hash = SHA-256(payloadString).
 * - Request Play Integrity token using payload_hash as requestHash.
 * - Sign payloadString with the device key.
 */
export async function buildEnvelope(params: {
  studentId: string;
  windowId: string;
  nonce: string;
  challenge: ChallengeRecord[];
  frames: FrameRecord[];
  wifi: WifiRecord;
  environment: EnvironmentRecord;
  appVersion?: string;
}): Promise<BuiltEnvelope> {
  const clientTime = formatLocalIsoTime();

  // Step 1: Build the core payload object and serialize it once
  const corePayload: CorePayload = {
    v: 1,
    student_id: params.studentId,
    window_id: params.windowId,
    nonce: params.nonce,
    client_time: clientTime,
    challenge: params.challenge,
    frames: params.frames.map((f) => ({
      index: f.index,
      sha256: f.sha256,
      tag: f.tag,
    })),
    wifi: params.wifi,
    environment: params.environment,
    app_version: params.appVersion ?? '0.1.0',
  };

  const payloadString = JSON.stringify(corePayload);

  // Step 2: Compute SHA-256 of the payload bytes
  const payloadHash = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    payloadString,
  );

  // Step 3: Request Play Integrity token bound to payload_hash
  const integrityResult = await Integrity.requestToken(payloadHash);
  const integrityToken = integrityResult.token ?? '';
  const integrityError = integrityResult.errorCode ?? undefined;

  // Step 4: Sign payload bytes with the hardware-backed device key
  const signature = await DeviceKey.sign(utf8ToBytes(payloadString));

  return {
    payloadString,
    payloadHash,
    signature,
    integrityToken,
    integrityError,
    frames: params.frames,
  };
}

/**
 * Builds a FormData instance ready for multipart POST /v1/attendance/verify.
 */
export function envelopeToFormData(envelope: BuiltEnvelope): FormData {
  const formData = new FormData();

  // Exact payload string from step 1
  formData.append('payload', envelope.payloadString);
  // Base64 signature from step 4
  formData.append('signature', envelope.signature);
  // Integrity token or empty
  formData.append('integrity_token', envelope.integrityToken);
  if (envelope.integrityError) {
    formData.append('integrity_error', envelope.integrityError);
  }

  // 4 JPEG frames: frame_0, frame_1, frame_2, frame_3
  envelope.frames.forEach((frame, idx) => {
    formData.append(`frame_${idx}`, {
      uri: frame.uri,
      name: `frame_${idx}.jpg`,
      type: 'image/jpeg',
    } as unknown as Blob);
  });

  return formData;
}
