import DeviceKeyNative from './src/DeviceKeyModule';
import type { SecurityLevel } from './src/DeviceKey.types';

export type { SecurityLevel };

const NOT_AVAILABLE_MESSAGE =
  'DeviceKey needs a development build. It is not available in Expo Go or on web.';

function requireNative() {
  if (DeviceKeyNative === null) {
    throw new Error(NOT_AVAILABLE_MESSAGE);
  }
  return DeviceKeyNative;
}

/**
 * Creates a non-exportable EC P-256 Keystore key under `nightroll_device_key`. Refuses to
 * overwrite an existing key; call `deleteKey()` first if re-enrolling. Returns the public key
 * as base64 DER (X.509 SubjectPublicKeyInfo).
 */
export async function generate(): Promise<string> {
  return requireNative().generate();
}

/** The current public key as base64 DER, or null if no key exists yet. */
export async function getPublicKey(): Promise<string | null> {
  return requireNative().getPublicKey();
}

/** Signs bytes with SHA256withECDSA. Returns the signature as base64 DER. */
export async function sign(data: Uint8Array): Promise<string> {
  return requireNative().sign(data);
}

/** True if a device key is present in the Keystore. */
export async function exists(): Promise<boolean> {
  return requireNative().exists();
}

/** Removes the device key. Used before re-enrollment. */
export async function deleteKey(): Promise<void> {
  return requireNative().delete();
}

/**
 * `strongbox` or `tee` on real hardware; `software` only if the phone exposes neither, which
 * is sent at enrollment so the backend can log it as a warning.
 */
export async function securityLevel(): Promise<SecurityLevel> {
  return requireNative().securityLevel();
}

/** True once a development build links the native module (always false in Expo Go or on web). */
export function isAvailable(): boolean {
  return DeviceKeyNative !== null;
}
