import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ErrorBanner } from '../components/ErrorBanner'
import { apiDownload, ApiError, apiFetch } from '../lib/api'
import type { RoomRow } from '../api/types'

const MAX_DAYS = 31
const DAY = 86_400_000

function dateKey(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function Export() {
  const rooms = useQuery({ queryKey: ['rooms'], queryFn: () => apiFetch<RoomRow[]>('/rooms') })
  const [from, setFrom] = useState(() => dateKey(new Date(Date.now() - 6 * DAY)))
  const [to, setTo] = useState(() => dateKey(new Date()))
  const [floor, setFloor] = useState('')
  const [room, setRoom] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const days = from && to ? Math.round((Date.parse(to) - Date.parse(from)) / DAY) + 1 : 0
  const rangeError = !from || !to
    ? 'Pick both dates.'
    : days < 1
      ? 'The end date is before the start date.'
      : days > MAX_DAYS
        ? `One export covers at most ${MAX_DAYS} days.`
        : null
  const floors = [...new Set((rooms.data ?? []).map((r) => r.floor))].sort((a, b) => a - b)

  async function download() {
    setBusy(true)
    setError(null)
    const params = new URLSearchParams({ from, to })
    if (floor) params.set('floor', floor)
    if (room) params.set('room', room)
    try {
      await apiDownload(`/exports/attendance?${params.toString()}`, `nightroll-attendance-${from}-to-${to}.csv`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The export did not download. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Records</span>
          <h1 className="display">Export</h1>
        </div>
      </header>

      <section className="card form-stack">
        <p className="muted">
          One row per enrolled student per night: status, when it was marked, how it was decided and by whom. No scores, network details or biometric data.
        </p>
        {rooms.isError && <ErrorBanner error={rooms.error} onRetry={() => void rooms.refetch()} stale={false} />}
        <div className="field-row">
          <div className="field">
            <label htmlFor="export-from">From</label>
            <input id="export-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="export-to">To</label>
            <input id="export-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="export-floor">Floor</label>
            <select id="export-floor" value={floor} onChange={(e) => { setFloor(e.target.value); setRoom('') }}>
              <option value="">All floors</option>
              {floors.map((f) => (
                <option key={f} value={f}>Floor {f}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="export-room">Room</label>
            <select id="export-room" value={room} onChange={(e) => setRoom(e.target.value)}>
              <option value="">All rooms</option>
              {(rooms.data ?? [])
                .filter((r) => !floor || String(r.floor) === floor)
                .map((r) => (
                  <option key={r.id} value={r.id}>Room {r.number}</option>
                ))}
            </select>
          </div>
        </div>
        {(rangeError || error) && <p className="form-error" role="alert">{rangeError ?? error}</p>}
        <div className="confirm__actions">
          <button className="btn btn--primary" type="button" disabled={Boolean(rangeError) || busy} onClick={() => void download()}>
            {busy ? 'Preparing…' : 'Download CSV'}
          </button>
        </div>
      </section>
    </>
  )
}
