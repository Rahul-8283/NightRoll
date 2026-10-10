import { STATUS_LABEL, type Status } from './status'

export function StatusPill({ status, label }: { status: Status; label?: string }) {
  return (
    <span className={`pill pill--${status}`}>
      <span className={`swatch swatch--${status}`} aria-hidden="true" />
      {label ?? STATUS_LABEL[status]}
    </span>
  )
}
