import { missingConfig } from '../config'

export function MissingConfig() {
  return (
    <section>
      <h1>Dashboard not configured</h1>
      <p>Set these in dashboard/.env and restart the dev server: {missingConfig.join(', ')}</p>
    </section>
  )
}
