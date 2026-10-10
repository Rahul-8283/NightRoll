import type { AttendanceStatus } from '@/api/attendance';

/**
 * Fixed sample states for `EXPO_PUBLIC_MOCK_STATUS=true` (task 8.7), so every Home state can
 * be checked in Expo Go without a backend. Home cycles through these once per refresh tick.
 */
export const MOCK_STATUSES: AttendanceStatus[] = [
  {
    state: 'scheduled',
    opens_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    state: 'open',
    window_id: '00000000-0000-0000-0000-000000000001',
    nonce: 'mock-nonce',
    closes_at: new Date(Date.now() + 20 * 60 * 1000).toISOString(),
    challenge: ['blink', 'turn_left'],
  },
  {
    state: 'marked',
    window_id: '00000000-0000-0000-0000-000000000001',
  },
  {
    state: 'off',
  },
  {
    state: 'closed',
  },
];
