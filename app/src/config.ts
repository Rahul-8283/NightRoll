// EXPO_PUBLIC_ values are baked into the app at build time. Only public values belong here.
export const config = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://10.0.2.2:8000/v1',
  googleCloudProjectNumber: process.env.EXPO_PUBLIC_GOOGLE_CLOUD_PROJECT_NUMBER ?? '',
  mockStatus: process.env.EXPO_PUBLIC_MOCK_STATUS === 'true',
};
