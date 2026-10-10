import { ApiError } from '../lib/api'

type Props = {
  error: unknown
  onRetry: () => void
  /** True when older data is still on screen and is shown greyed. */
  stale: boolean
}

// Explains a failed request in plain words, with the API's request ID when there is one.
export function ErrorBanner({ error, onRetry, stale }: Props) {
  const unreachable = error instanceof ApiError && error.code === 'NETWORK'
  const detail = error instanceof ApiError ? error.message : 'Something went wrong.'
  const requestId = error instanceof ApiError ? error.requestId : undefined

  return (
    <div className="banner banner--ember" role="alert">
      <div className="banner__text">
        <strong>{unreachable ? 'Cannot reach the NightRoll API' : 'The last request failed'}</strong>
        <span className="muted">
          {stale ? ' Showing the last known data. ' : ' '}
          {detail}
          {requestId ? ` Request ID ${requestId}.` : ''}
        </span>
      </div>
      <button className="btn btn--quiet-small" type="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}
