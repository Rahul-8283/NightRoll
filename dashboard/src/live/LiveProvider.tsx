import { useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { config } from '../config'
import { supabase } from '../lib/supabase'
import { applyRoomUpdate, applyWindowState } from './patch'
import { LiveContext, type LiveStatus } from './context'
import type { RoomUpdate, TonightData, WindowState } from '../api/types'

const RETRY_DELAYS_MS = [1000, 2000, 4000, 8000, 16000, 30000]
const FAILURES_BEFORE_POLLING = 5
const POLL_INTERVAL_MS = 5000
const CLOSE_UNAUTHORIZED = 4401
const CLOSE_FORBIDDEN = 4403

type Incoming =
  | ({ type: 'snapshot' } & TonightData)
  | ({ type: 'room_update' } & RoomUpdate)
  | { type: 'window_state'; window_id: string; state: WindowState }
  | { type: 'enrollment_update'; student_id: string; enrolled: boolean }
  | { type: 'ping' }

// Keeps one WebSocket open for the signed-in warden and writes every update into the React Query cache.
export function LiveProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<LiveStatus>('connecting')
  const [roomPulses, setRoomPulses] = useState<Record<string, number>>({})
  const [enrollmentTick, setEnrollmentTick] = useState(0)

  useEffect(() => {
    let socket: WebSocket | null = null
    let retryTimer: number | undefined
    let pollTimer: number | undefined
    let failures = 0
    let stopped = false

    const stopPolling = () => {
      if (pollTimer !== undefined) window.clearInterval(pollTimer)
      pollTimer = undefined
    }

    const startPolling = () => {
      if (pollTimer !== undefined) return
      setStatus('polling')
      pollTimer = window.setInterval(() => {
        void queryClient.invalidateQueries({ queryKey: ['tonight'] })
      }, POLL_INTERVAL_MS)
    }

    const handle = (message: Incoming) => {
      switch (message.type) {
        case 'snapshot': {
          failures = 0
          stopPolling()
          setStatus('live')
          const { type: _type, ...data } = message
          queryClient.setQueryData<TonightData>(['tonight'], data)
          return
        }
        case 'room_update':
          queryClient.setQueryData<TonightData | undefined>(['tonight'], (old) => applyRoomUpdate(old, message))
          setRoomPulses((pulses) => ({ ...pulses, [message.room_id]: Date.now() }))
          void queryClient.invalidateQueries({ queryKey: ['roomTonight', message.room_id] })
          // A decision by any warden moves cards in and out of the review queue on every open dashboard.
          void queryClient.invalidateQueries({ queryKey: ['reviews'] })
          void queryClient.invalidateQueries({ queryKey: ['mark'] })
          void queryClient.invalidateQueries({ queryKey: ['absentees'] })
          return
        case 'window_state': {
          const current = queryClient.getQueryData<TonightData>(['tonight'])
          if (current?.window?.id === message.window_id) {
            queryClient.setQueryData<TonightData | undefined>(['tonight'], (old) =>
              applyWindowState(old, message.window_id, message.state),
            )
          } else {
            void queryClient.invalidateQueries({ queryKey: ['tonight'] })
          }
          return
        }
        case 'enrollment_update':
          setEnrollmentTick((tick) => tick + 1)
          void queryClient.invalidateQueries({ queryKey: ['student'] })
          void queryClient.invalidateQueries({ queryKey: ['roomTonight'] })
          return
        case 'ping':
          socket?.send(JSON.stringify({ type: 'pong' }))
          return
      }
    }

    const scheduleReconnect = (delay: number) => {
      retryTimer = window.setTimeout(() => void connect(), delay)
    }

    const connect = async () => {
      if (stopped) return
      const { data } = await supabase.auth.getSession()
      const token = data.session?.access_token
      if (!token) return
      const ws = new WebSocket(config.wsUrl)
      socket = ws
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token }))
      ws.onmessage = (event) => handle(JSON.parse(event.data) as Incoming)
      ws.onclose = (event) => {
        socket = null
        if (stopped) return
        if (event.code === CLOSE_FORBIDDEN) {
          stopped = true
          startPolling()
          return
        }
        if (event.code === CLOSE_UNAUTHORIZED) {
          // A fresh token is needed before the socket can authenticate again. If refresh fails, the auth guard takes over.
          setStatus('reconnecting')
          void supabase.auth.refreshSession().then(({ error }) => {
            if (error) {
              stopped = true
              return
            }
            scheduleReconnect(0)
          })
          return
        }
        failures += 1
        if (failures >= FAILURES_BEFORE_POLLING) startPolling()
        else setStatus('reconnecting')
        scheduleReconnect(RETRY_DELAYS_MS[Math.min(failures - 1, RETRY_DELAYS_MS.length - 1)])
      }
    }

    void connect()

    return () => {
      stopped = true
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
      stopPolling()
      socket?.close()
    }
  }, [queryClient])

  return <LiveContext.Provider value={{ status, roomPulses, enrollmentTick }}>{children}</LiveContext.Provider>
}
