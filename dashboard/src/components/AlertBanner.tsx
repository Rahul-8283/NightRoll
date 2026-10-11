import { useAlerts } from '../api/queries'

// Problems the system itself has: the face worker is down while attendance is open, the scheduler has stopped
// checking in, or too many attempts are being rejected. Critical ones are ember, warnings are moon.
export function AlertBanner() {
  const { data: alerts } = useAlerts()
  if (!alerts || alerts.length === 0) return null

  return (
    <div className="alerts" role="region" aria-label="System alerts">
      {alerts.map((alert) => (
        <div
          key={alert.code}
          className={`banner ${alert.severity === 'critical' ? 'banner--ember' : 'banner--moon'}`}
          role="alert"
        >
          <div className="banner__text">
            <strong>{alert.severity === 'critical' ? 'Needs attention now' : 'Keep an eye on this'}</strong>
            <span className="muted">{alert.message}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
