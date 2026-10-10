import { useCallback, useEffect, useRef, useState } from 'react';

import type { AttendanceStatus } from '@/api/attendance';
import { fetchAttendanceStatus } from '@/api/attendance';
import { NetworkError } from '@/api/errors';
import { config } from '@/config';
import { getCachedStatus, setCachedStatus } from '@/state/statusCache';

import { MOCK_STATUSES } from './mockStatuses';

const POLL_INTERVAL_MS = 60_000;

export type AttendanceStatusResult = {
  status: AttendanceStatus | null;
  /** True while the first fetch for this mount is still in flight. */
  loading: boolean;
  /** True once a fetch has failed and `status` is the last known value, not a fresh one. */
  isOffline: boolean;
  /** When `status` was last confirmed live, or last cached if offline. ISO string or null. */
  asOf: string | null;
  refresh: () => void;
};

/**
 * Fetches tonight's status on mount and every 60 seconds while the caller stays mounted
 * (task 8.1). Falls back to the last cached status with a retry when the network fails
 * (task 8.6). In mock mode it ignores the network and cycles through fixed sample states
 * (task 8.7).
 */
export function useAttendanceStatus(studentId: string | null): AttendanceStatusResult {
  const [status, setStatus] = useState<AttendanceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [asOf, setAsOf] = useState<string | null>(null);
  const mockIndex = useRef(0);
  const [refreshTick, setRefreshTick] = useState(0);

  const load = useCallback(async () => {
    if (config.mockStatus) {
      const next = MOCK_STATUSES[mockIndex.current % MOCK_STATUSES.length];
      mockIndex.current += 1;
      setStatus(next);
      setIsOffline(false);
      setAsOf(new Date().toISOString());
      setLoading(false);
      return;
    }

    if (!studentId) {
      setLoading(false);
      return;
    }

    try {
      const fresh = await fetchAttendanceStatus(studentId);
      setStatus(fresh);
      setIsOffline(false);
      setAsOf(new Date().toISOString());
      await setCachedStatus(fresh);
    } catch (error) {
      if (error instanceof NetworkError) {
        const cached = await getCachedStatus();
        if (cached) {
          setStatus(cached.status);
          setAsOf(cached.fetchedAt);
        }
        setIsOffline(true);
      } else {
        throw error;
      }
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load, refreshTick]);

  const refresh = useCallback(() => setRefreshTick((tick) => tick + 1), []);

  return { status, loading, isOffline, asOf, refresh };
}
