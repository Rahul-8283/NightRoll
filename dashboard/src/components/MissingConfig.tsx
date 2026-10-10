import { missingConfig } from '../config'
import { Wordmark } from './ui/Wordmark'

export function MissingConfig() {
  return (
    <div className="centered">
      <section className="auth-card">
        <Wordmark />
        <h1 className="title">Dashboard not configured</h1>
        <p className="lede">
          Set these in <code className="mono">dashboard/.env</code> and restart the dev server:
        </p>
        <p className="mono">{missingConfig.join(', ')}</p>
      </section>
    </div>
  )
}
