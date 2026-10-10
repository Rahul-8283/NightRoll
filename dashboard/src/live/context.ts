import { createContext } from 'react'

export type LiveStatus = 'connecting' | 'live' | 'reconnecting' | 'polling'

export type LiveValue = {
  status: LiveStatus
  // When each room last changed, so its tile can pulse once.
  roomPulses: Record<string, number>
  // Bumped on every enrollment update, so a page can refresh the student it is showing.
  enrollmentTick: number
}

export const LiveContext = createContext<LiveValue | null>(null)
