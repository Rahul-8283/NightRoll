import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import type { TonightData } from './types'

// The live provider writes into this key, so the page and the top bar always share one copy.
export function useTonight() {
  return useQuery({
    queryKey: ['tonight'],
    queryFn: () => apiFetch<TonightData>('/attendance/tonight'),
  })
}
