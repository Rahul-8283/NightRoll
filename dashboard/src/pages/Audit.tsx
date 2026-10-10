import { useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/useAuth'
import { ErrorBanner } from '../components/ErrorBanner'
import { EmptyState } from '../components/ui/EmptyState'
import { apiFetch } from '../lib/api'
import { formatClock } from '../lib/format'

type AuditRow = {
  id: number
  created_at: string
  actor: string
  action: string
  target_id: string | null
  payload: Record<string, unknown> | null
}

type AuditPage = { items: AuditRow[]; next_before: number | null }

const ACTION_LABEL: Record<string, string> = {
  'attendance.attempt': 'Student attempt',
  'attendance.manual': 'Manual mark',
  'export.created': 'Export',
  'frames.viewed': 'Frames viewed',
  'mark.overridden': 'Override',
  'review.decided': 'Review decision',
  'room.fingerprint_captured': 'Fingerprint captured',
  'room.fingerprint_reset': 'Fingerprint reset',
  'student.consent_withdrawn': 'Consent withdrawn',
  'student.enrolled': 'Student enrolled',
  'student.room_changed': 'Room changed',
  'enrollment.code_created': 'Enrollment code created',
  'window.create': 'Window created',
  'window.update': 'Window changed',
  'window.open': 'Window opened',
  'window.close': 'Window closed',
  'window.off': 'Night marked off',
}

function describe(row: AuditRow): string {
  const note = typeof row.payload?.note === 'string' ? row.payload.note : null
  const reason = typeof row.payload?.reason === 'string' ? row.payload.reason : null
  return note ?? reason ?? ''
}

export function Audit() {
  const { role } = useAuth()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')

  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  if (actor.trim()) params.set('actor', actor.trim())
  if (action) params.set('action', action)

  const query = useInfiniteQuery({
    queryKey: ['audit', params.toString()],
    queryFn: ({ pageParam }) => {
      const page = new URLSearchParams(params)
      if (pageParam) page.set('before', String(pageParam))
      return apiFetch<AuditPage>(`/audit?${page.toString()}`)
    },
    initialPageParam: null as number | null,
    getNextPageParam: (last) => last.next_before,
    enabled: role === 'admin',
  })

  if (role !== 'admin') {
    return (
      <EmptyState title="Admins only">
        <p>The audit trail is for admins. Ask an admin if you need to see an entry.</p>
      </EmptyState>
    )
  }

  const rows = query.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Read only</span>
          <h1 className="display">Audit</h1>
        </div>
      </header>

      <section className="card form-stack">
        <div className="field-row">
          <div className="field">
            <label htmlFor="audit-from">From</label>
            <input id="audit-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="audit-to">To</label>
            <input id="audit-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="audit-actor">Person (email or ID)</label>
            <input id="audit-actor" value={actor} onChange={(e) => setActor(e.target.value)} autoComplete="off" />
          </div>
          <div className="field">
            <label htmlFor="audit-action">Action</label>
            <select id="audit-action" value={action} onChange={(e) => setAction(e.target.value)}>
              <option value="">All actions</option>
              {Object.entries(ACTION_LABEL).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={rows.length > 0} />}
      {query.isPending && <p className="muted">Loading the log…</p>}
      {query.data && rows.length === 0 && (
        <EmptyState title="No entries match">
          <p>Try a wider date range or another action.</p>
        </EmptyState>
      )}

      {rows.length > 0 && (
        <section className="card">
          <div className="ledger">
            {rows.map((row) => (
              <div key={row.id} className="ledger__row audit__row">
                <span className="mono muted audit__time">
                  {new Date(row.created_at).toLocaleDateString('en-GB')} {formatClock(row.created_at)}
                </span>
                <div className="ledger__main">
                  <span>{ACTION_LABEL[row.action] ?? row.action}</span>
                  <small className="mono">{row.actor}{row.target_id ? ` · ${row.target_id}` : ''}</small>
                  {describe(row) && <small>{describe(row)}</small>}
                </div>
              </div>
            ))}
          </div>
          {query.hasNextPage && (
            <div className="confirm__actions">
              <button className="btn" type="button" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
                {query.isFetchingNextPage ? 'Loading…' : 'Load older entries'}
              </button>
            </div>
          )}
        </section>
      )}
    </>
  )
}
