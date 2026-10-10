import { config } from '@/config';

import { NetworkError, toApiError } from './errors';
import { signRequest } from './signing';

const TIMEOUT_MS = 10_000;

export type RequestOptions = {
  method?: string;
  body?: unknown;
  /** Student UUID. When set, the request carries the signed headers (section 3 of Phase 4). */
  signAs?: string;
};

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const bodyText = options.body !== undefined ? JSON.stringify(options.body) : '';
  const url = new URL(path, config.apiBaseUrl.endsWith('/') ? config.apiBaseUrl : `${config.apiBaseUrl}/`);

  const headers: Record<string, string> = {};
  if (bodyText) {
    headers['Content-Type'] = 'application/json';
  }
  if (options.signAs) {
    const signed = await signRequest(options.signAs, method, `${url.pathname}${url.search}`, bodyText);
    Object.assign(headers, signed);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: bodyText || undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new NetworkError('Request timed out');
    }
    throw new NetworkError(error instanceof Error ? error.message : 'Network request failed');
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw await toApiError(response.status, response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
