import { NavLink, Outlet } from 'react-router'
import { useTonight } from '../api/queries'
import { useAuth } from '../auth/useAuth'
import { LiveProvider } from '../live/LiveProvider'
import { TopBar } from './TopBar'
import { Wordmark } from './ui/Wordmark'

const links = [
  { to: '/dashboard', label: 'Tonight', end: true },
  { to: '/dashboard/review', label: 'Review', end: false },
  { to: '/dashboard/absentees', label: 'Absentees', end: false },
  { to: '/dashboard/export', label: 'Export', end: false },
  { to: '/dashboard/windows', label: 'Windows', end: false },
  { to: '/dashboard/enrollment', label: 'Enrollment', end: false },
]

// Phase 11 pages are listed so the layout is complete, and stay inactive until they are built.
const later: string[] = []

const adminLinks = [{ to: '/dashboard/audit', label: 'Audit', end: false }]

export function Layout() {
  const { email, role, signOut } = useAuth()
  const navLinks = role === 'admin' ? [...links, ...adminLinks] : links
  const { data } = useTonight()
  const pending = data?.totals.pending_review ?? 0

  return (
    <LiveProvider>
      <div className="shell">
        <aside className="rail">
          <Wordmark />
          <nav className="rail__nav" aria-label="Main">
            {navLinks.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end} className="rail__link">
                <span className="rail__dot" aria-hidden="true" />
                {link.label}
                {link.to === '/dashboard/review' && pending > 0 && (
                  <span className="rail__count" aria-label={`${pending} waiting for review`}>{pending}</span>
                )}
              </NavLink>
            ))}
            {later.map((label) => (
              <span key={label} className="rail__link is-disabled" aria-disabled="true" title="Arrives in Phase 11">
                <span className="rail__dot" aria-hidden="true" />
                {label}
              </span>
            ))}
          </nav>
          <div className="rail__foot">
            <strong>{role === 'admin' ? 'Admin' : 'Warden'}</strong>
            <span className="mono">{email}</span>
            <button className="btn btn--quiet-small" type="button" onClick={() => void signOut()}>
              Sign out
            </button>
          </div>
        </aside>
        <main className="page">
          <TopBar />
          <Outlet />
        </main>
      </div>
    </LiveProvider>
  )
}
