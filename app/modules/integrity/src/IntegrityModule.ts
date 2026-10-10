import { requireNativeModule } from 'expo-modules-core';
import { Platform } from 'react-native';

import type { IntegrityResult } from './Integrity.types';

type IntegrityNativeType = {
  prepare(projectNumber: string): Promise<boolean>;
  requestToken(requestHash: string): Promise<IntegrityResult>;
};

let IntegrityNative: IntegrityNativeType | null = null;
if (Platform.OS !== 'web') {
  try {
    IntegrityNative = requireNativeModule<IntegrityNativeType>('Integrity');
  } catch {
    IntegrityNative = null;
  }
}

export default IntegrityNative;
