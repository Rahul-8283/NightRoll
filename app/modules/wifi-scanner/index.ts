import WifiScannerNative from './src/WifiScannerModule';
import type { CurrentConnectionInfo, NetworkInfo, WifiScanResult } from './src/WifiScanner.types';

export type { CurrentConnectionInfo, NetworkInfo, WifiScanResult };

export function isAvailable(): boolean {
  return WifiScannerNative !== null;
}

export async function isLocationEnabled(): Promise<boolean> {
  if (WifiScannerNative === null) {
    return true;
  }
  return WifiScannerNative.isLocationEnabled();
}

export async function currentConnection(): Promise<CurrentConnectionInfo> {
  if (WifiScannerNative === null) {
    return {
      bssid: 'aa:bb:cc:dd:ee:01',
      ssidHash: 'mock_ssid_hash',
      rssi: -50,
      frequency: 5200,
      band: '5GHz',
    };
  }
  return WifiScannerNative.currentConnection();
}

export async function scan(): Promise<WifiScanResult> {
  if (WifiScannerNative === null) {
    return {
      networks: [
        {
          bssid: 'aa:bb:cc:dd:ee:01',
          ssidHash: 'mock_ssid_hash',
          rssi: -55,
          frequency: 5200,
          band: '5GHz',
        },
        {
          bssid: 'aa:bb:cc:dd:ee:02',
          ssidHash: 'mock_neighbor_hash',
          rssi: -72,
          frequency: 2437,
          band: '2.4GHz',
        },
      ],
      ageSeconds: 0,
      stale: false,
      freshScanTriggered: true,
      locationEnabled: true,
    };
  }
  return WifiScannerNative.scan();
}
