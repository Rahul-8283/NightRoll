/**
 * The last window status Home saw, for the offline case (task 8.6): nothing sensitive, so
 * AsyncStorage is enough.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

import type { AttendanceStatus } from '@/api/attendance';

const KEY = 'nightroll.status.last';

export type CachedStatus = {
  status: AttendanceStatus;
  fetchedAt: string;
};

export async function getCachedStatus(): Promise<CachedStatus | null> {
  const raw = await AsyncStorage.getItem(KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as CachedStatus;
  } catch {
    return null;
  }
}

export async function setCachedStatus(status: AttendanceStatus): Promise<void> {
  const cached: CachedStatus = { status, fetchedAt: new Date().toISOString() };
  await AsyncStorage.setItem(KEY, JSON.stringify(cached));
}
