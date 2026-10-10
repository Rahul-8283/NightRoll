import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/useAuth'
import { useTonight } from '../api/queries'
import type { WindowBrief, WindowHistory, WindowState } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { StatusPill } from '../components/ui/StatusPill'
import { apiFetch, ApiError, postJson } from '../lib/api'
import { formatClock } from '../lib/format'

const STATE_LABEL: Record<WindowState, string> = {
  scheduled: 'Scheduled',
  open: 'Open',
  closed: 'Closed',
  off: 'Off',
}

// Short labels for the small calendar cells. The full word stays in the accessible name.
const CELL_LABEL: Record<WindowState, string> = {
  scheduled: 'Planned',
  open: 'Open',
  closed: 'Done',
  off: 'Off',
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

// The calendar and the API both use the local date as YYYY-MM-DD.
function dateKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function useWindows() {
  return useQuery({
    queryKey: ['windows'],
    queryFn: () => apiFetch<WindowBrief[]>('/windows'),
  })
}

function useHistory() {
  return useQuery({
    queryKey: ['windowHistory'],
    queryFn: () => apiFetch<WindowHistory[]>('/windows/history'),
  })
}

// Admin-only controls for the window that is running tonight. Each needs a second press to confirm.
function AdminControls({ windowId, state }: { windowId: string; state: WindowState }) {
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<'open-now' | 'close-now' | null>(null)
  const action = useMutation({
    mutationFn: (path: 'open-now' | 'close-now') => postJson<WindowBrief>(`/windows/${windowId}/${path}`, {}),
    onSuccess: () => {
      setPending(null)
      void queryClient.invalidateQueries({ queryKey: ['tonight'] })
      void queryClient.invalidateQueries({ queryKey: ['windows'] })
    },
  })

  const canOpen = state === 'scheduled' || state === 'closed'
  const canClose = state === 'open'
  if (!canOpen && !canClose) return null

  const label = pending === 'open-now' ? 'Open the window now?' : 'Close the window now?'
  return (
    <div className="admin-controls">
      {pending === null && (
        <div className="confirm__actions">
          {canOpen && (
            <button className="btn btn--primary" type="button" onClick={() => setPending('open-now')}>
              Open now
            </button>
          )}
          {canClose && (
            <button className="btn btn--danger" type="button" onClick={() => setPending('close-now')}>
              Close now
            </button>
          )}
        </div>
      )}
      {pending !== null && (
        <div className="confirm">
          <p>{label} Students can mark or stop marking straight away.</p>
          {action.isError && (
            <p className="form-error" role="alert">
              {action.error instanceof ApiError ? action.error.message : 'That did not go through. Try again.'}
            </p>
          )}
          <div className="confirm__actions">
            <button className="btn btn--danger" type="button" disabled={action.isPending} onClick={() => action.mutate(pending)}>
              {action.isPending ? 'Working…' : 'Yes, do it'}
            </button>
            <button className="btn" type="button" disabled={action.isPending} onClick={() => setPending(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function Windows() {
  const queryClient = useQueryClient()
  const { role } = useAuth()
  const tonight = useTonight()
  const windows = useWindows()
  const history = useHistory()

  const [night, setNight] = useState(() => dateKey(new Date()))
  const [opens, setOpens] = useState('22:00')
  const [closes, setCloses] = useState('22:30')
  const [month, setMonth] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [formError, setFormError] = useState<string | null>(null)

  const byNight = new Map((windows.data ?? []).map((item) => [item.night, item]))
  const selected = byNight.get(night)
  const tonightWindow = tonight.data?.window

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['windows'] })
    void queryClient.invalidateQueries({ queryKey: ['tonight'] })
    void queryClient.invalidateQueries({ queryKey: ['windowHistory'] })
  }

  const save = useMutation({
    mutationFn: (body: { night: string; opens_at: string; closes_at: string; off: boolean }) =>
      postJson<WindowBrief>('/windows', body),
    onSuccess: refresh,
  })

  // Times are read in the warden's local zone and sent with their offset. A closing time before the opening one means the next morning.
  function timesFor(): { opens_at: string; closes_at: string } {
    const opensAt = new Date(`${night}T${opens}`)
    const closesAt = new Date(`${night}T${closes}`)
    if (closesAt <= opensAt) closesAt.setDate(closesAt.getDate() + 1)
    return { opens_at: opensAt.toISOString(), closes_at: closesAt.toISOString() }
  }

  function submitWindow(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    if (!night || !opens || !closes) {
      setFormError('Pick a date and both times.')
      return
    }
    save.mutate({ night, ...timesFor(), off: false }, {
      onError: (error) => setFormError(error instanceof ApiError ? error.message : 'The window was not saved.'),
    })
  }

  function markOff() {
    setFormError(null)
    save.mutate({ night, ...timesFor(), off: true }, {
      onError: (error) => setFormError(error instanceof ApiError ? error.message : 'The night was not marked off.'),
    })
  }

  const firstWeekday = (month.getDay() + 6) % 7
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const cells: (number | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Nights and windows</span>
          <h1 className="display">Windows</h1>
        </div>
      </header>

      {windows.isError && <ErrorBanner error={windows.error} onRetry={() => void windows.refetch()} stale={Boolean(windows.data)} />}

      <section className="card">
        <div className="card__head">
          <h2 className="title">Tonight</h2>
          {tonightWindow ? (
            <StatusPill status={tonightWindow.state === 'open' ? 'present' : 'unlit'} label={STATE_LABEL[tonightWindow.state]} />
          ) : (
            <span className="eyebrow">None set</span>
          )}
        </div>
        {tonightWindow ? (
          <>
            <p className="muted">
              {tonightWindow.night} · opens {formatClock(tonightWindow.opens_at)} · closes {formatClock(tonightWindow.closes_at)}
            </p>
            {role === 'admin' && <AdminControls windowId={tonightWindow.id} state={tonightWindow.state} />}
          </>
        ) : (
          <p className="muted">No window is set for tonight. Set one below.</p>
        )}
      </section>

      <div className="grid-2">
        <section className="card">
          <div className="card__head">
            <h2 className="title">Set a window</h2>
            {selected && <span className="eyebrow">{STATE_LABEL[selected.state]} for {selected.night}</span>}
          </div>
          <form onSubmit={submitWindow} className="form-stack">
            <div className="field">
              <label htmlFor="night">Night</label>
              <input id="night" type="date" value={night} onChange={(e) => setNight(e.target.value)} required />
            </div>
            <div className="field-row">
              <div className="field">
                <label htmlFor="opens">Opens</label>
                <input id="opens" type="time" value={opens} onChange={(e) => setOpens(e.target.value)} required />
              </div>
              <div className="field">
                <label htmlFor="closes">Closes</label>
                <input id="closes" type="time" value={closes} onChange={(e) => setCloses(e.target.value)} required />
              </div>
            </div>
            {formError && <p className="form-error" role="alert">{formError}</p>}
            <div className="confirm__actions">
              <button className="btn btn--primary" type="submit" disabled={save.isPending}>
                {save.isPending ? 'Saving…' : 'Save window'}
              </button>
              <button className="btn" type="button" disabled={save.isPending} onClick={markOff}>
                Mark this night off
              </button>
            </div>
          </form>
        </section>

        <section className="card">
          <div className="card__head">
            <h2 className="title">Calendar</h2>
            <div className="calendar__nav">
              <button className="btn btn--quiet-small" type="button" aria-label="Previous month"
                onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>
                ‹
              </button>
              <span className="mono">{month.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })}</span>
              <button className="btn btn--quiet-small" type="button" aria-label="Next month"
                onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>
                ›
              </button>
            </div>
          </div>
          <div className="calendar" role="grid" aria-label="Nights">
            {WEEKDAYS.map((day) => (
              <span key={day} className="calendar__weekday">{day}</span>
            ))}
            {cells.map((day, index) => {
              if (day === null) return <span key={`blank-${index}`} />
              const key = dateKey(new Date(month.getFullYear(), month.getMonth(), day))
              const item = byNight.get(key)
              const classes = ['calendar__day', key === night && 'is-selected', item?.state === 'off' && 'is-off']
                .filter(Boolean)
                .join(' ')
              return (
                <button key={key} type="button" className={classes} onClick={() => setNight(key)}
                  aria-label={`${key}${item ? `, ${STATE_LABEL[item.state]}` : ''}`}>
                  <span>{day}</span>
                  {item && <span className="calendar__state" aria-hidden="true">{CELL_LABEL[item.state]}</span>}
                </button>
              )
            })}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card__head">
          <h2 className="title">Past nights</h2>
          <span className="eyebrow">{history.data?.length ?? 0} nights</span>
        </div>
        {history.isError && <ErrorBanner error={history.error} onRetry={() => void history.refetch()} stale={false} />}
        {history.data && history.data.length === 0 && <p className="muted">No past windows yet.</p>}
        {history.data && history.data.length > 0 && (
          <div className="ledger">
            {history.data.map((past) => (
              <div key={past.id} className="ledger__row">
                <div className="ledger__main">
                  <span>{past.night}</span>
                  <small>{STATE_LABEL[past.state]}</small>
                </div>
                <span className="mono">
                  {past.present} of {past.enrolled} in
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
