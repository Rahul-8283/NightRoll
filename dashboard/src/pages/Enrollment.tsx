import { NotConnected } from '../components/ui/EmptyState'
import { SampleNote } from '../components/ui/SampleNote'
import { config } from '../config'

const STEPS = [
  'Create a code for the student and read it out. It works once and expires in 15 minutes.',
  'The student reads the privacy notice in the app and agrees.',
  'They type the code, then the app captures their face and creates the phone key.',
  'Back in their room, the app scans the Wi-Fi a few times to learn the room.',
]

export function Enrollment() {
  return (
    <>
      {config.sampleData && <SampleNote />}
      <header className="page__head">
        <div>
          <span className="eyebrow">Enrollment desk</span>
          <h1 className="display">
            One student, <em>one code</em>, one phone
          </h1>
          <p className="lede">Enrollment happens once, in person. The code is what stops anyone enrolling a phone from a roll number alone.</p>
        </div>
      </header>

      {!config.sampleData ? (
        <NotConnected what="Creating enrollment codes" />
      ) : (
        <div className="grid-2">
          <section className="card stack">
            <form className="stack" onSubmit={(event) => event.preventDefault()}>
              <div className="field">
                <label htmlFor="roll">Roll number</label>
                <input id="roll" placeholder="TEST001" disabled />
              </div>
              <button className="btn btn--primary" type="submit" disabled style={{ alignSelf: 'flex-start' }}>
                Create code
              </button>
            </form>
            <div>
              <span className="eyebrow">Example code</span>
              <p className="code">7K4 29Q</p>
              <p className="muted">Expires in 15:00. Codes are created for real once sign-in is connected in Phase 10.</p>
            </div>
          </section>

          <section className="card">
            <div className="card__head">
              <h2 className="title">At the desk</h2>
            </div>
            <ol className="ledger" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {STEPS.map((step, index) => (
                <li key={step} className="ledger__row" style={{ justifyContent: 'flex-start', alignItems: 'baseline' }}>
                  <span className="mono muted">{String(index + 1).padStart(2, '0')}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </>
  )
}
