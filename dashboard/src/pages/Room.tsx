import { Link, useParams } from 'react-router'
import { EmptyState, NotConnected } from '../components/ui/EmptyState'
import { RoomWindow } from '../components/ui/RoomWindow'
import { SampleNote } from '../components/ui/SampleNote'
import { StatusPill } from '../components/ui/StatusPill'
import { config } from '../config'
import { SAMPLE_ROOMS } from '../sample/hostel'

export function Room() {
  const { roomId } = useParams()

  if (!config.sampleData) {
    return (
      <>
        <header className="page__head">
          <div>
            <span className="eyebrow">Room</span>
            <h1 className="display">Room {roomId}</h1>
          </div>
        </header>
        <NotConnected what="The room page" />
      </>
    )
  }

  const room = SAMPLE_ROOMS.find((r) => r.number === roomId)
  if (!room) {
    return (
      <EmptyState title="No such room">
        <p>
          Room {roomId} is not in the sample data. <Link to="/dashboard">Back to tonight</Link>
        </p>
      </EmptyState>
    )
  }

  const present = room.students.filter((s) => s.status === 'present').length

  return (
    <>
      <SampleNote />
      <header className="page__head">
        <div>
          <span className="eyebrow">
            <Link to="/dashboard">Tonight</Link> · Floor {room.floor}
          </span>
          <h1 className="display">
            Room {room.number}, <em>{present}</em> of {room.students.length} in
          </h1>
        </div>
      </header>

      <div className="grid-2">
        <section className="card">
          <div className="card__head">
            <h2 className="title">Who sleeps here</h2>
            <span className="eyebrow">{room.students.length} beds</span>
          </div>
          <div className="ledger">
            {room.students.map((student) => (
              <div key={student.roll} className="ledger__row">
                <div className="ledger__main">
                  <span>{student.name}</span>
                  <small>
                    <span className="mono">{student.roll}</span>
                    {student.note ? ` · ${student.note}` : ''}
                  </small>
                </div>
                <StatusPill status={student.status} />
              </div>
            ))}
          </div>
        </section>

        <aside className="card" style={{ display: 'grid', placeItems: 'center', gap: 'var(--s-4)' }}>
          <RoomWindow number={room.number} panes={room.students.map((s) => s.status)} size="lg" />
          <p className="muted" style={{ textAlign: 'center' }}>
            One pane per bed, in roll-number order.
          </p>
        </aside>
      </div>
    </>
  )
}
