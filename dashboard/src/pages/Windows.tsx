import { NotConnected } from '../components/ui/EmptyState'
import { SampleNote } from '../components/ui/SampleNote'
import { StatusPill } from '../components/ui/StatusPill'
import { config } from '../config'
import { SAMPLE_NIGHTS, SAMPLE_WINDOW } from '../sample/hostel'

// The timeline runs 21:30 to 23:00, so 22:00-22:30 sits a third of the way in.
const TICKS = ['21:30', '22:00', '22:30', '23:00']

export function Windows() {
  if (!config.sampleData) {
    return (
      <>
        <header className="page__head">
          <div>
            <span className="eyebrow">Attendance windows</span>
            <h1 className="display">Windows</h1>
          </div>
        </header>
        <NotConnected what="Setting and reviewing windows" />
      </>
    )
  }

  return (
    <>
      <SampleNote />
      <header className="page__head">
        <div>
          <span className="eyebrow">Attendance windows</span>
          <h1 className="display">
            Open from <em>{SAMPLE_WINDOW.opens}</em> to <em>{SAMPLE_WINDOW.closes}</em>
          </h1>
          <p className="lede">Students can mark only inside this window. Times follow the server clock.</p>
        </div>
        <StatusPill status="present" label="Open now" />
      </header>

      <div className="grid-2">
        <section className="card">
          <div className="card__head">
            <h2 className="title">Tonight</h2>
            <span className="eyebrow">30 minutes</span>
          </div>
          <div className="timeline" aria-hidden="true">
            <div className="timeline__span" style={{ left: '33.33%', width: '33.33%' }} />
          </div>
          <div className="timeline__ticks" aria-hidden="true">
            {TICKS.map((tick) => (
              <span key={tick}>{tick}</span>
            ))}
          </div>

          <form className="stack" style={{ marginTop: 'var(--s-5)' }} onSubmit={(event) => event.preventDefault()}>
            <div className="field-row">
              <div className="field">
                <label htmlFor="opens">Opens at</label>
                <input id="opens" type="time" defaultValue={SAMPLE_WINDOW.opens} disabled />
              </div>
              <div className="field">
                <label htmlFor="closes">Closes at</label>
                <input id="closes" type="time" defaultValue={SAMPLE_WINDOW.closes} disabled />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--s-3)', flexWrap: 'wrap' }}>
              <button className="btn btn--primary" type="submit" disabled>
                Save window
              </button>
              <button className="btn btn--danger" type="button" disabled>
                Make tonight an off day
              </button>
            </div>
            <p className="muted">These controls start working once sign-in is connected in Phase 10.</p>
          </form>
        </section>

        <section className="card">
          <div className="card__head">
            <h2 className="title">Past nights</h2>
          </div>
          <div className="ledger">
            {SAMPLE_NIGHTS.map((night) => (
              <div key={night.night} className="ledger__row">
                <div className="ledger__main">
                  <span>{night.night}</span>
                  <small className="mono">{night.state === 'off' ? 'Off day' : `${night.opens} to ${night.closes}`}</small>
                </div>
                {night.state === 'off' ? (
                  <StatusPill status="unlit" label="No window" />
                ) : (
                  <span className="mono muted">
                    {night.present}/{night.total}
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  )
}
