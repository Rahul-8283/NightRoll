# Phase 13: Testing, Tuning and Demo Rehearsal

| | |
|---|---|
| **Type** | Testing |
| **Depends on** | Phases 0 to 12 |
| **Unlocks** | The demo |
| **Leads** | Whole team |

## Goal

Find out whether the system does what it claims, fix what does not, replace the provisional numbers with measured ones, and rehearse the demo until it runs the same way every time. Every item marked "Deferred to Phase 13" in the earlier phases is collected here.

## Outcome

- Automated tests for the logic that decides a verdict.
- Measured face, liveness and Wi-Fi limits, replacing the starting values.
- Each security claim in the threat model checked with a real attempt.
- A demo rehearsed at least three times, with a recorded backup.
- A short, honest report of what was measured and what is still unproven.

## A note on this plan

All testing sits in this one phase, by the team's choice. The cost is that a defect in an early phase is found late, when more is built on top of it. Two things reduce that cost: each earlier phase has exit criteria that are checked by hand as it finishes, and this phase is ordered so the most damaging defects are found first.

---

## Order of work

| Order | Block | Why first |
|---|---|---|
| 1 | End-to-end smoke run | Shows at once whether the pieces fit together |
| 2 | Verdict logic tests | Errors here make every result wrong |
| 3 | Security checks | These are the product's central claims |
| 4 | Measurement and tuning | Needs a working, correct system |
| 5 | Everything else | Lower risk |
| 6 | Demo rehearsal | Needs the final numbers |

Stop adding tests when time runs short, and move to block 6. A rehearsed demo matters more than full coverage.

---

## 1. End-to-end smoke run

On the packaged system from Phase 12, on the demo hardware.

| # | Step | Expected |
|---|---|---|
| 1.1 | Start everything from a clean state with the runbook | All services healthy |
| 1.2 | Warden logs in with password and code | Reaches Tonight page |
| 1.3 | Enroll a new student from scratch | Enrolled, with room fingerprint |
| 1.4 | Admin opens the window | Window shows as open once the student opens the app |
| 1.5 | Student marks from their room | `PRESENT`, tile turns within 2 s |
| 1.6 | Admin closes the window | Absentees listed |
| 1.7 | Export tonight's CSV | File has the right rows |

Any failure here is fixed before anything else in this phase.

## 2. Automated tests

### 2.1 Setup

| # | Task |
|---|---|
| 2.1.1 | Add `pytest` to `backend/` and `face/`, and a test runner to `dashboard/` and `app/` |
| 2.1.2 | Integration tests use a local Supabase stack from the Supabase CLI and a throwaway Redis, never the shared development project |
| 2.1.3 | Record a set of real submissions from the test phones as fixtures: genuine, wrong room, wrong device, tampered. Strip the frames and keep the hashes. |
| 2.1.4 | Add a GitHub Actions workflow that runs lint and the unit tests on every push |

### 2.2 Unit tests, in priority order

| Area | Cases |
|---|---|
| Signature check | Valid; one byte changed; wrong key; frame swapped after signing |
| Nonce consume | First use ok; second use refused; wrong value; expired; 50 simultaneous consumes give exactly one ok |
| Window gate | One second before open; at open; at close; one second after; phone clock wrong |
| Integrity gate | Wrong package; wrong request hash; stale timestamp; missing device verdict; service unreachable gives 503 |
| Network gate | Inside subnet; outside; forwarded-for from an untrusted source ignored; BSSID not in room |
| Each scorer | Low end, high end and midpoint of its range; missing input |
| Fingerprint scorer | Same room; next room; outside; own access point missing; stale scan; no fingerprint |
| Fusion and verdict | Each cutoff boundary; face floor; liveness floor; weights not summing to 1 refused at startup |
| Effective status | Every combination of marks and reviews from Phase 11's table |
| Settings | Each unsafe setting refused outside local |
| Log redaction | Each sensitive field absent from output |
| Export | Formula-injection guard; 31-day limit; no score columns |
| Enrollment codes | Expiry; single use; lockout after five wrong tries |

### 2.3 Integration tests

| Flow | Checks |
|---|---|
| Enroll, open, mark, close | The whole path against real Redis and a local database, with the face worker replaced by a stand-in returning fixed scores |
| Retry | Rejected, then fresh nonce, then present; fourth attempt refused |
| Idempotency | The same envelope twice gives one row and identical responses |
| Review | Approve, decline, override, manual, each with its audit row |
| Scheduler | Opens and closes on time; restart mid-window does not reissue nonces; catch-up after downtime |
| Permissions | Each warden-only and admin-only route with no token, a warden token and an admin token |
| Row-level security | The anon key reads nothing from any table or bucket |

### 2.4 App and dashboard

| Area | Cases |
|---|---|
| Envelope builder | Fixed input gives fixed payload string and hash |
| Signing string | Fixed input matches a known signature check |
| Reason messages | Every reason code has a plain sentence |
| Dashboard live state | Snapshot, update, reconnect, fall back to polling |
| Tile states | Each state renders with a label, not colour alone |

## 3. Security checks

Each row is attempted for real on the test phones, and the result written down. These map to the threat model in the README.

| # | Attempt | Expected |
|---|---|---|
| 3.1 | Mark from a teammate's phone for another student | `SIGNATURE_INVALID` or `DEVICE_NOT_ENROLLED` |
| 3.2 | Hand an enrolled phone to a different person | `FACE_MISMATCH` |
| 3.3 | Printed photo of the student | Not `PRESENT` |
| 3.4 | Video of the student on a second phone, including a video of them blinking and turning | Not `PRESENT` |
| 3.5 | Capture a real submission and send it again | Stored response returned, no new mark |
| 3.6 | Send a captured submission the next night | `NONCE_INVALID` or `OUTSIDE_WINDOW` |
| 3.7 | Turn on a VPN | Blocked in the app; if forced through, rejected at the server |
| 3.8 | Connect to the other room's router | `NETWORK_MISMATCH` |
| 3.9 | Use mobile data | Blocked in the app; rejected at the server |
| 3.10 | Send a false forwarded-for header | Ignored; gate uses the real address |
| 3.11 | Set the phone clock back after the window closes | `OUTSIDE_WINDOW` |
| 3.12 | Run the app on an emulator | Integrity gate fails |
| 3.13 | Run on a rooted phone, if one is available | Integrity gate fails |
| 3.14 | Edit the payload to claim `vpn: false` while on a VPN | Signature still valid, so this passes the environment gate; the network gate must catch it. Record whether it does. |
| 3.15 | Call warden routes with no token, an expired token, a token that skipped the code step | `401` or `403` |
| 3.16 | Read tables and frames with the public Supabase key | Nothing returned |
| 3.17 | Search the built app and dashboard bundles for the service role key | Not present |
| 3.18 | Search git history for secrets | None |

Row 3.14 is the honest test of the design: a modified app can lie about its own environment, and only the server-side checks stand behind it. Whatever happens, write it in the report.

## 4. Measurement and tuning

This is where the provisional numbers become real ones. Record raw data in `docs/measurements/`.

### 4.1 Face match

| # | Task |
|---|---|
| 4.1.1 | Enroll every teammate, and any volunteers who agree |
| 4.1.2 | Collect at least 10 genuine attempts per person in bed-like conditions: lying down, dim light, with and without glasses |
| 4.1.3 | Collect impostor attempts: each person against every other person's enrollment |
| 4.1.4 | Plot the two sets of similarity scores |
| 4.1.5 | Set `FACE_SIM_LOW` just above the highest impostor score, and `FACE_SIM_HIGH` at a level most genuine attempts clear |

### 4.2 Liveness

| # | Task |
|---|---|
| 4.2.1 | Collect anti-spoof scores for live captures, printed photos, and screen replays on at least two different screens |
| 4.2.2 | Set `ANTISPOOF_MIN` between the live and fake groups |
| 4.2.3 | Note how often a genuine student fails the challenge in dim light, and adjust time limits if needed |

### 4.3 Walk test for Wi-Fi

Done in the real hostel if at all possible, otherwise at the demo venue.

| # | Position | Scans |
|---|---|---|
| 4.3.1 | Inside the room: bed, desk, door | 3 each |
| 4.3.2 | Corridor outside the door | 3 |
| 4.3.3 | The room next door | 3 |
| 4.3.4 | The floor above or below | 3 |
| 4.3.5 | Outside the building, as far as the Wi-Fi still connects | 3 |
| 4.3.6 | Outside the compound wall, if the signal reaches | 3 |

| # | Task |
|---|---|
| 4.3.7 | Run each scan through the fingerprint and own-access-point scorers and record the scores |
| 4.3.8 | Set `OWN_AP_RSSI_LOW` and `OWN_AP_RSSI_HIGH` so inside positions score high and outside positions low |
| 4.3.9 | Set the fingerprint settings the same way |
| 4.3.10 | Note which positions cannot be told apart. The corridor and the room next door probably cannot be, and that is acceptable: the student is still in the hostel. |
| 4.3.11 | Repeat for a room at the edge of the building, where the outside is closest |

### 4.4 Weights and cutoffs

| # | Task |
|---|---|
| 4.4.1 | Replay all recorded genuine and attack attempts through fusion with the tuned scorer settings |
| 4.4.2 | Adjust `THRESHOLD_PRESENT` and `THRESHOLD_REVIEW` so no attack is `PRESENT`, and as few genuine attempts as possible fall to review |
| 4.4.3 | Change the weights only if the data clearly supports it |
| 4.4.4 | Record the final values and the false-accept and false-reject counts they give on the recorded set |

Update `backend/.env.example`, the README and the TRD with the final values, and remove the word "provisional" only where a value was actually measured.

## 5. Load and timing

| # | Test | Target |
|---|---|---|
| 5.1 | Replay recorded submissions at 5 per second for 2 minutes | 95th percentile under 2 s, no errors |
| 5.2 | Burst of 20 per second for 30 seconds | No crash; requests queue and complete |
| 5.3 | Face worker alone, one frame | Record the time on the demo laptop |
| 5.4 | Open a window for 1,000 seeded students | Nonces issued within 60 s |
| 5.5 | 20 dashboards connected during the replay | All stay in step |
| 5.6 | Marking flow on the slowest test phone | Under 30 s, tap to result |

The replay needs submissions that pass the gates. Use a test-only mode, available only with `APP_ENV=local`, that accepts pre-signed fixtures for seeded test students.

## 6. Failure drills

| # | Break this | Expected |
|---|---|---|
| 6.1 | Stop the face worker mid-window | Verify returns 503, app shows fallback, dashboard alert appears |
| 6.2 | Stop Redis | Verify returns 503, nothing is accepted |
| 6.3 | Cut the laptop's internet | Database and integrity calls fail safely; nothing is marked present by default |
| 6.4 | Unplug a room's router | Students in that room get the fallback; room flagged |
| 6.5 | Restart the API mid-window | Dashboards reconnect; no marks lost |
| 6.6 | Restart the scheduler mid-window | No second set of nonces; window still closes on time |

## 7. Privacy checks

| # | Check |
|---|---|
| 7.1 | No enrollment photo exists anywhere in storage |
| 7.2 | Frames older than 24 hours are gone, and their `frames_path` is cleared |
| 7.3 | Logs from a full night contain no embedding, frame, token, signature or raw student ID |
| 7.4 | The export contains no scores, network detail or biometric data |
| 7.5 | Withdrawing consent removes the embedding and deactivates the device |
| 7.6 | Every frame view has an audit row with a reason |

## 8. Demo rehearsal

### 8.1 Script

Target length: 4 minutes for the live part.

| # | Action | On screen | Line to say |
|---|---|---|---|
| 0 | Admin opens the window | Both phones show it open once the app is opened | "It's 10 PM. Students open NightRoll and the window is waiting for them." |
| 1 | Teammate A marks from Room 101 | Tile turns green | "Marked from bed. That took about fifteen seconds." |
| 2 | Teammate A joins the Room 102 router and tries | Rejected: wrong room network | "Same person, same phone, wrong room." |
| 3 | Hold a photo, then a video, to phone A | Rejected: liveness | "A photo or a video of a face is not a person." |
| 4 | Teammate B tries on phone A | Rejected: face does not match | "A friend can't mark for you on your phone." |
| 5 | Teammate B marks as teammate A from phone B | Rejected: device not recognised | "And not on their own phone either." |
| 6 | Walk out of range while on the Wi-Fi | Rejected or sent to review: Wi-Fi pattern | "Still connected, but the room looks wrong from out here." |
| 7 | Warden approves a review item | Tile turns green | "And a person always has the final say." |

### 8.2 Rehearsal tasks

| # | Task |
|---|---|
| 8.2.1 | Run the full script at least three times, timed, using "Reset demo" between runs |
| 8.2.2 | Assign one person to each phone, one to the dashboard, one to speak |
| 8.2.3 | Rehearse once at the venue, or on the venue's network, before the real thing |
| 8.2.4 | Record a clean run as a backup video, with the dashboard and a phone both visible |
| 8.2.5 | Prepare a one-line recovery for each step if it fails live, and practise switching to the video |
| 8.2.6 | Charge all phones, turn off battery saver, turn on Do Not Disturb except for NightRoll |
| 8.2.7 | Prepare answers to the likely questions: privacy of face data, iPhones, a student who leaves after marking, what the hostel network must provide, what was measured and what was not |

## 9. Defect handling

| Severity | Meaning | Action |
|---|---|---|
| Blocker | A demo step fails, or an attack gets `PRESENT` | Fix now, re-run the affected block |
| Major | A genuine student is wrongly rejected often; data shown is wrong | Fix before rehearsal |
| Minor | Cosmetic, or a rare edge case | Write it down; fix if time allows |

Each fix gets a test that would have caught it. Keep the list in `docs/defects.md`.

## 10. Final report

Write `docs/test-report.md`, one page.

| Section | Content |
|---|---|
| What was tested | Counts of automated tests, and the security checks attempted |
| Measured accuracy | Face, liveness and Wi-Fi results on the recorded set, with the sample sizes stated plainly |
| Final settings | The tuned values |
| What held | Attacks that were blocked |
| What did not | Anything that got through or could not be tested, such as row 3.14 or a rooted phone |
| Not yet proven | Real hostel conditions, large numbers of students, the campus controller integration |

State sample sizes honestly. Results from four teammates in one room are a demonstration, not proof of accuracy across a hostel.

---

## Exit criteria

- [ ] The smoke run passes from a clean start.
- [ ] Unit tests for every gate, scorer, fusion and the effective-status logic pass, and run on every push.
- [ ] Every row of the security checks has a recorded result.
- [ ] No attack in the recorded set gets `PRESENT` with the final settings.
- [ ] The walk test is done and the Wi-Fi settings come from its data.
- [ ] Face and liveness settings come from recorded attempts.
- [ ] The 5-per-second replay meets the 2-second target.
- [ ] Every failure drill ends in a safe state.
- [ ] All privacy checks pass.
- [ ] The demo has run cleanly three times in a row.
- [ ] The backup video is recorded.
- [ ] No blocker or major defect is open.
- [ ] `docs/test-report.md` is written, and the README no longer calls a measured value provisional.

## Risks

| Risk | What to do |
|---|---|
| Testing finds a design-level problem late | Fix what can be fixed, and state the rest plainly in the report and the pitch |
| No access to the real hostel for the walk test | Do it at the venue, and say that hostel limits are still to be measured |
| Too few faces for a meaningful accuracy number | Report the sample size; do not quote a percentage that suggests more |
| Tuning to the demo room overfits | Keep demo settings and pilot settings as separate env files |
| Time runs out | Follow the order of work. Rehearsal is never the block that gets cut. |
