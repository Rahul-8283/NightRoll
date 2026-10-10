import { useQuery } from '@tanstack/react-query'
import { apiFetch, ApiError } from '../lib/api'
import type { RoomFingerprint, RoomTonight, TonightData } from './types'

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
