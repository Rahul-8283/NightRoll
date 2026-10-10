export type NetworkInfo = {
  bssid: string;
  ssidHash: string;
  rssi: number;
  frequency: number;
  band: '2.4GHz' | '5GHz' | string;
};

export type CurrentConnectionInfo = {
  bssid: string;
  ssidHash: string;
  rssi: number;
  frequency: number;
  band: '2.4GHz' | '5GHz' | string;
};

export type WifiScanResult = {
  networks: NetworkInfo[];
  ageSeconds: number;
  stale: boolean;
  freshScanTriggered: boolean;
  locationEnabled: boolean;
};
