import { Link } from 'react-router'
import { useTonight } from '../api/queries'
import type { HealthFlag, RecentMark, RoomCount, TonightData, Verdict } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { RoomWindow } from '../components/ui/RoomWindow'
import { StatusPill } from '../components/ui/StatusPill'
import type { Status } from '../components/ui/status'
import { useNow } from '../hooks/useNow'
import { useLive } from '../live/useLive'
import { describeReasons, formatClock, formatCountdown } from '../lib/format'

const today = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())

type TileState = 'empty' | 'none' | 'some' | 'all' | 'review' | 'problem'

const TILE_LABEL: Record<TileState, string> = {
  empty: 'No one enrolled',
  none: 'None yet',
  some: 'Some in',
  all: 'All in',
  review: 'Needs review',
  problem: 'Rejected attempt',
}

// The suggested action for each health flag, in the words a warden acts on.
const FLAG_ACTION: Record<HealthFlag, string> = {
  rescan_wifi: 'Re-scan Wi-Fi',
  check_router: 'Check router',
}

const VERDICT: Record<Verdict, { status: Status; label: string }> = {
  PRESENT: { status: 'present', label: 'Present' },
  MANUAL: { status: 'present', label: 'Marked by warden' },
  NEEDS_REVIEW: { status: 'review', label: 'In review' },
  REJECTED: { status: 'rejected', label: 'Rejected' },
  ABSENT: { status: 'unlit', label: 'Absent' },
}

// Order matters: a room with someone waiting for review is shown as needing review even if others are in.
function tileState(room: RoomCount): TileState {
  if (room.total === 0) return 'empty'
  if (room.present >= room.total) return 'all'
  if (room.pending_review > 0) return 'review'
  if (room.rejected > 0 && room.present === 0) return 'problem'
  if (room.present > 0) return 'some'
  return 'none'
}

// One pane per bed: lit for present, moon for in review, dark for not yet marked.
function panesFor(room: RoomCount): Status[] {
  const present = Math.min(room.present, room.total)
  const review = Math.min(room.pending_review, room.total - present)
  return Array.from({ length: room.total }, (_, i): Status => (i < present ? 'present' : i < present + review ? 'review' : 'unlit'))
}

function headline(data: TonightData): string {
  return `${data.totals.present} of ${data.totals.enrolled} ${data.window?.state === 'closed' ? 'were in' : 'are in'} for the night`
}

function windowPill(data: TonightData) {
  const window = data.window
  if (!window) return null
  if (window.state === 'open') return <StatusPill status="present" label="Window open" />
  if (window.state === 'scheduled') return <StatusPill status="unlit" label={`Opens ${formatClock(window.opens_at)}`} />
  if (window.state === 'closed') return <StatusPill status="unlit" label="Window closed" />
  return <StatusPill status="unlit" label="Off night" />
}

function WindowBanner({ data }: { data: TonightData }) {
  const window = data.window
  if (!window) {
    return (
      <div className="banner">
        <span>No attendance window tonight.</span>
        <Link className="inline-link" to="/dashboard/windows">
          Set one on the Windows page
        </Link>
      </div>
    )
  }
  if (window.state === 'scheduled') {
    return <div className="banner">Window opens at {formatClock(window.opens_at)}. Rooms stay unlit until then.</div>
  }
  if (window.state === 'closed') {
    return (
      <div className="banner">
        Closed at {formatClock(window.closes_at)}. The view is frozen on the final state.
      </div>
    )
  }
  if (window.state === 'off') {
    return <div className="banner">Tonight is an off night. No attendance is taken.</div>
  }
  return null
}

function RecentRow({ mark }: { mark: RecentMark }) {
  const verdict = VERDICT[mark.verdict]
  const detail = mark.verdict === 'PRESENT' || mark.verdict === 'MANUAL' ? '' : describeReasons(mark.reasons)
  return (
    <div className="ledger__row activity__row">
      <span className="mono muted activity__time">{formatClock(mark.marked_at)}</span>
      <div className="ledger__main">
        <span>
          {mark.student_name} <span className="muted nowrap">· Room {mark.room_number}</span>
        </span>
        {detail && <small>{detail}</small>}
      </div>
      <StatusPill status={verdict.status} label={verdict.label} />
    </div>
  )
}

export function Tonight() {
  const query = useTonight()
  const { roomPulses } = useLive()
  const now = useNow()
  const data = query.data

  const header = (
    <header className="page__head">
      <div>
        <span className="eyebrow">Tonight · {today}</span>
        <h1 className="display">{data ? headline(data) : 'Tonight'}</h1>
      </div>
      {data && windowPill(data)}
    </header>
  )

  if (!data) {
    return (
      <>
        {header}
        {query.isError ? (
          <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={false} />
        ) : (
          <p className="muted">Loading tonight…</p>
        )}
      </>
    )
  }

  const { totals, rooms, recent, window } = data
  const share = totals.enrolled ? Math.round((totals.present / totals.enrolled) * 100) : 0
  const timeLeft =
    window?.state === 'open' ? formatCountdown(new Date(window.closes_at).getTime() - now) : '—'
  const floors = [...new Set(rooms.map((room) => room.floor))]

  return (
    <>
      {header}
      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale />}
      <WindowBanner data={data} />

      <div className={query.isError ? 'stack is-stale' : 'stack'}>
        <section className="tally tally--five" aria-label="Tonight's counts">
          <div className="tally__cell">
            <span className="tally__value">{totals.present}</span>
            <span className="tally__label">
              <span className="swatch swatch--present" aria-hidden="true" />
              Present
            </span>
            <span className="tally__note">{share}% of {totals.enrolled}</span>
          </div>
          <div className="tally__cell">
            <span className="tally__value">{totals.pending_review}</span>
            <span className="tally__label">
              <span className="swatch swatch--review" aria-hidden="true" />
              Needs review
            </span>
            <span className="tally__note">Waiting for a warden</span>
          </div>
          <div className="tally__cell">
            <span className="tally__value">{totals.not_marked}</span>
            <span className="tally__label">
              <span className="swatch swatch--unlit" aria-hidden="true" />
              Not yet marked
            </span>
            <span className="tally__note">Enrolled, no mark yet</span>
          </div>
          <div className="tally__cell">
            <span className="tally__value">{totals.rejected}</span>
            <span className="tally__label">
              <span className="swatch swatch--rejected" aria-hidden="true" />
              Rejected attempts
            </span>
            <span className="tally__note">Each try counted</span>
          </div>
          <div className="tally__cell">
            <span className="tally__value tally__value--mono">{timeLeft}</span>
            <span className="tally__label">Time left</span>
            <span className="tally__note">{window?.state === 'open' ? `Closes ${formatClock(window.closes_at)}` : 'Window not open'}</span>
          </div>
        </section>

        {rooms.length === 0 ? (
          <section className="empty">
            <h2 className="title">No rooms yet</h2>
            <p className="lede">Load the hostel rooms with the seed script in the backend, then refresh this page.</p>
          </section>
        ) : (
          <div className="grid-2">
            <section className="stack">
              <div className="facade" aria-label="Rooms by floor">
                {floors.map((floor) => (
                  <div key={floor} className="facade__floor">
                    <span className="eyebrow">Floor {floor}</span>
                    <div className="facade__rooms">
                      {rooms
                        .filter((room) => room.floor === floor)
                        .map((room, index) => {
                          const state = tileState(room)
                          return (
                            <RoomWindow
                              key={room.room_id}
                              number={room.number}
                              panes={panesFor(room)}
                              to={`/dashboard/rooms/${room.room_id}`}
                              index={index}
                              count={state === 'empty' ? undefined : `${room.present} / ${room.total}`}
                              caption={TILE_LABEL[state]}
                              problem={state === 'problem'}
                              pulse={roomPulses[room.room_id]}
                              flag={room.health.map((h) => FLAG_ACTION[h]).join(' · ') || undefined}
                            />
                          )
                        })}
                    </div>
                  </div>
                ))}
              </div>
              <div className="legend">
                {(['present', 'review', 'rejected', 'unlit'] as const).map((status) => (
                  <span key={status}>
                    <span className={`swatch swatch--${status}`} aria-hidden="true" />
                    {status === 'present' ? 'Present' : status === 'review' ? 'In review' : status === 'rejected' ? 'Rejected' : 'Not yet marked'}
                  </span>
                ))}
                <span className="muted">Each pane is one bed.</span>
              </div>
            </section>

            <aside className="stack">
              <section className="card">
                <div className="card__head">
                  <h2 className="title">Recent activity</h2>
                  <span className="eyebrow">Latest {recent.length}</span>
                </div>
                {recent.length === 0 ? (
                  <p className="muted">No marks yet tonight.</p>
                ) : (
                  <div className="ledger">
                    {recent.map((mark) => (
                      <RecentRow key={mark.mark_id} mark={mark} />
                    ))}
                  </div>
                )}
              </section>
            </aside>
          </div>
        )}
      </div>
    </>
  )
}
