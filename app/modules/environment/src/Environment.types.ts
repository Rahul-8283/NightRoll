export type EnvironmentReport = {
  vpn: boolean;
  proxy: boolean;
  mockLocation: boolean;
  developerOptions: boolean;
  onWifi: boolean;
  locationEnabled: boolean;
};

export type BlockingEnvironmentCheck =
  | 'VPN_ACTIVE'
  | 'PROXY_SET'
  | 'MOCK_LOCATION'
  | 'NOT_ON_WIFI'
  | 'LOCATION_DISABLED';
