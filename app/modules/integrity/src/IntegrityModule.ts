import { requireNativeModule } from 'expo-modules-core';

import type { IntegrityResult } from './Integrity.types';

type IntegrityNativeType = {
  prepare(projectNumber: string): Promise<boolean>;
  requestToken(requestHash: string): Promise<IntegrityResult>;
};

let IntegrityNative: IntegrityNativeType | null = null;
try {
  IntegrityNative = requireNativeModule<IntegrityNativeType>('Integrity');
} catch {
  IntegrityNative = null;
}

export default IntegrityNative;
