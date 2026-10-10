import { Link, useNavigate } from 'react-router'
import { Wordmark } from '../components/ui/Wordmark'
import { config } from '../config'

export function Login() {
  const navigate = useNavigate()
  return (
    <div className="centered">
      <section className="auth-card">
        <Wordmark />
        <div>
          <h1 className="title">Warden access</h1>
          <p className="muted">Sign up for a warden account or sign in. Then enter the 6-digit code from your authenticator app.</p>
        </div>
        <form onSubmit={(event) => { event.preventDefault(); navigate('/dashboard') }}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="username" placeholder="warden@college.edu" />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete="current-password" />
          </div>
          <button className="btn btn--primary" type="submit">
            Continue
          </button>
        </form>
        <p className="muted">
          Sign-in is connected in Phase 10.{' '}
          {config.sampleData && (
            <Link to="/dashboard" style={{ color: 'var(--lamp)' }}>
              Open the dashboard preview
            </Link>
          )}
        </p>
      </section>
    </div>
  )
}
