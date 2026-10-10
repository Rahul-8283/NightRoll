import { useTonight } from '../api/queries'
import { useNow } from '../hooks/useNow'
import { useLive } from '../live/useLive'
import { formatClock, formatCountdown } from '../lib/format'
import type { LiveStatus } from '../live/context'

const LIVE_LABEL: Record<LiveStatus, string> = {
  connecting: 'Connecting',
  live: 'Live',
  reconnecting: 'Reconnecting',
  polling: 'Polling',
}

// Tonight's window with its countdown, and the state of the live connection.
export function TopBar() {
  const { data } = useTonight()
  const { status } = useLive()
  const now = useNow()
  const window = data?.window

  let windowText = 'No window tonight'
  if (window?.state === 'open') {
    windowText = `Closes in ${formatCountdown(new Date(window.closes_at).getTime() - now)}`
  } else if (window?.state === 'scheduled') {
    windowText = `Opens at ${formatClock(window.opens_at)}`
  } else if (window?.state === 'closed') {
    windowText = `Closed at ${formatClock(window.closes_at)}`
  } else if (window?.state === 'off') {
    windowText = 'Off night'
  }

  return (
    <header className="topbar">
      <div className="topbar__window">
        <span className="eyebrow">Tonight&apos;s window</span>
        <span className="topbar__countdown">{windowText}</span>
      </div>
      <span className={`live live--${status}`} role="status" aria-live="polite">
        <span className="live__dot" aria-hidden="true" />
        {LIVE_LABEL[status]}
      </span>
    </header>
  )
}
