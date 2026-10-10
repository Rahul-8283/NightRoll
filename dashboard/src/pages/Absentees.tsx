import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useAbsentees } from '../api/queries'
import type { AbsenteeRow } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { EmptyState } from '../components/ui/EmptyState'
import { StatusPill } from '../components/ui/StatusPill'
import { ApiError, postJson } from '../lib/api'

const MIN_NOTE = 10

function ManualMark({ row, windowId }: { row: AbsenteeRow; windowId: string }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const record = useMutation({
    mutationFn: () =>
      postJson('/attendance/manual', { student_id: row.student_id, window_id: windowId, note: note.trim() }),
    onSuccess: () => {
      setOpen(false)
      setNote('')
      void queryClient.invalidateQueries({ queryKey: ['absentees'] })
      void queryClient.invalidateQueries({ queryKey: ['tonight'] })
      void queryClient.invalidateQueries({ queryKey: ['reviews'] })
    },
  })

  if (!open) {
    return (
      <button className="btn btn--quiet-small" type="button" onClick={() => setOpen(true)}>
        Record manual mark
      </button>
    )
  }
  return (
    <div className="confirm absentee__manual">
      <div className="field">
        <label htmlFor={`manual-${row.student_id}`}>Why are you recording this by hand? (at least {MIN_NOTE} characters)</label>
        <textarea id={`manual-${row.student_id}`} rows={2} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
      </div>
      {record.isError && (
        <p className="form-error" role="alert">
          {record.error instanceof ApiError ? record.error.message : 'The manual mark was not saved.'}
        </p>
      )}
      <div className="confirm__actions">
        <button className="btn btn--primary" type="button" disabled={note.trim().length < MIN_NOTE || record.isPending} onClick={() => record.mutate()}>
          {record.isPending ? 'Saving…' : 'Record present'}
        </button>
        <button className="btn" type="button" disabled={record.isPending} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function AbsenteeList({ rows, windowId, closed }: { rows: AbsenteeRow[]; windowId: string; closed: boolean }) {
  const byFloor = new Map<number, AbsenteeRow[]>()
  for (const row of rows) byFloor.set(row.floor, [...(byFloor.get(row.floor) ?? []), row])
  return (
    <>
      {[...byFloor.entries()].map(([floor, floorRows]) => (
        <section key={floor} className="card">
          <div className="card__head">
            <h2 className="title">Floor {floor}</h2>
            <span className="eyebrow">{floorRows.length}</span>
          </div>
          <div className="ledger">
            {floorRows.map((row) => (
              <div key={row.student_id} className="ledger__row absentee">
                <div className="ledger__main">
                  <span>{row.student_name}</span>
                  <small className="mono">{row.roll_number} · Room {row.room_number} · {row.reason_text}</small>
                </div>
                <div className="absentee__actions">
                  <StatusPill status={row.status === 'ABSENT' ? 'rejected' : 'unlit'} label={row.status === 'ABSENT' ? 'Absent' : 'Not yet marked'} />
                  {closed && <ManualMark row={row} windowId={windowId} />}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </>
  )
}

export function Absentees() {
  const query = useAbsentees()
  const data = query.data
  const open = data?.window_state === 'open'
  const closed = data?.window_state === 'closed'
  const withDevice = data?.students.filter((row) => row.device_enrolled) ?? []
  const withoutDevice = data?.students.filter((row) => !row.device_enrolled) ?? []

  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Tonight</span>
          <h1 className="display">{open ? 'Not yet marked' : 'Absentees'}</h1>
        </div>
        {data && data.window_id && (
          <span className="mono muted">
            {open ? `${data.still_to_mark} still to mark` : `${data.absent} absent`}
          </span>
        )}
      </header>

      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={Boolean(data)} />}
      {query.isPending && <p className="muted">Loading the list…</p>}

      {data && !data.window_id && (
        <EmptyState title="No window tonight">
          <p>There is no attendance window to check yet.</p>
        </EmptyState>
      )}

      {data && data.window_id && data.students.length === 0 && (
        <EmptyState title={open ? 'Everyone has marked' : 'No absentees'}>
          <p>{open ? 'Every enrolled student is present or in review.' : 'Every enrolled student is present.'}</p>
        </EmptyState>
      )}

      {data && data.window_id && withDevice.length > 0 && (
        <AbsenteeList rows={withDevice} windowId={data.window_id} closed={closed} />
      )}

      {data && data.window_id && withoutDevice.length > 0 && (
        <section className="card">
          <div className="card__head">
            <h2 className="title">No device enrolled</h2>
            <span className="eyebrow">{withoutDevice.length}</span>
          </div>
          <p className="muted">These students mark at the ground-floor scanner, not from bed.</p>
          <AbsenteeList rows={withoutDevice} windowId={data.window_id} closed={closed} />
        </section>
      )}
    </>
  )
}
