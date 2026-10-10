import type { CSSProperties } from 'react'
import { Link } from 'react-router'
import { STATUS_LABEL, type Status } from './status'

type Props = {
  number: string
  /** One entry per bed. Each becomes a pane of the window. */
  panes: Status[]
  to?: string
  size?: 'sm' | 'lg'
  /** Offsets the light-on animation so a floor lights up in sequence. */
  index?: number
  /** The count under the room number, for example "3 / 4". */
  count?: string
  /** The state in words under the count, for example "Needs review". */
  caption?: string
  /** Outlines the frame in ember for a room that needs attention. */
  problem?: boolean
  /** Changing this value replays the one-time pulse, so a tile that just changed catches the eye. */
  pulse?: number
  /** A suggested action for a room that needs attention, shown under the caption. */
  flag?: string
}

const EMPTY_PANES = [0, 1, 2, 3]

function describe(number: string, panes: Status[]): string {
  if (panes.length === 0) return `Room ${number}: no students enrolled`
  const counts = panes.reduce<Partial<Record<Status, number>>>((acc, status) => {
    acc[status] = (acc[status] ?? 0) + 1
    return acc
  }, {})
  const parts = (Object.keys(counts) as Status[]).map((status) => `${counts[status]} ${STATUS_LABEL[status].toLowerCase()}`)
  return `Room ${number}: ${parts.join(', ')}`
}

// A room drawn as a window. A lit pane is a student who is present.
export function RoomWindow({ number, panes, to, size = 'sm', index = 0, count, caption, problem = false, pulse, flag }: Props) {
  const frameClass = ['window__frame', size === 'lg' && 'window__frame--lg', problem && 'window__frame--problem']
    .filter(Boolean)
    .join(' ')

  const body = (
    <>
      <span className={frameClass} aria-hidden="true">
        {panes.length === 0
          ? // A room with nobody enrolled still reads as a window: four empty panes, not a collapsed bar.
            EMPTY_PANES.map((i) => <span key={i} className="pane pane--empty" />)
          : panes.map((status, i) => (
              <span key={i} className={`pane pane--${status}`} style={{ '--i': index * 4 + i } as CSSProperties} />
            ))}
        {pulse !== undefined && <span key={pulse} className="window__pulse" />}
      </span>
      {size === 'sm' && <span className="window__number">{number}</span>}
      {count && <span className="window__count">{count}</span>}
      {caption && <span className="window__caption">{caption}</span>}
      {flag && <span className="window__flag">{flag}</span>}
    </>
  )

  const label = describe(number, panes)
  const accessibleName = panes.length === 0 ? label : caption ? `${label}. ${count ?? ''} ${caption}` : label
  if (to) {
    return (
      <Link to={to} className="window" aria-label={accessibleName}>
        {body}
      </Link>
    )
  }
  return (
    <span className="window" role="img" aria-label={caption ? `${label}. ${caption}` : label}>
      {body}
    </span>
  )
}
