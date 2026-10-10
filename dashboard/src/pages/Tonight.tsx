import { NotConnected } from '../components/ui/EmptyState'
import { RoomWindow } from '../components/ui/RoomWindow'
import { SampleNote } from '../components/ui/SampleNote'
import { StatusPill } from '../components/ui/StatusPill'
import { STATUS_LABEL, type Status } from '../components/ui/status'
import { config } from '../config'
import { SAMPLE_ROOMS, SAMPLE_WINDOW, countByStatus, studentsWith } from '../sample/hostel'

const today = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
const TALLY: Status[] = ['present', 'review', 'rejected', 'unlit']

export function Tonight() {
  if (!config.sampleData) {
    return (
      <>
        <header className="page__head">
          <div>
            <span className="eyebrow">{today}</span>
            <h1 className="display">Tonight</h1>
          </div>
        </header>
        <NotConnected what="The live floor view" />
      </>
    )
  }

  const rooms = SAMPLE_ROOMS
  const counts = countByStatus(rooms)
  const total = TALLY.reduce((sum, status) => sum + counts[status], 0)
  const floors = [...new Set(rooms.map((room) => room.floor))]
  const review = studentsWith(rooms, 'review')
  const rejected = studentsWith(rooms, 'rejected')

  return (
    <>
      <SampleNote />
      <header className="page__head">
        <div>
          <span className="eyebrow">Tonight · {today}</span>
          <h1 className="display">
            <em>{counts.present}</em> of {total} are in for the night
          </h1>
        </div>
        <StatusPill status="present" label={`Window open · closes ${SAMPLE_WINDOW.closes}`} />
      </header>

      <section className="tally" aria-label="Tonight's counts">
        {TALLY.map((status) => (
          <div key={status} className="tally__cell">
            <span className="tally__value">{counts[status]}</span>
            <span className="tally__label">
              <span className={`swatch swatch--${status}`} aria-hidden="true" />
              {STATUS_LABEL[status]}
            </span>
          </div>
        ))}
      </section>

      <div className="grid-2">
        <section className="stack">
          <div className="facade" aria-label="Rooms by floor">
            {floors.map((floor) => (
              <div key={floor} className="facade__floor">
                <span className="eyebrow">Floor {floor}</span>
                <div className="facade__rooms">
                  {rooms
                    .filter((room) => room.floor === floor)
                    .map((room, index) => (
                      <RoomWindow
                        key={room.number}
                        number={room.number}
                        panes={room.students.map((s) => s.status)}
                        to={`/dashboard/rooms/${room.number}`}
                        index={index}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
          <div className="legend">
            {TALLY.map((status) => (
              <span key={status}>
                <span className={`swatch swatch--${status}`} aria-hidden="true" />
                {STATUS_LABEL[status]}
              </span>
            ))}
            <span className="muted">Each pane is one bed.</span>
          </div>
        </section>

        <aside className="stack">
          <section className="card">
            <div className="card__head">
              <h2 className="title">Needs your eye</h2>
              <span className="eyebrow">{review.length} waiting</span>
            </div>
            <div className="ledger">
              {review.map((student) => (
                <div key={student.roll} className="ledger__row">
                  <div className="ledger__main">
                    <span>{student.name}</span>
                    <small>{student.note}</small>
                  </div>
                  <span className="mono muted">{student.room}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="card__head">
              <h2 className="title">Sent downstairs</h2>
              <span className="eyebrow">{rejected.length} rejected</span>
            </div>
            <div className="ledger">
              {rejected.map((student) => (
                <div key={student.roll} className="ledger__row">
                  <div className="ledger__main">
                    <span>{student.name}</span>
                    <small>{student.note}</small>
                  </div>
                  <span className="mono muted">{student.room}</span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </>
  )
}
