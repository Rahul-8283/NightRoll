import * as Crypto from 'expo-crypto';

import * as DeviceKey from '@/modules/device-key';

export type SignedHeaders = {
  'X-Student-Id': string;
  'X-Timestamp': string;
  'X-Signature': string;
};

/** UTF-8 bytes without depending on a global TextEncoder, which some JS engines omit. */
function utf8ToBytes(input: string): Uint8Array {
  const utf8 = unescape(encodeURIComponent(input));
  const bytes = new Uint8Array(utf8.length);
  for (let i = 0; i < utf8.length; i += 1) {
    bytes[i] = utf8.charCodeAt(i);
  }
  return bytes;
}

/**
 * The string the device key signs, one field per line: method, path with query, timestamp,
 * then the SHA-256 hex of the body (or of the empty string for a bodyless request). The
 * backend rejects a timestamp more than 60 seconds from its own clock.
 */
export async function buildSigningString(
  method: string,
  pathWithQuery: string,
  timestamp: string,
  body: string
): Promise<string> {
  const bodyHash = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, body);
  return [method.toUpperCase(), pathWithQuery, timestamp, bodyHash].join('\n');
}

export async function signRequest(
  studentId: string,
  method: string,
  pathWithQuery: string,
  body: string
): Promise<SignedHeaders> {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const toSign = await buildSigningString(method, pathWithQuery, timestamp, body);
  const signature = await DeviceKey.sign(utf8ToBytes(toSign));
  return {
    'X-Student-Id': studentId,
    'X-Timestamp': timestamp,
    'X-Signature': signature,
  };
}
