import type { ReactNode } from 'react'

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="empty">
      <h2 className="title">{title}</h2>
      <div className="lede">{children}</div>
    </section>
  )
}

