import { Navigate, Outlet } from 'react-router'
import { useAuth } from './useAuth'
import { EmptyState } from '../components/ui/EmptyState'

// Only a session that passed the authenticator code can reach any dashboard page.
export function RequireWarden() {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <div className="centered">
        <p className="muted">Checking your session…</p>
      </div>
    )
  }
  if (status === 'signed-out' || status === 'mfa-setup' || status === 'mfa-required') {
    return <Navigate to="/login" replace />
  }
  if (status === 'no-access') {
    return (
      <div className="centered">
        <EmptyState title="This account has no access">
          <p>Ask an admin to give this account the warden role. Then sign in again.</p>
        </EmptyState>
      </div>
    )
  }
  return <Outlet />
}
