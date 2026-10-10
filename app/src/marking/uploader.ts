import { config } from '@/config';
import { NetworkError } from '@/api/errors';
import { envelopeToFormData, type BuiltEnvelope } from './envelope';

const UPLOAD_TIMEOUT_MS = 15_000;

export type VerificationReason = {
  code: string;
  message: string;
};

export type VerificationResponse = {
  mark_id?: string;
  verdict: 'PRESENT' | 'NEEDS_REVIEW' | 'REJECTED';
  score?: number | null;
  reasons?: VerificationReason[];
  retry_allowed?: boolean;
  attempts_left?: number;
  fallback?: string;
};

/**
 * Uploads the signed multipart attendance envelope to POST /v1/attendance/verify.
 *
 * Rules:
 * - 15-second timeout per attempt.
 * - On network failure, retry once with the identical envelope.
 * - After a second network failure, throws NetworkError so Fallback screen can be shown.
 */
export async function uploadAttendanceEnvelope(
  envelope: BuiltEnvelope,
): Promise<VerificationResponse> {
  const url = new URL(
    'attendance/verify',
    config.apiBaseUrl.endsWith('/') ? config.apiBaseUrl : `${config.apiBaseUrl}/`,
  ).toString();

  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= 2; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

    try {
      const formData = envelopeToFormData(envelope);
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        if (response.status >= 500) {
          throw new NetworkError('Hostel server is currently unavailable');
        }
        // Client errors (4xx) might also carry JSON verdict or details
        try {
          const json = await response.json();
          if (json.verdict) {
            return json as VerificationResponse;
          }
        } catch {
          // ignore
        }
        throw new NetworkError(`Server rejected submission with status ${response.status}`);
      }

      const result = (await response.json()) as VerificationResponse;
      return result;
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (err instanceof Error && err.name === 'AbortError') {
        lastError = new NetworkError('Upload timed out (15s exceeded)');
      }
      // If this was attempt 1, wait briefly and retry with identical envelope
      if (attempt === 1) {
        await new Promise((resolve) => setTimeout(resolve, 800));
        continue;
      }
    } finally {
      clearTimeout(timeoutId);
    }
  }

  throw lastError ?? new NetworkError('Could not reach the hostel server');
}
