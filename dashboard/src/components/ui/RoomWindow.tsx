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
}

function describe(number: string, panes: Status[]): string {
  const counts = panes.reduce<Partial<Record<Status, number>>>((acc, status) => {
    acc[status] = (acc[status] ?? 0) + 1
    return acc
  }, {})
  const parts = (Object.keys(counts) as Status[]).map((status) => `${counts[status]} ${STATUS_LABEL[status].toLowerCase()}`)
  return `Room ${number}: ${parts.join(', ')}`
}

// A room drawn as a window. A lit pane is a student who is present.
export function RoomWindow({ number, panes, to, size = 'sm', index = 0 }: Props) {
  const body = (
    <>
      <span className={`window__frame${size === 'lg' ? ' window__frame--lg' : ''}`} aria-hidden="true">
        {panes.map((status, i) => (
          <span key={i} className={`pane pane--${status}`} style={{ '--i': index * 4 + i } as CSSProperties} />
        ))}
      </span>
      {size === 'sm' && <span className="window__number">{number}</span>}
    </>
  )

  if (to) {
    return (
      <Link to={to} className="window" aria-label={describe(number, panes)}>
        {body}
      </Link>
    )
  }
  return (
    <span className="window" role="img" aria-label={describe(number, panes)}>
      {body}
    </span>
  )
}
