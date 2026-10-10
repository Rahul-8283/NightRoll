import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'
import { AuthContext, type AuthStatus, type AuthValue, type Role } from './context'

async function derive(session: Session | null): Promise<{ status: AuthStatus; role: Role | null }> {
  if (!session) return { status: 'signed-out', role: null }
  const role = session.user.app_metadata?.role
  if (role !== 'warden' && role !== 'admin') return { status: 'no-access', role: null }
  const { data } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel()
  if (data?.currentLevel === 'aal2') return { status: 'ready', role }
  if (data?.nextLevel === 'aal2') return { status: 'mfa-required', role }
  return { status: 'mfa-setup', role }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [session, setSession] = useState<Session | null>(null)
  const [role, setRole] = useState<Role | null>(null)

  const apply = useCallback(async (next: Session | null) => {
    const result = await derive(next)
    setSession(next)
    setRole(result.role)
    setStatus(result.status)
  }, [])

  // Supabase reports the current session on subscribe (INITIAL_SESSION), then every change, refresh and sign-out.
  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      void apply(next)
    })
    return () => data.subscription.unsubscribe()
  }, [apply])

  const refresh = useCallback(async () => {
    const { data } = await supabase.auth.getSession()
    await apply(data.session)
  }, [apply])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    await apply(null)
  }, [apply])

  const value = useMemo<AuthValue>(
    () => ({ status, session, email: session?.user.email ?? null, role, refresh, signOut }),
    [status, session, role, refresh, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
