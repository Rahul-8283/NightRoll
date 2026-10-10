import type { ReactNode } from 'react'

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="empty">
      <h2 className="title">{title}</h2>
      <div className="lede">{children}</div>
    </section>
  )
}

// Shown by every page until Phase 10 connects it to the API.
export function NotConnected({ what }: { what: string }) {
  return (
    <EmptyState title="Not connected yet">
      <p>
        {what} is wired to the live API in Phase 10. To look at this page now, set <code className="mono">VITE_SAMPLE_DATA=true</code> in{' '}
        <code className="mono">dashboard/.env</code> and restart the dev server.
      </p>
    </EmptyState>
  )
}
