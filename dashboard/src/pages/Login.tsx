import { Link } from 'react-router'
import { Wordmark } from '../components/ui/Wordmark'
import { config } from '../config'

export function Login() {
  return (
    <div className="centered">
      <section className="auth-card">
        <Wordmark />
        <div>
          <h1 className="title">Warden sign-in</h1>
          <p className="muted">Email, password, then the 6-digit code from your authenticator app.</p>
        </div>
        <form onSubmit={(event) => event.preventDefault()}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="username" placeholder="warden@college.edu" disabled />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete="current-password" disabled />
          </div>
          <button className="btn btn--primary" type="submit" disabled>
            Sign in
          </button>
        </form>
        <p className="muted">
          Sign-in is connected in Phase 10.{' '}
          {config.sampleData && (
            <Link to="/" style={{ color: 'var(--lamp)' }}>
              Preview the dashboard
            </Link>
          )}
        </p>
      </section>
    </div>
  )
}
