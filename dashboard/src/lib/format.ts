import type { ReasonOut } from '../api/types'

// Clock time as a warden reads it, for example "10:00 PM".
export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

// Counts down as m:ss, or h:mm:ss once an hour or more is left.
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`
}

export function describeReasons(reasons: ReasonOut[]): string {
  // Older marks can carry the same reason twice. Say each one once.
  return [...new Set(reasons.map((reason) => reason.message))].join(' ')
}
