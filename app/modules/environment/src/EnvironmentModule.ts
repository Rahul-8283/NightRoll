import { requireNativeModule } from 'expo-modules-core';

import type { EnvironmentReport } from './Environment.types';

type EnvironmentNativeType = {
  checkEnvironment(): Promise<EnvironmentReport>;
};

let EnvironmentNative: EnvironmentNativeType | null = null;
try {
  EnvironmentNative = requireNativeModule<EnvironmentNativeType>('Environment');
} catch {
  EnvironmentNative = null;
}

export default EnvironmentNative;
