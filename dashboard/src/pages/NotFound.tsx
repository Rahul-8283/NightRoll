import { Link } from 'react-router'
import { EmptyState } from '../components/ui/EmptyState'

export function NotFound() {
  return (
    <EmptyState title="Nothing on this floor">
      <p>
        That page does not exist.{' '}
        <Link to="/" style={{ color: 'var(--lamp)' }}>
          Back to tonight
        </Link>
      </p>
    </EmptyState>
  )
}
