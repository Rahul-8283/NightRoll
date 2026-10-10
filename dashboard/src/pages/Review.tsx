import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMarkDetail, useReviewQueue } from '../api/queries'
import type { FramesView, ReviewItem } from '../api/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { ScoreBars } from '../components/ScoreBars'
import { useNow } from '../hooks/useNow'
import { EmptyState } from '../components/ui/EmptyState'
import { ApiError, postJson } from '../lib/api'
import { formatClock } from '../lib/format'

const MIN_NOTE = 10
const STALE_FINGERPRINT_DAYS = 30

function fingerprintLine(captured: string | null): { text: string; stale: boolean } {
  if (!captured) return { text: 'This room has no Wi-Fi fingerprint yet.', stale: true }
  const days = Math.floor((Date.now() - new Date(captured).getTime()) / 86_400_000)
  const when = days === 0 ? 'today' : days === 1 ? 'yesterday' : `${days} days ago`
  return {
    text: `Room Wi-Fi fingerprint captured ${when}.`,
    stale: days > STALE_FINGERPRINT_DAYS,
  }
}

function EarlierAttempts({ markId, open }: { markId: string; open: boolean }) {
  const detail = useMarkDetail(markId, open)
  if (!open) return null
  if (detail.isPending) return <p className="muted">Loading earlier attempts…</p>
  if (detail.isError) return <ErrorBanner error={detail.error} onRetry={() => void detail.refetch()} stale={false} />
  const attempts = detail.data?.earlier_attempts ?? []
  if (attempts.length === 0) return <p className="muted">No earlier attempts tonight.</p>
  return (
    <ol className="attempts">
      {attempts.map((attempt) => (
        <li key={attempt.mark_id}>
          <span className="mono">Attempt {attempt.attempt}</span> · {formatClock(attempt.marked_at)} · {attempt.verdict}
          {attempt.reasons.length > 0 && <small className="muted"> {attempt.reasons.map((r) => r.message).join(' ')}</small>}
        </li>
      ))}
    </ol>
  )
}

// Disputes only. A written reason is required and audited before any link is made. Links last 60 seconds.
function FramesViewer({ markId, available }: { markId: string; available: boolean }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [view, setView] = useState<{ data: FramesView; fetchedAt: number } | null>(null)
  const now = useNow()
  const fetchFrames = useMutation({
    mutationFn: () => postJson<FramesView>(`/attendance/marks/${markId}/frames/view`, { reason: reason.trim() }),
    onSuccess: (data) => setView({ data, fetchedAt: Date.now() }),
  })

  if (!available) {
    return <p className="muted">Frames are removed after 24 hours, so there is nothing to view for this mark.</p>
  }

  const remaining = view ? Math.max(0, view.data.expires_in_seconds - Math.floor((now - view.fetchedAt) / 1000)) : 0
  const expired = view !== null && remaining === 0

  return (
    <div className="frames" onClick={(event) => event.stopPropagation()}>
      {!open && (
        <button className="btn btn--quiet-small" type="button" onClick={() => setOpen(true)}>
          View captured frames
        </button>
      )}
      {open && !view && (
        <div className="confirm">
          <div className="field">
            <label htmlFor={`frames-reason-${markId}`}>Why do you need the frames? (at least {MIN_NOTE} characters)</label>
            <textarea id={`frames-reason-${markId}`} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
          </div>
          {fetchFrames.isError && (
            <p className="form-error" role="alert">
              {fetchFrames.error instanceof ApiError ? fetchFrames.error.message : 'The frames could not be opened.'}
            </p>
          )}
          <div className="confirm__actions">
            <button
              className="btn btn--danger"
              type="button"
              disabled={reason.trim().length < MIN_NOTE || fetchFrames.isPending}
              onClick={() => fetchFrames.mutate()}
            >
              {fetchFrames.isPending ? 'Opening…' : 'Open frames'}
            </button>
            <button className="btn" type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {view && !expired && (
        <div className="frames__viewer">
          <p className="muted" aria-live="polite">Links stop working in {remaining} seconds. Open again to refresh them.</p>
          <div className="frames__grid">
            {view.data.links.map((link) => (
              <img key={link.name} src={link.url} alt={`Captured frame ${link.name}`} loading="lazy" referrerPolicy="no-referrer" />
            ))}
          </div>
        </div>
      )}
      {view && expired && (
        <p className="muted">
          The links have expired. <button className="btn btn--quiet-small" type="button" onClick={() => { setView(null); fetchFrames.reset() }}>Open again with a new reason</button>
        </p>
      )}
    </div>
  )
}

function ReviewCard({ item, selected, declining, onSelect, onStartDecline, onCancelDecline, onDecide, busy }: {
  item: ReviewItem
  selected: boolean
  declining: boolean
  onSelect: () => void
  onStartDecline: () => void
  onCancelDecline: () => void
  onDecide: (decision: 'APPROVED' | 'DECLINED', note: string) => void
  busy: boolean
}) {
  const [note, setNote] = useState('')
  const [showAttempts, setShowAttempts] = useState(false)
  const fingerprint = fingerprintLine(item.fingerprint_created_at)
  const noteOk = note.trim().length >= MIN_NOTE

  return (
    <article className={`review-card${selected ? ' is-selected' : ''}`} onClick={onSelect} aria-current={selected}>
      <header className="review-card__head">
        <div className="ledger__main">
          <span>{item.student_name}</span>
          <small className="mono">{item.roll_number} · Room {item.room_number} · Floor {item.floor}</small>
        </div>
        <div className="review-card__meta">
          <span className="mono muted">{formatClock(item.marked_at)}</span>
          <span className="pill pill--review">In review</span>
          {item.score !== null && <span className="mono">Trust {item.score.toFixed(2)}</span>}
        </div>
      </header>

      <ScoreBars scorers={item.scorers} />

      {item.reasons.length > 0 && (
        <div className="review-card__why">
          <strong>Why it was held</strong>
          <ul>
            {item.reasons.map((reason) => (
              <li key={reason.code}>{reason.message}</li>
            ))}
          </ul>
        </div>
      )}

      <p className={fingerprint.stale ? 'form-error' : 'muted'}>
        {fingerprint.text}
        {fingerprint.stale && ' Re-scan this room’s Wi-Fi before trusting the Wi-Fi scores.'}
      </p>

      <button
        className="btn btn--quiet-small"
        type="button"
        aria-expanded={showAttempts}
        onClick={(event) => {
          event.stopPropagation()
          setShowAttempts((open) => !open)
        }}
      >
        {showAttempts ? 'Hide earlier attempts' : `Earlier attempts (${Math.max(0, item.attempts_tonight - 1)})`}
      </button>
      <EarlierAttempts markId={item.mark_id} open={showAttempts} />
      <FramesViewer markId={item.mark_id} available={item.frames_available} />

      {!declining ? (
        <div className="confirm__actions">
          <button
            className="btn btn--primary"
            type="button"
            disabled={busy}
            onClick={(event) => {
              event.stopPropagation()
              onDecide('APPROVED', '')
            }}
          >
            Approve
          </button>
          <button
            className="btn btn--danger"
            type="button"
            disabled={busy}
            onClick={(event) => {
              event.stopPropagation()
              onStartDecline()
            }}
          >
            Decline
          </button>
        </div>
      ) : (
        <div className="confirm" onClick={(event) => event.stopPropagation()}>
          <div className="field">
            <label htmlFor={`note-${item.mark_id}`}>Why are you declining? (at least {MIN_NOTE} characters)</label>
            <textarea id={`note-${item.mark_id}`} rows={3} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
          </div>
          <div className="confirm__actions">
            <button className="btn btn--danger" type="button" disabled={!noteOk || busy} onClick={() => onDecide('DECLINED', note.trim())}>
              {busy ? 'Saving…' : 'Confirm decline'}
            </button>
            <button className="btn" type="button" disabled={busy} onClick={onCancelDecline}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </article>
  )
}

export function Review() {
  const queue = useReviewQueue()
  const queryClient = useQueryClient()
  const items = useMemo(() => queue.data ?? [], [queue.data])
  const [index, setIndex] = useState(0)
  const [declining, setDeclining] = useState<string | null>(null)
  const current = Math.min(index, Math.max(0, items.length - 1))

  const decide = useMutation({
    mutationFn: ({ markId, decision, note }: { markId: string; decision: 'APPROVED' | 'DECLINED'; note: string }) =>
      postJson(`/attendance/marks/${markId}/review`, { decision, note: note || null }),
    onSuccess: () => {
      setDeclining(null)
      void queryClient.invalidateQueries({ queryKey: ['reviews'] })
      void queryClient.invalidateQueries({ queryKey: ['tonight'] })
    },
  })

  const { mutate: decideMutate, isPending: deciding } = decide

  // Keyboard: J/K or arrows move, A approves, D opens decline, Escape cancels. Ignored while typing.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      if (target?.closest('input, textarea, select')) return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const item = items[current]
      if (!item) return
      if (event.key === 'j' || event.key === 'ArrowDown') {
        event.preventDefault()
        setIndex(Math.min(current + 1, items.length - 1))
      } else if (event.key === 'k' || event.key === 'ArrowUp') {
        event.preventDefault()
        setIndex(Math.max(current - 1, 0))
      } else if (event.key === 'a' && !deciding) {
        decideMutate({ markId: item.mark_id, decision: 'APPROVED', note: '' })
      } else if (event.key === 'd') {
        setDeclining(item.mark_id)
      } else if (event.key === 'Escape') {
        setDeclining(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [items, current, deciding, decideMutate])

  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Tonight</span>
          <h1 className="display">Review</h1>
        </div>
        <span className="mono muted">{items.length} waiting</span>
      </header>

      {queue.isError && <ErrorBanner error={queue.error} onRetry={() => void queue.refetch()} stale={Boolean(queue.data)} />}
      {decide.isError && (
        <p className="form-error" role="alert">
          {decide.error instanceof ApiError ? decide.error.message : 'The decision did not save. Try again.'}
        </p>
      )}

      {queue.isPending && <p className="muted">Loading the queue…</p>}
      {queue.data && items.length === 0 && (
        <EmptyState title="Nothing waiting for review">
          <p>Borderline marks appear here as students mark attendance.</p>
        </EmptyState>
      )}

      {items.length > 0 && (
        <>
          <p className="muted review-hint">
            Shortcuts: <span className="mono">J</span>/<span className="mono">K</span> move · <span className="mono">A</span> approve · <span className="mono">D</span> decline · <span className="mono">Esc</span> cancel
          </p>
          <div className="review-list">
            {items.map((item, i) => (
              <ReviewCard
                key={item.mark_id}
                item={item}
                selected={i === current}
                declining={declining === item.mark_id}
                onSelect={() => setIndex(i)}
                onStartDecline={() => setDeclining(item.mark_id)}
                onCancelDecline={() => setDeclining(null)}
                onDecide={(decision, note) => decide.mutate({ markId: item.mark_id, decision, note })}
                busy={decide.isPending}
              />
            ))}
          </div>
        </>
      )}
    </>
  )
}
