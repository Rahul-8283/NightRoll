import { SCORER_LABEL } from './scorerLabels'
import type { ScorerOut } from '../api/types'

export function ScoreBars({ scorers }: { scorers: ScorerOut[] }) {
  if (scorers.length === 0) return <p className="muted">No scores were recorded for this attempt.</p>
  return (
    <div className="weights">
      {scorers.map((scorer) => (
        <div key={scorer.name} className="weight">
          <div className="weight__head">
            <span>{SCORER_LABEL[scorer.name] ?? scorer.name}</span>
            <span className="mono">{scorer.score.toFixed(2)}</span>
          </div>
          <div className="weight__bar" role="img" aria-label={`${SCORER_LABEL[scorer.name] ?? scorer.name} ${scorer.score.toFixed(2)} of 1`}>
            <span style={{ width: `${Math.round(Math.min(1, Math.max(0, scorer.score)) * 100)}%` }} />
          </div>
          <small className="muted">{scorer.detail}</small>
        </div>
      ))}
    </div>
  )
}

