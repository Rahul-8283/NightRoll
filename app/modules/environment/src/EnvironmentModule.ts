import { requireNativeModule } from 'expo-modules-core';
import { Platform } from 'react-native';

import type { EnvironmentReport } from './Environment.types';

type EnvironmentNativeType = {
  checkEnvironment(): Promise<EnvironmentReport>;
};

let EnvironmentNative: EnvironmentNativeType | null = null;
if (Platform.OS !== 'web') {
  try {
    EnvironmentNative = requireNativeModule<EnvironmentNativeType>('Environment');
  } catch {
    EnvironmentNative = null;
  }
}

export default EnvironmentNative;
