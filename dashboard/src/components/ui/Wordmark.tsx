// The mark is a single lit window: four panes, one of them on.
export function Wordmark() {
  return (
    <span className="wordmark">
      <svg width="26" height="30" viewBox="0 0 26 30" aria-hidden="true">
        <rect x="0.5" y="0.5" width="25" height="29" rx="5" fill="#181c28" stroke="#262b3c" />
        <rect x="4" y="4" width="8" height="10" rx="1.5" fill="#f5b95c" />
        <rect x="14" y="4" width="8" height="10" rx="1.5" fill="#0b0d13" />
        <rect x="4" y="16" width="8" height="10" rx="1.5" fill="#0b0d13" />
        <rect x="14" y="16" width="8" height="10" rx="1.5" fill="#0b0d13" />
      </svg>
      <span className="wordmark__name">
        Night<em>Roll</em>
      </span>
    </span>
  )
}
