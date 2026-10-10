import { NativeModule, requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';
import type { CurrentConnectionInfo, WifiScanResult } from './WifiScanner.types';

declare class WifiScannerModule extends NativeModule<{}> {
  isLocationEnabled(): Promise<boolean>;
  currentConnection(): Promise<CurrentConnectionInfo>;
  scan(): Promise<WifiScanResult>;
}

export default Platform.OS === 'web'
  ? null
  : requireOptionalNativeModule<WifiScannerModule>('WifiScanner');
