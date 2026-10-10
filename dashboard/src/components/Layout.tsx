import { NavLink, Outlet } from 'react-router'
import { Wordmark } from './ui/Wordmark'

const links = [
  { to: '/dashboard', label: 'Tonight' },
  { to: '/dashboard/windows', label: 'Windows' },
  { to: '/dashboard/enrollment', label: 'Enrollment' },
]

export function Layout() {
  return (
    <div className="shell">
      <aside className="rail">
        <Wordmark />
        <nav className="rail__nav" aria-label="Main">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === '/dashboard'} className="rail__link">
              <span className="rail__dot" aria-hidden="true" />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail__foot">
          <strong>Warden desk</strong>
          Sign-in arrives in Phase 10.
        </div>
      </aside>
      <main className="page">
        <Outlet />
      </main>
    </div>
  )
}
