import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { useFingerprint, useRoomTonight } from '../api/queries'
import type { RoomStudentStatus, Verdict } from '../api/types'
import { ScoreBars } from '../components/ScoreBars'
import { EmptyState } from '../components/ui/EmptyState'
import { RoomWindow } from '../components/ui/RoomWindow'
import { StatusPill } from '../components/ui/StatusPill'
import type { Status } from '../components/ui/status'
import { ErrorBanner } from '../components/ErrorBanner'
import { apiFetch, ApiError } from '../lib/api'
import { formatClock } from '../lib/format'

const VERDICT: Record<Verdict, { status: Status; label: string }> = {
  PRESENT: { status: 'present', label: 'Present' },
  MANUAL: { status: 'present', label: 'Marked by warden' },
  NEEDS_REVIEW: { status: 'review', label: 'In review' },
  REJECTED: { status: 'rejected', label: 'Rejected' },
  ABSENT: { status: 'unlit', label: 'Absent' },
}

function studentStatus(student: RoomStudentStatus): { status: Status; label: string } {
  if (!student.enrolled) return { status: 'unlit', label: 'Not enrolled' }
  if (!student.mark) return { status: 'unlit', label: 'Not yet marked' }
  return VERDICT[student.mark.verdict]
}

function paneFor(student: RoomStudentStatus): Status {
  if (!student.mark) return 'unlit'
  return studentStatus(student).status
}

function StudentRow({ student }: { student: RoomStudentStatus }) {
  const state = studentStatus(student)
  return (
    <details className="student">
      <summary className="student__summary">
        <div className="ledger__main">
          <span>{student.name}</span>
          <small className="mono">{student.roll_number}</small>
        </div>
        <span className="student__time mono muted">
          {student.mark ? formatClock(student.mark.marked_at) : ''}
        </span>
        <StatusPill status={state.status} label={state.label} />
      </summary>
      <div className="student__body">
        <div className="student__enrollment">
          <span className={`pill ${student.face_enrolled ? 'pill--present' : 'pill--unlit'}`}>
            Face {student.face_enrolled ? 'enrolled' : 'not enrolled'}
          </span>
          <span className={`pill ${student.device_enrolled ? 'pill--present' : 'pill--unlit'}`}>
            Device {student.device_enrolled ? `enrolled${student.device_security_level ? ` · ${student.device_security_level}` : ''}` : 'not enrolled'}
          </span>
        </div>
        {student.mark ? (
          <>
            <p className="muted">
              Attempt {student.mark.attempt}
              {student.mark.score !== null ? ` · trust ${student.mark.score.toFixed(2)}` : ''}
              {student.mark.reasons.length > 0 ? ` · ${student.mark.reasons.map((reason) => reason.message).join(' ')}` : ''}
            </p>
            <ScoreBars scorers={student.mark.scorers} />
          </>
        ) : (
          <p className="muted">No attempt tonight yet.</p>
        )}
      </div>
    </details>
  )
}

function FingerprintCard({ roomId }: { roomId: string }) {
  const query = useFingerprint(roomId)
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const reset = useMutation({
    mutationFn: () => apiFetch<{ reset_pending: boolean }>(`/rooms/${roomId}/fingerprint/reset`, { method: 'POST' }),
    onSuccess: () => {
      setConfirming(false)
      void queryClient.invalidateQueries({ queryKey: ['fingerprint', roomId] })
    },
  })

  const notCaptured = query.error instanceof ApiError && query.error.status === 404
  const fingerprint = query.data

  return (
    <section className="card">
      <div className="card__head">
        <h2 className="title">Wi-Fi fingerprint</h2>
        {fingerprint && <span className="eyebrow">Version {fingerprint.version}</span>}
      </div>

      {query.isPending && <p className="muted">Loading fingerprint…</p>}
      {query.isError && !notCaptured && (
        <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={false} />
      )}
      {notCaptured && (
        <p className="muted">
          No fingerprint yet. Captured scans from this room create one during enrollment.
        </p>
      )}

      {fingerprint && (
        <dl className="facts">
          <div>
            <dt>Captured</dt>
            <dd>{new Date(fingerprint.created_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}</dd>
          </div>
          <div>
            <dt>Access points</dt>
            <dd>{fingerprint.ap_count}</dd>
          </div>
        </dl>
      )}

      {(fingerprint?.reset_pending || reset.isSuccess) && (
        <div className="banner banner--moon">
          Reset requested. The next scans from this room replace the current fingerprint. Until then, the current one stays in use.
        </div>
      )}

      {fingerprint && !confirming && (
        <button className="btn btn--danger" type="button" onClick={() => setConfirming(true)}>
          Reset room fingerprint
        </button>
      )}
      {fingerprint && confirming && (
        <div className="confirm">
          <p>
            Reset the Wi-Fi fingerprint for this room? The current one stays in use until new scans replace it.
          </p>
          {reset.isError && (
            <p className="form-error" role="alert">
              {reset.error instanceof ApiError ? reset.error.message : 'The reset did not go through. Try again.'}
            </p>
          )}
          <div className="confirm__actions">
            <button className="btn btn--danger" type="button" disabled={reset.isPending} onClick={() => reset.mutate()}>
              {reset.isPending ? 'Resetting…' : 'Confirm reset'}
            </button>
            <button className="btn" type="button" disabled={reset.isPending} onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

export function Room() {
  const { roomId = '' } = useParams()
  const query = useRoomTonight(roomId)
  const data = query.data

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <section className="empty">
        <h2 className="title">Room not found</h2>
        <p className="lede">
          This room is not in the hostel list. <Link className="inline-link" to="/dashboard">Back to Tonight</Link>
        </p>
      </section>
    )
  }

  if (!data) {
    return (
      <>
        <Link className="inline-link" to="/dashboard">← Tonight</Link>
        {query.isError ? (
          <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={false} />
        ) : (
          <p className="muted">Loading room…</p>
        )}
      </>
    )
  }

  const present = data.students.filter((s) => s.mark && (s.mark.verdict === 'PRESENT' || s.mark.verdict === 'MANUAL')).length
  const enrolled = data.students.filter((s) => s.enrolled && s.active).length

  return (
    <>
      <header className="page__head">
        <div>
          <Link className="inline-link" to="/dashboard">← Tonight</Link>
          <span className="eyebrow">Floor {data.floor}</span>
          <h1 className="display">Room {data.number}</h1>
        </div>
        {data.window ? (
          <StatusPill status={data.window.state === 'open' ? 'present' : 'unlit'} label={`Window ${data.window.state}`} />
        ) : (
          <StatusPill status="unlit" label="No window tonight" />
        )}
      </header>

      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale />}

      <div className={query.isError ? 'stack is-stale' : 'stack'}>
        <section className="card room-head">
          <RoomWindow
            size="lg"
            number={data.number}
            panes={data.students.map(paneFor)}
          />
          <div className="room-head__text">
            <p className="title">
              {present} of {enrolled} {data.window?.state === 'closed' ? 'were in' : 'are in'}
            </p>
            <p className="muted">Each pane is one enrolled student. Lit means present.</p>
          </div>
        </section>

        <div className="grid-2">
          <section className="card">
            <div className="card__head">
              <h2 className="title">Students</h2>
              <span className="eyebrow">{data.students.length} in this room</span>
            </div>
            {data.students.length === 0 ? (
              <EmptyState title="No students in this room">
                <p>Move a student into this room from the Enrollment page.</p>
              </EmptyState>
            ) : (
              <div className="ledger">
                {data.students.map((student) => (
                  <StudentRow key={student.student_id} student={student} />
                ))}
              </div>
            )}
          </section>

          <aside className="stack">
            <FingerprintCard roomId={roomId} />
          </aside>
        </div>
      </div>
    </>
  )
}
