import { useQuery } from '@tanstack/react-query'
import { apiFetch, ApiError } from '../lib/api'
import type {
  AbsenteeList,
  Alert,
  MarkDetailFull,
  ReviewItem,
  RoomFingerprint,
  RoomTonight,
  SystemOverview,
  TonightData,
} from './types'

// The live provider writes into this key, so the page and the top bar always share one copy.
export function useTonight() {
  return useQuery({
    queryKey: ['tonight'],
    queryFn: () => apiFetch<TonightData>('/attendance/tonight'),
  })
}

export function useRoomTonight(roomId: string) {
  return useQuery({
    queryKey: ['roomTonight', roomId],
    queryFn: () => apiFetch<RoomTonight>(`/rooms/${roomId}/tonight`),
  })
}

// A room with no fingerprint yet answers 404. That is an empty state, not a failure, so it is not retried.
export function useFingerprint(roomId: string) {
  return useQuery({
    queryKey: ['fingerprint', roomId],
    queryFn: () => apiFetch<RoomFingerprint>(`/rooms/${roomId}/fingerprint`),
    retry: (failures, error) => !(error instanceof ApiError && error.status === 404) && failures < 2,
  })
}

// Marks awaiting a decision in tonight's window, oldest first.
export function useReviewQueue() {
  return useQuery({
    queryKey: ['reviews'],
    queryFn: () => apiFetch<ReviewItem[]>('/reviews'),
  })
}

export function useMarkDetail(markId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['mark', markId],
    queryFn: () => apiFetch<MarkDetailFull>(`/attendance/marks/${markId}`),
    enabled,
  })
}

export function useAbsentees() {
  return useQuery({
    queryKey: ['absentees'],
    queryFn: () => apiFetch<AbsenteeList>('/attendance/absentees'),
  })
}

// What every warden should be told right now. Checked often because a face worker that stops during a window is
// the kind of thing someone has to act on within minutes.
export function useAlerts() {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiFetch<{ alerts: Alert[] }>('/alerts'),
    refetchInterval: 15_000,
    select: (data) => data.alerts,
  })
}

// Admin only: service health, tonight's counts, latency and the housekeeping jobs.
export function useSystem(enabled: boolean) {
  return useQuery({
    queryKey: ['system'],
    queryFn: () => apiFetch<SystemOverview>('/system'),
    refetchInterval: 10_000,
    enabled,
  })
}
