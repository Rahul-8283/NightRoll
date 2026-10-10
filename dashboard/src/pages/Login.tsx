import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { supabase } from '../lib/supabase'
import { Wordmark } from '../components/ui/Wordmark'

export function Login() {
  const { status, refresh, signOut } = useAuth()

  if (status === 'ready') return <Navigate to="/dashboard" replace />
  if (status === 'loading') {
    return (
      <div className="centered">
        <p className="muted">Checking your session…</p>
      </div>
    )
  }

  return (
    <div className="centered">
      <section className="auth-card">
        <Wordmark />
        {status === 'no-access' && <NoAccess onSignOut={signOut} />}
        {status === 'signed-out' && <PasswordStep />}
        {status === 'mfa-setup' && <SetupStep onDone={refresh} />}
        {status === 'mfa-required' && <CodeStep onDone={refresh} />}
      </section>
    </div>
  )
}

function NoAccess({ onSignOut }: { onSignOut: () => Promise<void> }) {
  return (
    <>
      <div>
        <h1 className="title">This account has no access</h1>
        <p className="muted">Ask an admin to give this account the warden role.</p>
      </div>
      <button className="btn" type="button" onClick={() => void onSignOut()}>
        Sign out
      </button>
    </>
  )
}

function PasswordStep() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password })
    setBusy(false)
    if (signInError) setError('That email and password do not match an account.')
  }

  return (
    <>
      <div>
        <h1 className="title">Warden sign-in</h1>
        <p className="muted">Sign in with your warden account. Accounts are created by an admin.</p>
      </div>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Continue'}
        </button>
      </form>
    </>
  )
}

function CodeStep({ onDone }: { onDone: () => Promise<void> }) {
  const [factorId, setFactorId] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void supabase.auth.mfa.listFactors().then(({ data }) => {
      setFactorId(data?.totp.find((factor) => factor.status === 'verified')?.id ?? null)
    })
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!factorId) return
    setBusy(true)
    setError(null)
    const { error: verifyError } = await supabase.auth.mfa.challengeAndVerify({ factorId, code })
    setBusy(false)
    if (verifyError) {
      setError('That code is not right. Codes change every 30 seconds.')
      return
    }
    await onDone()
  }

  return (
    <>
      <div>
        <h1 className="title">Enter your code</h1>
        <p className="muted">Open your authenticator app and enter the six-digit code for NightRoll.</p>
      </div>
      <form onSubmit={submit}>
        <CodeInput value={code} onChange={setCode} />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="btn btn--primary" type="submit" disabled={busy || !factorId || code.length !== 6}>
          {busy ? 'Checking…' : 'Sign in'}
        </button>
      </form>
    </>
  )
}

function SetupStep({ onDone }: { onDone: () => Promise<void> }) {
  const [factor, setFactor] = useState<{ id: string; qr: string; secret: string } | null>(null)
  const [setupError, setSetupError] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    void supabase.auth.mfa.enroll({ factorType: 'totp', friendlyName: 'NightRoll' }).then(({ data, error: enrollError }) => {
      if (enrollError || !data) {
        setSetupError('Could not start authenticator setup. Refresh the page and try again.')
        return
      }
      setFactor({ id: data.id, qr: data.totp.qr_code, secret: data.totp.secret })
    })
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!factor) return
    setBusy(true)
    setError(null)
    const { error: verifyError } = await supabase.auth.mfa.challengeAndVerify({ factorId: factor.id, code })
    setBusy(false)
    if (verifyError) {
      setError('That code is not right. Check the time on your phone and try the next code.')
      return
    }
    await onDone()
  }

  return (
    <>
      <div>
        <h1 className="title">Set up your authenticator</h1>
        <p className="muted">
          Scan this code with an authenticator app, then enter the six-digit code it shows.
        </p>
      </div>
      {setupError && <p className="form-error" role="alert">{setupError}</p>}
      {factor && (
        <>
          <div className="qr-frame">
            <img src={factor.qr} alt="Scan this code with your authenticator app" width={180} height={180} />
          </div>
          <p className="muted">
            Cannot scan? Enter this key instead: <code className="mono secret-key">{factor.secret}</code>
          </p>
          <form onSubmit={submit}>
            <CodeInput value={code} onChange={setCode} />
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn btn--primary" type="submit" disabled={busy || code.length !== 6}>
              {busy ? 'Checking…' : 'Finish setup'}
            </button>
          </form>
        </>
      )}
    </>
  )
}

function CodeInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="field">
      <label htmlFor="otp">Six-digit code</label>
      <input
        id="otp"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        pattern="[0-9]{6}"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))}
        required
      />
    </div>
  )
}
