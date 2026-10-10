import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { EnrollmentCode, EnrollmentStatus, RoomRow, StudentRow } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { StatusPill } from '../components/ui/StatusPill'
import { useNow } from '../hooks/useNow'
import { apiFetch, ApiError, patchJson, postJson } from '../lib/api'
import { formatCountdown } from '../lib/format'

function useStudentSearch(term: string) {
  return useQuery({
    queryKey: ['students', term],
    queryFn: () => apiFetch<StudentRow[]>(`/students?q=${encodeURIComponent(term)}`),
    enabled: term.length > 0,
  })
}

function useEnrollmentStatus(studentId: string | null) {
  return useQuery({
    queryKey: ['student', studentId, 'enrollment'],
    queryFn: () => apiFetch<EnrollmentStatus>(`/students/${studentId}/enrollment`),
    enabled: studentId !== null,
  })
}

function useRooms() {
  return useQuery({
    queryKey: ['rooms'],
    queryFn: () => apiFetch<RoomRow[]>('/rooms'),
  })
}

function errorText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

// Shown once. The warden reads it out or types it into the student's phone before it expires.
function CodeCard({ studentId }: { studentId: string }) {
  const now = useNow()
  const [issued, setIssued] = useState<EnrollmentCode | null>(null)
  const create = useMutation({
    mutationFn: () => postJson<EnrollmentCode>('/enrollment-codes', { student_id: studentId }),
    onSuccess: setIssued,
  })

  const remaining = issued ? new Date(issued.expires_at).getTime() - now : 0
  const expired = issued !== null && remaining <= 0

  return (
    <section className="card">
      <div className="card__head">
        <h2 className="title">Enrollment code</h2>
        {issued && !expired && <span className="eyebrow">Expires in {formatCountdown(remaining)}</span>}
      </div>
      {issued && !expired ? (
        <div className="code-display" aria-live="polite">
          <span className="code-display__value mono">{issued.code}</span>
          <p className="muted">Shown once. Enter it in the NightRoll app on the student&apos;s phone.</p>
        </div>
      ) : (
        <p className="muted">
          {expired ? 'That code has expired. Create a new one.' : 'Create a code for this student to enter on their phone.'}
        </p>
      )}
      {create.isError && <p className="form-error" role="alert">{errorText(create.error, 'The code was not created.')}</p>}
      <button className="btn btn--primary" type="button" disabled={create.isPending} onClick={() => create.mutate()}>
        {create.isPending ? 'Creating…' : issued ? 'Create a new code' : 'Create enrollment code'}
      </button>
    </section>
  )
}

// Withdrawal needs the student's roll number typed back, so it cannot happen by a stray click.
function WithdrawCard({ student }: { student: EnrollmentStatus }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const withdraw = useMutation({
    mutationFn: () => postJson<{ withdrawn: boolean }>(`/students/${student.student_id}/withdraw`, {}),
    onSuccess: () => {
      setOpen(false)
      setTyped('')
      void queryClient.invalidateQueries({ queryKey: ['student'] })
      void queryClient.invalidateQueries({ queryKey: ['students'] })
    },
  })

  if (!student.enrolled) return null
  return (
    <section className="card">
      <div className="card__head">
        <h2 className="title">Withdraw consent</h2>
      </div>
      {!open ? (
        <>
          <p className="muted">Use this if the student asks to stop using NightRoll.</p>
          <button className="btn btn--danger" type="button" onClick={() => setOpen(true)}>
            Withdraw consent
          </button>
        </>
      ) : (
        <div className="confirm">
          <p>
            This deletes the student&apos;s face data, deactivates their device key, and clears their enrollment and consent.
            They will have to enroll again before they can mark attendance.
          </p>
          <div className="field">
            <label htmlFor="withdraw-confirm">Type the roll number {student.roll_number} to confirm</label>
            <input id="withdraw-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          </div>
          {withdraw.isError && <p className="form-error" role="alert">{errorText(withdraw.error, 'Consent was not withdrawn.')}</p>}
          <div className="confirm__actions">
            <button
              className="btn btn--danger"
              type="button"
              disabled={typed.trim() !== student.roll_number || withdraw.isPending}
              onClick={() => withdraw.mutate()}
            >
              {withdraw.isPending ? 'Withdrawing…' : 'Withdraw consent'}
            </button>
            <button className="btn" type="button" disabled={withdraw.isPending} onClick={() => { setOpen(false); setTyped('') }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

function ChangeRoomCard({ student }: { student: EnrollmentStatus }) {
  const queryClient = useQueryClient()
  const rooms = useRooms()
  const [roomId, setRoomId] = useState(student.room_id)
  const move = useMutation({
    mutationFn: () => patchJson<{ room_number: string }>(`/students/${student.student_id}/room`, { room_id: roomId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['student', student.student_id] })
      void queryClient.invalidateQueries({ queryKey: ['students'] })
      void queryClient.invalidateQueries({ queryKey: ['roomTonight'] })
    },
  })

  return (
    <section className="card">
      <div className="card__head">
        <h2 className="title">Room</h2>
        <span className="eyebrow">Now in Room {student.room_number}</span>
      </div>
      {rooms.isError && <ErrorBanner error={rooms.error} onRetry={() => void rooms.refetch()} stale={false} />}
      {rooms.data && (
        <div className="field-row">
          <div className="field">
            <label htmlFor="room">Move to</label>
            <select id="room" value={roomId} onChange={(e) => setRoomId(e.target.value)}>
              {rooms.data.map((room) => (
                <option key={room.id} value={room.id}>
                  Room {room.number} (floor {room.floor})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="field__spacer" aria-hidden="true" />
            <button className="btn" type="button" disabled={roomId === student.room_id || move.isPending} onClick={() => move.mutate()}>
              {move.isPending ? 'Moving…' : 'Change room'}
            </button>
          </div>
        </div>
      )}
      {move.isSuccess && <p className="muted">Moved. Their attendance will count in the new room from tonight.</p>}
      {move.isError && <p className="form-error" role="alert">{errorText(move.error, 'The room was not changed.')}</p>}
    </section>
  )
}

function StudentDetail({ studentId }: { studentId: string }) {
  const query = useEnrollmentStatus(studentId)

  if (query.isPending) return <p className="muted">Loading student…</p>
  if (query.isError) return <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={false} />
  const student = query.data

  return (
    <div className="stack">
      <section className="card">
        <div className="card__head">
          <h2 className="title">{student.name}</h2>
          <StatusPill status={student.enrolled ? 'present' : 'unlit'} label={student.enrolled ? 'Enrolled' : 'Not enrolled'} />
        </div>
        <dl className="facts">
          <div>
            <dt>Roll number</dt>
            <dd className="mono">{student.roll_number}</dd>
          </div>
          <div>
            <dt>Room</dt>
            <dd>{student.room_number}</dd>
          </div>
          <div>
            <dt>Face</dt>
            <dd>{student.face_enrolled ? 'Enrolled' : 'Not enrolled'}</dd>
          </div>
          <div>
            <dt>Device</dt>
            <dd>
              {student.device_enrolled ? `Enrolled${student.device_security_level ? `, ${student.device_security_level}` : ''}` : 'Not enrolled'}
            </dd>
          </div>
          <div>
            <dt>Room Wi-Fi fingerprint</dt>
            <dd>{student.room_fingerprint_enrolled ? `Version ${student.room_fingerprint_version}` : 'None yet'}</dd>
          </div>
          <div>
            <dt>Consent</dt>
            <dd>{student.consent_at ? `Given ${new Date(student.consent_at).toLocaleDateString('en-GB')}` : 'Not given'}</dd>
          </div>
        </dl>
      </section>
      <CodeCard key={studentId} studentId={studentId} />
      <ChangeRoomCard student={student} />
      <WithdrawCard student={student} />
    </div>
  )
}

export function Enrollment() {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const term = search.trim()
  const results = useStudentSearch(term)

  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Warden&apos;s desk</span>
          <h1 className="display">Enrollment</h1>
        </div>
      </header>

      <div className="grid-2">
        <section className="card">
          <div className="card__head">
            <h2 className="title">Find a student</h2>
          </div>
          <div className="field">
            <label htmlFor="student-search">Roll number or name</label>
            <input
              id="student-search"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoComplete="off"
              placeholder="e.g. 21CS014 or Asha"
            />
          </div>
          {results.isError && <ErrorBanner error={results.error} onRetry={() => void results.refetch()} stale={false} />}
          {term.length > 0 && results.data?.length === 0 && <p className="muted">No student matches “{term}”.</p>}
          {term.length === 0 && <p className="muted">Type part of a roll number or name to find someone.</p>}
          {results.data && results.data.length > 0 && (
            <div className="ledger">
              {results.data.map((student) => (
                <button
                  key={student.id}
                  type="button"
                  className={`ledger__row result${selected === student.id ? ' is-selected' : ''}`}
                  onClick={() => setSelected(student.id)}
                  aria-pressed={selected === student.id}
                >
                  <span className="ledger__main">
                    <span>{student.name}</span>
                    <small className="mono">{student.roll_number} · Room {student.room_number}</small>
                  </span>
                  <StatusPill status={student.enrolled ? 'present' : 'unlit'} label={student.enrolled ? 'Enrolled' : 'Not enrolled'} />
                </button>
              ))}
            </div>
          )}
        </section>

        <aside>
          {selected ? (
            <StudentDetail key={selected} studentId={selected} />
          ) : (
            <section className="empty">
              <h2 className="title">No student selected</h2>
              <p className="lede">Pick someone from the results to see their enrollment.</p>
            </section>
          )}
        </aside>
      </div>
    </>
  )
}
