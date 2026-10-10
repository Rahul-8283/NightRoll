import { createContext } from 'react'
import type { Session } from '@supabase/supabase-js'

// signed-out: no session. mfa-setup: first sign-in, the authenticator is not set up yet.
// mfa-required: password passed, the six-digit code is still needed. no-access: a session without a warden role.
export type AuthStatus = 'loading' | 'signed-out' | 'mfa-setup' | 'mfa-required' | 'no-access' | 'ready'

export type Role = 'warden' | 'admin'

export type AuthValue = {
  status: AuthStatus
  session: Session | null
  email: string | null
  role: Role | null
  refresh: () => Promise<void>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthValue | null>(null)
