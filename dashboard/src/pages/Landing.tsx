import { Link } from 'react-router'
import { useLenis } from '../landing/useLenis'
import { useReveal } from '../landing/useReveal'
import { RoomWindow } from '../components/ui/RoomWindow'
import { Wordmark } from '../components/ui/Wordmark'
import type { Status } from '../components/ui/status'

const NAV = [
  { href: '#problem', label: 'Why' },
  { href: '#proof', label: 'Three checks' },
  { href: '#night', label: 'A night' },
  { href: '#rules', label: 'Decisions' },
  { href: '#privacy', label: 'Privacy' },
  { href: '#stack', label: 'Build' },
  { href: '#roadmap', label: 'Roadmap' },
]

const PROOFS = [
  {
    no: 'I',
    title: 'The right person',
    lead: 'A face match and a liveness challenge.',
    body:
      'The app asks the student to blink or turn their head, then checks a short burst of frames against the embedding stored at enrolment. A photo held up to the camera fails the challenge. A video replay fails it too. We store the face as a 512-number ArcFace embedding, never as a photo.',
  },
  {
    no: 'II',
    title: 'The right place',
    lead: 'The request must come from their own room’s network.',
    body:
      'Each room has its own access point and subnet. The phone’s request leaves through that access point, so the server sees the room’s address. A hotspot, a VPN or a proxy changes the address and the request is rejected. The Wi-Fi fingerprint of the room is a supporting signal, not the gate.',
  },
  {
    no: 'III',
    title: 'The right device, right now',
    lead: 'A key that cannot leave the phone signs a one-time nonce.',
    body:
      'The phone’s signing key lives in the Android Keystore, in secure hardware where the phone has it. It never reaches JavaScript and cannot be copied off the device. The server issues one nonce per student per night, valid until the window closes, and it can be used exactly once.',
  },
]

const STEPS: { at: string; title: string; body: string; tone: Status }[] = [
  {
    at: '21:00',
    title: 'The warden sets the window',
    body: 'Tonight’s window opens at 22:00 and closes at 22:30, unless the warden moves it or marks the night as an off day.',
    tone: 'unlit',
  },
  {
    at: '22:00',
    title: 'The window opens',
    body: 'The server issues one nonce to every enrolled student. Nothing is pushed to phones. Students open the app themselves.',
    tone: 'review',
  },
  {
    at: 'in bed',
    title: 'The student opens NightRoll',
    body: 'Before the camera opens, the app checks for a VPN, a proxy and mock location. If any is on, it says why and stops.',
    tone: 'unlit',
  },
  {
    at: 'seconds',
    title: 'The phone gathers the proof',
    body: 'A liveness challenge, a few face frames, one Wi-Fi scan, a Play Integrity token. Then the Keystore key signs the whole payload.',
    tone: 'unlit',
  },
  {
    at: 'instant',
    title: 'The server decides',
    body: 'Five hard gates run first: window time, signature and nonce, integrity, no VPN, room subnet. Then five scores are fused into one trust value.',
    tone: 'review',
  },
  {
    at: 'verdict',
    title: 'Present, review, or rejected',
    body: 'Above 0.80 the room tile turns lit. Between 0.60 and 0.80 the warden gets it in a queue. Below 0.60, or any failed gate, the student sees the reason and is pointed to the ground-floor scanner.',
    tone: 'present',
  },
  {
    at: '22:30',
    title: 'The window closes',
    body: 'Anyone with no mark is recorded as absent. Students with a mark still in review are left for the warden. The warden exports the night as CSV.',
    tone: 'rejected',
  },
]

const GATES = [
  ['Server clock', 'The mark arrives inside the window, by the server’s clock.'],
  ['Signature and nonce', 'The Keystore signature checks out, and the nonce is fresh and unused.'],
  ['Play Integrity', 'Google’s device check passes for the NightRoll app on a genuine phone.'],
  ['No VPN, proxy or mock location', 'The phone is not routing through a tunnel or faking its place.'],
  ['Room subnet', 'The request came from the student’s own room network.'],
]

const SCORES = [
  ['Face match', 0.3, 'How closely the face matches the enrolled embedding.'],
  ['Liveness and anti-spoof', 0.2, 'The challenge passed and the frames look like a live person.'],
  ['Room Wi-Fi fingerprint', 0.3, 'The visible access points look like this room’s pattern.'],
  ['Own access point signal', 0.15, 'The room’s own router is present and strong.'],
  ['Access point agreement', 0.05, 'The access point’s view agrees with the phone’s.'],
]

const STACK = [
  ['Phone', 'Expo app, React Native and TypeScript. Kotlin Expo Modules for the Keystore key, Wi-Fi scan and camera.'],
  ['API', 'FastAPI on Python 3.12. Verification orchestrator, gates, scoring and the warden endpoints.'],
  ['Face worker', 'Python service. InsightFace ArcFace embeddings and anti-spoof, kept apart from the API.'],
  ['Data', 'Supabase PostgreSQL with pgvector for embeddings, row-level security on every table, Auth with TOTP for wardens, and a private Storage bucket for frames.'],
  ['Live state', 'Upstash Redis over TLS for nonces and window state. Every nonce operation is one atomic Lua script.'],
  ['Dashboard', 'React and Vite. The floor view, review queue, absentees and CSV export, with live updates over WebSocket.'],
]

const PHASES = [
  ['0', 'Base setup', 'Repository, accounts, the spikes that test the risky ideas first.'],
  ['1', 'Data layer', 'Every table, index and policy, created by migrations.'],
  ['2', 'Backend core', 'Settings, connections, warden sign-in, the error shape, logs and audit.'],
  ['3', 'Windows and nonces', 'Open and close windows on the server clock. One-time nonces.'],
  ['4', 'App foundation and key', 'The Expo app, the Keystore key, and Home showing tonight.'],
  ['5', 'Face worker', 'Embeddings and anti-spoof, behind their own service.'],
  ['6', 'Enrolment', 'Consent, a one-time code, the face, the device key, the room scan.'],
  ['7', 'Nightly capture', 'The liveness challenge, frames, the Wi-Fi scan, and the signed payload.'],
  ['8', 'Verification and gates', 'The five hard gates, in order, each failure logged on its own.'],
  ['9', 'Scoring and verdict', 'Five scores, one fused value, and the three verdicts.'],
  ['10', 'Warden dashboard', 'The floor view and live updates, wired to the real API.'],
  ['11', 'Review and audit', 'Approve, decline or override. Absentees, export and the audit view.'],
  ['12', 'Hardening and demo', 'Production builds, deployment, and a demo environment with two routers.'],
  ['13', 'Testing and rehearsal', 'Tests for each factor, tuning on our own data, and a rehearsed demo.'],
]

export function Landing() {
  useLenis()
  useReveal()

  // A fixed grid of rooms for the hero building. Each bed is one pane.
  const hero: Status[][] = [
    ['present', 'present', 'present', 'review', 'present', 'present'],
    ['present', 'present', 'rejected', 'present', 'present', 'unlit'],
    ['present', 'present', 'present', 'present', 'review', 'present'],
  ]

  return (
    <div className="landing">
      <header className="landing__nav">
        <Wordmark />
        <nav aria-label="On this page">
          {NAV.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
        <div className="landing__nav-actions">
          <Link to="/login" className="btn btn--primary landing__signup">
            Sign in
          </Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero__copy reveal">
          <span className="eyebrow">Hostel attendance, from bed</span>
          <h1 className="display hero__title">
            Mark attendance from your <em>bed</em>, not the ground floor.
          </h1>
          <p className="lede hero__lede">
            Every night at 10 PM, students on the upper floors walk down to be counted. NightRoll lets them
            mark from their phone instead, and still proves three things at once: it is them, they are in
            their own room, and it is their own device.
          </p>
          <div className="hero__actions">
            <Link to="/login" className="btn btn--primary">
              Warden sign-in
            </Link>
            <a href="#night" className="btn btn--quiet">
              Walk through a night
            </a>
          </div>
          <p className="muted hero__note">
            Built for the Genesis hackathon. Android first. Sample data throughout. Warden accounts are
            created by an admin; there is no self sign-up.
          </p>
        </div>

        <div className="hero__building reveal" aria-label="Sample hostel floors, one window per room">
          {[3, 2, 1].map((floor, row) => (
            <div key={floor} className="hero__floor">
              <span className="eyebrow">F{floor}</span>
              <div className="hero__rooms">
                {hero[row].map((status, col) => (
                  <RoomWindow
                    key={col}
                    number={`${floor}0${col + 1}`}
                    panes={[status, status, status, status]}
                    index={row * 6 + col}
                  />
                ))}
              </div>
            </div>
          ))}
          <p className="hero__caption muted">Each window is a room. Each pane is a bed. Lit means present.</p>
        </div>
      </section>

      <section id="problem" className="section reveal">
        <div className="section__head">
          <span className="eyebrow">01 · The problem</span>
          <h2 className="title-xl">Counting people should not cost them their sleep.</h2>
        </div>
        <div className="prose">
          <p>
            Hostellers on the first, second and third floors walk down to the ground floor every night at 10 PM to
            be marked. They queue at a scanner, wait for the person in front to finish, then climb back up. On a
            wet night, or with a dead phone, it is the same walk.
          </p>
          <p>
            The obvious fix is to let the phone mark it. The hard part is trust. A phone can be shared, a
            location can be faked, and a face can be a photograph. Any system that counts a student present has to
            answer three questions, and a single yes or no cannot answer all of them.
          </p>
          <p>
            NightRoll does not turn three weak checks into one strong one. It runs each check on its own, combines
            the results into a decision, and shows the warden why every decision was made.
          </p>
        </div>
      </section>

      <section id="proof" className="section">
        <div className="section__head reveal">
          <span className="eyebrow">02 · Three things at once</span>
          <h2 className="title-xl">No single factor is enough. All three are required.</h2>
        </div>
        <div className="proofs">
          {PROOFS.map((proof) => (
            <article key={proof.no} className="proof reveal">
              <span className="proof__no mono">{proof.no}</span>
              <h3 className="title">{proof.title}</h3>
              <p className="proof__lead">{proof.lead}</p>
              <p className="muted">{proof.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="night" className="section night">
        <div className="section__head reveal">
          <span className="eyebrow">03 · One night, end to end</span>
          <h2 className="title-xl">From the warden’s desk to the absentee list.</h2>
          <p className="lede">Seven steps, in order. Each one is a separate piece of the system, and each one can fail on its own.</p>
        </div>
        <ol className="timeline-steps">
          {STEPS.map((step, index) => (
            <li key={step.title} className="step reveal">
              <div className="step__rail" aria-hidden="true">
                <span className={`step__dot swatch--${step.tone}`} />
                {index < STEPS.length - 1 && <span className="step__line" />}
              </div>
              <div className="step__body">
                <span className="eyebrow">
                  {String(index + 1).padStart(2, '0')} · {step.at}
                </span>
                <h3 className="title">{step.title}</h3>
                <p className="muted">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section id="rules" className="section">
        <div className="section__head reveal">
          <span className="eyebrow">04 · The decision</span>
          <h2 className="title-xl">Gates first, then a score. A failed gate cannot be outvoted.</h2>
        </div>
        <div className="rules">
          <div className="card reveal">
            <h3 className="title">Five hard gates</h3>
            <p className="muted">Any one failing rejects the mark. No score is calculated.</p>
            <ol className="gates">
              {GATES.map(([name, detail], i) => (
                <li key={name}>
                  <span className="mono muted">G{i + 1}</span>
                  <div>
                    <strong>{name}</strong>
                    <span className="muted">{detail}</span>
                  </div>
                </li>
              ))}
            </ol>
          </div>
          <div className="card reveal">
            <h3 className="title">Five scores, fused</h3>
            <p className="muted">Weights and thresholds are provisional until the walk test sets them from real measurements.</p>
            <div className="weights">
              {SCORES.map(([name, weight, detail]) => (
                <div key={name} className="weight">
                  <div className="weight__head">
                    <span>{name}</span>
                    <span className="mono">{(weight as number).toFixed(2)}</span>
                  </div>
                  <div className="weight__bar">
                    <span style={{ width: `${(weight as number) * 100 * 2.6}%` }} />
                  </div>
                  <small className="muted">{detail}</small>
                </div>
              ))}
            </div>
            <div className="verdicts">
              <div className="verdict verdict--present">
                <span className="mono">≥ 0.80</span> Present
              </div>
              <div className="verdict verdict--review">
                <span className="mono">0.60 – 0.80</span> In review
              </div>
              <div className="verdict verdict--rejected">
                <span className="mono">&lt; 0.60</span> Rejected
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="privacy" className="section">
        <div className="section__head reveal">
          <span className="eyebrow">05 · Privacy</span>
          <h2 className="title-xl">We keep the least that makes the check work.</h2>
        </div>
        <div className="privacy">
          {[
            ['Embeddings, not photos', 'Enrolment keeps a face embedding. The enrolment photo is discarded.'],
            ['Frames deleted in 24 hours', 'Captured frames sit in a private bucket and are deleted within a day.'],
            ['Explicit consent', 'Enrolment starts with a consent screen the student must agree to. It is stated on the pitch slide too.'],
            ['Nothing biometric in logs', 'Embeddings, frames and signatures are redacted from every log line and audit row.'],
            ['Warden override always', 'Every automatic decision can be reviewed and overridden. The ground-floor scanner remains the fallback.'],
            ['No push notifications', 'Students open the app themselves at window time. No push service is added.'],
          ].map(([title, body]) => (
            <div key={title} className="privacy__item reveal">
              <span className="pane pane--present privacy__pane" aria-hidden="true" />
              <div>
                <h3 className="title-s">{title}</h3>
                <p className="muted">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="stack" className="section">
        <div className="section__head reveal">
          <span className="eyebrow">06 · How it is built</span>
          <h2 className="title-xl">Six parts, each with one job.</h2>
        </div>
        <div className="stack-grid">
          {STACK.map(([name, body]) => (
            <div key={name} className="stack-item reveal">
              <span className="eyebrow">{name}</span>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="roadmap" className="section">
        <div className="section__head reveal">
          <span className="eyebrow">07 · Roadmap</span>
          <h2 className="title-xl">Fourteen phases, from base setup to the rehearsed demo.</h2>
          <p className="lede">Each phase has its own plan, exit criteria and a commit per piece of work. Nothing merges until its checks pass.</p>
        </div>
        <div className="phases">
          {PHASES.map(([no, name, body]) => (
            <div key={no} className="phase reveal">
              <span className="mono muted">{no.padStart(2, '0')}</span>
              <div>
                <h3 className="title-s">{name}</h3>
                <p className="muted">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section cta reveal">
        <span className="eyebrow">Ready when the wardens are</span>
        <h2 className="display">
          One visit to the desk. <em>Then one tap a night.</em>
        </h2>
        <div className="hero__actions">
          <Link to="/login" className="btn btn--primary">
            Warden sign-in
          </Link>
        </div>
        <p className="muted">Accounts are created by an admin. There is no self sign-up.</p>
      </section>

      <footer className="landing__foot">
        <Wordmark />
        <span className="muted">NightRoll · Genesis hackathon · Sample data only, not the real hostel.</span>
      </footer>
    </div>
  )
}
