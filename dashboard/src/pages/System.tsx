import { useSystem } from '../api/queries'
import type { SystemOverview } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { ErrorBanner } from '../components/ErrorBanner'
import { EmptyState } from '../components/ui/EmptyState'
import { StatusPill } from '../components/ui/StatusPill'
import type { Status } from '../components/ui/status'
import { formatClock } from '../lib/format'

const HEALTH: Record<'ok' | 'degraded' | 'down', { status: Status; label: string }> = {
  ok: { status: 'present', label: 'Healthy' },
  degraded: { status: 'review', label: 'Degraded' },
  down: { status: 'rejected', label: 'Down' },
}

function ms(value: number | null): string {
  return value === null ? 'No data yet' : `${Math.round(value)} ms`
}

function when(iso: string | null): string {
  if (!iso) return 'Not run yet'
  return `${new Date(iso).toLocaleDateString('en-GB')} ${formatClock(iso)}`
}

function ago(seconds: number | null): string {
  if (seconds === null) return 'never seen'
  if (seconds < 90) return `${Math.round(seconds)} seconds ago`
  return `${Math.round(seconds / 60)} minutes ago`
}

function Service({ name, health, note }: { name: string; health: 'ok' | 'degraded' | 'down'; note?: string | null }) {
  return (
    <div className="ledger__row">
      <div className="ledger__main">
        <span>{name}</span>
        {note && <small>{note}</small>}
      </div>
      <StatusPill status={HEALTH[health].status} label={HEALTH[health].label} />
    </div>
  )
}

function Services({ system }: { system: SystemOverview }) {
  const { face_worker: face, scheduler } = system
  return (
    <section className="card" aria-labelledby="system-services">
      <div className="card__head">
        <h2 className="title" id="system-services">Services</h2>
        <span className="eyebrow">{system.app_env}</span>
      </div>
      <div className="ledger">
        <Service name="Database" health={system.database.status} />
        <Service name="Redis" health={system.redis.status} />
        <Service
          name="Face worker"
          health={face.status}
          note={
            face.status === 'down'
              ? (face.detail ?? 'The face worker did not answer')
              : `${face.model_version ?? 'No model'} · answers in ${ms(face.latency_ms)}${face.antispoof_available ? '' : ' · anti-spoof model missing'}`
          }
        />
        <Service
          name="Scheduler"
          health={scheduler.status}
          note={scheduler.last_heartbeat ? `Last checked in ${ago(scheduler.age_seconds)}` : 'No heartbeat has been recorded'}
        />
      </div>
    </section>
  )
}

function Tonight({ system }: { system: SystemOverview }) {
  const { tonight } = system
  const rate = tonight.rejection_rate_5m
  return (
    <section className="card" aria-labelledby="system-tonight">
      <div className="card__head">
        <h2 className="title" id="system-tonight">Tonight&apos;s attempts</h2>
        <span className="eyebrow">{tonight.attempts} in all</span>
      </div>
      <div className="system__counts">
        <div>
          <span className="tally__value">{tonight.verdicts.PRESENT ?? 0}</span>
          <span className="muted">Present</span>
        </div>
        <div>
          <span className="tally__value">{tonight.verdicts.NEEDS_REVIEW ?? 0}</span>
          <span className="muted">In review</span>
        </div>
        <div>
          <span className="tally__value">{tonight.verdicts.REJECTED ?? 0}</span>
          <span className="muted">Rejected</span>
        </div>
      </div>
      <p className="muted system__note">
        {rate === null
          ? 'No attempts in the last five minutes.'
          : `${Math.round(rate * 100)}% of the ${tonight.attempts_5m} attempts in the last five minutes were rejected.`}
      </p>
      <h3 className="eyebrow system__sub">Stopped at a gate</h3>
      {tonight.gate_failures.length === 0 ? (
        <p className="muted">No attempt has been stopped at a gate tonight.</p>
      ) : (
        <div className="ledger">
          {tonight.gate_failures.map((failure) => (
            <div key={failure.reason} className="ledger__row">
              <div className="ledger__main">
                <span className="mono">{failure.reason}</span>
                <small>{failure.message}</small>
              </div>
              <span className="mono">{failure.count}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function System() {
  const { role } = useAuth()
  const query = useSystem(role === 'admin')

  if (role !== 'admin') {
    return (
      <EmptyState title="Admins only">
        <p>The System page is for admins. Ask an admin if something looks wrong.</p>
      </EmptyState>
    )
  }

  const system = query.data
  return (
    <>
      <header className="page__head">
        <div>
          <span className="eyebrow">Refreshes every 10 seconds</span>
          <h1 className="display">System</h1>
        </div>
        {system && <span className="muted mono">Version {system.version}</span>}
      </header>

      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} stale={Boolean(system)} />}
      {query.isPending && <p className="muted">Checking the services…</p>}

      {system && system.relaxed_settings.length > 0 && (
        <div className="banner banner--moon" role="note">
          <div className="banner__text">
            <strong>Relaxed settings are on</strong>
            <ul className="system__relaxed">
              {system.relaxed_settings.map((line) => (
                <li key={line} className="muted">{line}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {system && (
        <div className="grid-2">
          <div className="stack">
            <Services system={system} />
            <Tonight system={system} />
          </div>
          <div className="stack">
            <section className="card" aria-labelledby="system-latency">
              <div className="card__head">
                <h2 className="title" id="system-latency">Speed</h2>
                <span className="eyebrow">Since the API started</span>
              </div>
              <div className="ledger">
                <div className="ledger__row"><span>Requests, typical</span><span className="mono">{ms(system.latency.requests_p50_ms)}</span></div>
                <div className="ledger__row"><span>Requests, slowest 5%</span><span className="mono">{ms(system.latency.requests_p95_ms)}</span></div>
                <div className="ledger__row"><span>Marking, slowest 5%</span><span className="mono">{ms(system.latency.verify_p95_ms)}</span></div>
                <div className="ledger__row"><span>Face worker, slowest 5%</span><span className="mono">{ms(system.latency.face_worker_p95_ms)}</span></div>
                <div className="ledger__row"><span>Dashboards connected</span><span className="mono">{system.websocket_connections}</span></div>
              </div>
            </section>
            <section className="card" aria-labelledby="system-jobs">
              <div className="card__head">
                <h2 className="title" id="system-jobs">Housekeeping</h2>
              </div>
              <div className="ledger">
                {system.jobs.map((job) => (
                  <div key={job.name} className="ledger__row">
                    <div className="ledger__main">
                      <span>{job.name}</span>
                      <small>{job.detail ?? 'Waiting for its first run'}</small>
                    </div>
                    <span className="mono muted">{when(job.last_run)}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}
    </>
  )
}
