import EnvironmentNative from './src/EnvironmentModule';
import type { BlockingEnvironmentCheck, EnvironmentReport } from './src/Environment.types';

export type { BlockingEnvironmentCheck, EnvironmentReport };

const DEFAULT_REPORT: EnvironmentReport = {
  vpn: false,
  proxy: false,
  mockLocation: false,
  developerOptions: false,
  onWifi: true,
  locationEnabled: true,
};

export function isAvailable(): boolean {
  return EnvironmentNative !== null;
}

/**
 * Runs native environment checks on Android.
 * In Expo Go, web, or when native module is unavailable, returns a safe mock report.
 */
export async function check(): Promise<EnvironmentReport> {
  if (EnvironmentNative === null) {
    return DEFAULT_REPORT;
  }
  return EnvironmentNative.checkEnvironment();
}

/**
 * Evaluates whether an environment report contains a blocking condition
 * and returns the reason and fix instructions.
 */
export function getBlockingIssue(
  report: EnvironmentReport,
): { code: BlockingEnvironmentCheck; message: string; instruction: string } | null {
  if (report.vpn) {
    return {
      code: 'VPN_ACTIVE',
      message: 'VPN is active.',
      instruction: 'Turn off your VPN and try again.',
    };
  }
  if (report.proxy) {
    return {
      code: 'PROXY_SET',
      message: 'HTTP proxy is configured.',
      instruction: 'Turn off your proxy in network settings and try again.',
    };
  }
  if (report.mockLocation) {
    return {
      code: 'MOCK_LOCATION',
      message: 'Mock location provider is active.',
      instruction: 'Disable mock location in developer options and try again.',
    };
  }
  if (!report.onWifi) {
    return {
      code: 'NOT_ON_WIFI',
      message: 'Phone is on mobile data.',
      instruction: 'Connect to your room Wi-Fi network and try again.',
    };
  }
  if (!report.locationEnabled) {
    return {
      code: 'LOCATION_DISABLED',
      message: 'Location setting is turned off.',
      instruction: 'Turn on location to allow room Wi-Fi scanning.',
    };
  }
  return null;
}
