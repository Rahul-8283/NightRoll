import { NavLink, Outlet } from 'react-router'

const links = [
  { to: '/', label: 'Tonight' },
  { to: '/windows', label: 'Windows' },
  { to: '/enrollment', label: 'Enrollment' },
]

export function Layout() {
  return (
    <div className="layout">
      <header className="topbar">
        <strong>NightRoll</strong>
        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === '/'}>
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
