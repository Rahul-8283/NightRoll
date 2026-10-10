/**
 * Plain English mapping for all server-side rejection reason codes.
 * Kept in one file as specified in Phase 7 Task 8.
 */
export const REASON_MESSAGES: Record<string, string> = {
  WIFI_PATTERN_MISMATCH: 'Your phone does not appear to be in your room.',
  NETWORK_MISMATCH: 'Request did not come from your room network.',
  OUTSIDE_WINDOW: 'Tonight’s attendance window has closed.',
  NONCE_INVALID: 'Attendance session expired or was already used.',
  SIGNATURE_INVALID: 'Could not verify your device signature.',
  DEVICE_NOT_ENROLLED: 'This phone is not enrolled.',
  INTEGRITY_FAILED: 'Phone security check could not be verified.',
  ENVIRONMENT_FLAGGED: 'A VPN, proxy, or mock location was detected.',
  FACE_MISMATCH: 'Face did not match your enrolled profile.',
  LIVENESS_FAILED: 'Liveness check did not pass.',
  LOW_SCORE: 'Attendance verification score was too low.',
  AP_UNAVAILABLE: 'Room access point could not be verified.',
  SERVICE_UNAVAILABLE: 'Could not reach the hostel server.',
};

export function formatReason(code?: string | null): string {
  if (!code) {
    return 'NightRoll could not confirm your attendance tonight.';
  }
  return REASON_MESSAGES[code] ?? code;
}
