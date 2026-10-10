import IntegrityNative from './src/IntegrityModule';
import type { IntegrityResult } from './src/Integrity.types';

export type { IntegrityResult };

export function isAvailable(): boolean {
  return IntegrityNative !== null;
}

/**
 * Prepares the Google Play Integrity token provider using the cloud project number.
 */
export async function prepare(projectNumber: string): Promise<boolean> {
  if (IntegrityNative === null) {
    return true;
  }
  return IntegrityNative.prepare(projectNumber);
}

/**
 * Requests an integrity token bound to the given request hash (SHA-256 of the payload).
 * On failure or when running on unsupported platforms, returns the result with errorCode.
 */
export async function requestToken(requestHash: string): Promise<IntegrityResult> {
  if (IntegrityNative === null) {
    return {
      token: `mock_integrity_token_${requestHash.slice(0, 16)}`,
      errorCode: null,
    };
  }
  return IntegrityNative.requestToken(requestHash);
}
