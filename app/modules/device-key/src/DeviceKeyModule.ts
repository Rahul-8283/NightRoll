import { NativeModule, requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';

declare class DeviceKeyModule extends NativeModule<{}> {
  generate(): Promise<string>;
  getPublicKey(): Promise<string | null>;
  sign(data: Uint8Array): Promise<string>;
  exists(): Promise<boolean>;
  delete(): Promise<void>;
  securityLevel(): Promise<'strongbox' | 'tee' | 'software'>;
}

// null in Expo Go, on web, and on platforms without the native module; index.ts turns that into a clear error.
export default Platform.OS === 'web'
  ? null
  : requireOptionalNativeModule<DeviceKeyModule>('DeviceKey');

