import { NativeModule, requireOptionalNativeModule } from 'expo';
import type { CurrentConnectionInfo, WifiScanResult } from './WifiScanner.types';

declare class WifiScannerModule extends NativeModule<{}> {
  isLocationEnabled(): Promise<boolean>;
  currentConnection(): Promise<CurrentConnectionInfo>;
  scan(): Promise<WifiScanResult>;
}

export default requireOptionalNativeModule<WifiScannerModule>('WifiScanner');
