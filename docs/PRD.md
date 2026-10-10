# NightRoll: Product Requirements Document

**Team:** Zero_Latency
**Event:** Genesis Hackathon
**Status:** Design stage
**Version:** 0.1

---

## 1. Summary

NightRoll lets hostel students mark their nightly attendance from bed on their phone. Today, students on every floor walk down to one ground-floor face scanner at 10:00 PM. NightRoll replaces that walk with a short face check the student opens in bed, and it verifies that the mark comes from the student's own room, on their enrolled device, inside the warden's window.

No new hardware is needed. The system uses the student's phone, the hostel's existing per-room WiFi, and a backend on the campus network.

---

## 2. Problem

- Every hosteller goes to the ground floor each night to mark attendance.
- Students on upper floors lose time climbing up and down, and a queue forms at one scanner.
- The current check proves a student was at the ground floor at one moment. It does not prove they are in their room.
- Wardens have no live view of which rooms are marked during the window.

**Affected groups:** students (daily), wardens (nightly review), hostel administration (records).

---

## 3. Goals and success measures

| # | Goal | Success measure |
|---|------|-----------------|
| G1 | Students can mark from bed | Marking completes without leaving the room |
| G2 | Marks are hard to fake | Each attack in section 10 is blocked by at least one control |
| G3 | Wardens see every room live | Dashboard reflects a verdict within 2 seconds |
| G4 | No new hardware | Works on student Android phones and existing hostel WiFi |
| G5 | A clear fallback exists | Students with a dead phone or no WiFi can use the ground-floor scanner |
| G6 | Marking is fast | Median time from opening the app to verdict under 30 seconds |

---

## 4. Non-goals (first release)

- iOS support. iOS does not allow full WiFi scans, so iPhone users keep the ground-floor scanner.
- Random spot-checks after the window closes.
- Cross-student anomaly detection, such as device-sharing patterns.
- ERP or university system integration.
- Automatic fingerprint updates. Fingerprints are set at enrollment and refreshed by a manual re-scan.
- Any location tracking outside the window, or during the day.

---

## 5. Users

| Role | Needs | Concerns |
|------|-------|----------|
| **Student** | Mark in bed, quickly, with a clear result | Battery, speed, face data privacy, false rejections |
| **Warden** | Live room status, a review queue, override power, window control | Accuracy, the ability to correct errors, workload at night |
| **Campus network admin** | Clear, read-only integration with WiFi controller or RADIUS | Security of the integration, no change to network behavior |
| **Hostel administration** | Attendance records and exports | Data retention, consent records |

---

## 6. User stories

**Enrollment**
- As a student, I enroll once at the warden's office, so my face, my phone, and my room are registered.
- As a student, I am asked for consent before any face data is captured.
- As a warden, I can re-scan a room's WiFi fingerprint after a router change.

**Nightly marking**
- As a student, I open the app during the window and see that it is open, with its closing time.
- As a student, I can complete the face check in bed.
- As a student, I see a result and, if rejected, the reason and the next step.
- As a student, I can use the ground-floor scanner if my phone or WiFi fails.

**Warden**
- As a warden, I see every room's status live during the window.
- As a warden, I see a review queue of borderline marks with reasons.
- As a warden, I can approve, decline, or override any mark.
- As a warden, I set the window time and off days.
- As a warden, I see the absentee list when the window closes.

**Administration**
- As an administrator, I export attendance by night, floor, or room.

---

## 7. Functional requirements

### 7.1 Window management
- **FR-1** The warden sets the window start and end. Default is 22:00 to 22:30.
- **FR-2** The warden can mark nights as off days, when no window opens.
- **FR-3** At window open, the system issues one single-use nonce per enrolled student, valid until the window closes.
- **FR-4** The Home screen shows tonight's window status to each enrolled student who opens the app. No push notification is sent.

### 7.2 Enrollment
- **FR-5** Enrollment requires recorded consent before any capture.
- **FR-6** The system captures 3 to 5 face frames and stores only the resulting embedding. Photos are not kept.
- **FR-7** The app generates a signing keypair in the device's secure hardware. The private key cannot be exported.
- **FR-8** The system registers the device's public key to the student.
- **FR-9** The app performs 3 to 5 WiFi scans in the room and stores the room fingerprint.
- **FR-10** The network administrator provides the mapping of room to access point and subnet.

### 7.3 Marking
- **FR-11** The app refuses to continue if a VPN, proxy, or mock location is active.
- **FR-12** The app runs a random liveness challenge, such as blinking twice or turning the head.
- **FR-13** The app captures face frames, performs one WiFi scan, obtains a Play Integrity token, and signs the payload with the device key.
- **FR-14** The app sends the signed payload over HTTPS to the verification endpoint.
- **FR-15** The backend runs the hard gates in section 8.1 before any scoring.
- **FR-16** The backend scores the remaining checks and computes a trust score (section 8.2).
- **FR-17** The backend returns one verdict: PRESENT, NEEDS REVIEW, or REJECTED, with a reason.
- **FR-18** The dashboard updates the room tile when a verdict is recorded.

### 7.4 Review and override
- **FR-19** NEEDS REVIEW marks appear in the warden's queue with the scores and reasons.
- **FR-20** The warden can approve, decline, or override any mark. Each action is logged with the warden's identity and time.

### 7.5 Fallback
- **FR-21** A student who cannot mark through the app is directed to the ground-floor scanner.
- **FR-22** A warden can record a manual mark with a reason.

### 7.6 Reporting
- **FR-23** The warden and administration can export attendance by night, floor, or room.
- **FR-24** The dashboard shows the floor-by-floor heatmap, the review queue, and the absentee list.

---

## 8. Verification design

### 8.1 Hard gates (any failure rejects the mark)

| Gate | Checks | Defeats |
|------|--------|---------|
| Window | Server clock is inside the window | Changing the phone's clock |
| Signature and nonce | Signature matches the enrolled key, nonce is unused | A friend's phone, replayed requests |
| Device integrity | Play Integrity passes | Rooted devices, emulators, virtual cameras |
| Environment | No VPN, proxy, or mock location | Marking from outside the network |
| Network | Source IP is in the student's room subnet | Requests from outside the hostel network |

### 8.2 Scored checks (after all gates pass)

| Check | Weight (provisional) | Measures |
|-------|----------------------|----------|
| Face match | 0.30 | Cosine similarity to the enrolled embedding |
| Room WiFi fingerprint | 0.30 | Match of tonight's scan to the room's saved pattern |
| Liveness and anti-spoof | 0.20 | Challenge completed, face is not a photo or screen |
| Own access point strength | 0.15 | The room's own router is seen at room-level strength |
| Access point agreement | 0.05 | The router's view of the phone agrees with the phone's report |

### 8.3 Verdict thresholds (provisional)

| Score | Verdict | Next step |
|-------|---------|-----------|
| 0.80 or higher | PRESENT | Recorded, room tile turns green |
| 0.60 to 0.80 | NEEDS REVIEW | Warden queue |
| Below 0.60 | REJECTED | Student sees the reason and can retry or use the fallback |

Weights and thresholds must be tuned from measurements taken in the hostel before they are relied on.

### 8.4 WiFi geofencing

- The room fingerprint is built from the visible access points and their signal strengths, from 3 to 5 scans at enrollment.
- The check compares tonight's scan against the fingerprint. It looks at whether the room's own router is present, whether expected neighbours are visible, whether relative strengths match, and whether unknown outside networks appear.
- Limits are set by a walk test. The team measures inside several rooms and outside the compound wall, the corridor, the next room, and the floor below, then sets limits between the two groups. Edge rooms get stricter limits.
- The 5 GHz band is used as supporting evidence only if the walk test shows it helps.
- GPS is a warning signal only, and only when it is accurate and clearly outside the hostel.

---

## 9. Non-functional requirements

| Category | Requirement |
|----------|-------------|
| Performance | Verdict returned within 2 seconds of submission, at the 95th percentile |
| Availability | Available for the whole window; the fallback covers outages |
| Scalability | Supports the full hostel population (target: up to 1,000 students) marking within the same 30-minute window |
| Security | HTTPS only; keys stay in secure hardware; secrets kept out of source control |
| Privacy | Embeddings only; frames deleted within 24 hours; no biometric data in logs |
| Auditability | Every verdict and warden action is logged with time, inputs, and reason |
| Usability | A student completes marking without reading instructions after the first enrollment |
| Accessibility | Liveness challenge has a fallback for users who cannot blink or turn their head; the warden can override |
| Battery | Marking uses one camera session and one WiFi scan |
| Data retention | Set by hostel policy; default 1 academic year for attendance records |

---

## 10. Threat model

| Attack | Control |
|--------|---------|
| A friend marks on their own phone for you | Device-bound signature fails |
| A friend marks on your phone | Face match fails |
| A photo or video of your face | Liveness and anti-spoof reject |
| Replaying last night's request | Nonce is single-use and expires |
| Marking over a VPN | VPN check and room subnet gate |
| Marking from outside the hostel | Room subnet gate and WiFi fingerprint |
| A rooted phone, emulator, or fake camera | Play Integrity |
| Changing the phone's clock | Server clock decides the window |

**Known limitations:** a student can mark present and then leave. This is accepted for the first release. Random spot-checks are planned for later.

---

## 11. Dependencies

- Hostel administration approval for the pilot.
- Campus network admin cooperation to provide room-to-subnet mapping, and ideally controller or RADIUS access.
- Google Cloud project for Play Integrity API access.
- A Supabase project for database, authentication, and frame storage, with pilot data kept under the college data policy.
- Students' Android phones with location and camera permissions.

---

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hostel network does not expose subnets or controller access | Network gate cannot run in production | Demo with real routers; fall back to fingerprint plus warden review; pitch the integration as a next step |
| Fingerprint misses students on normal nights | Many marks go to review | Walk test sets limits; warden re-scan; drift handling |
| Face matching fails for some students | False rejections | Re-capture allowed; warden override; ground-floor fallback |
| Students object to face data collection | Low adoption or pilot blocked | Explicit consent, embeddings only, short retention, clear privacy notice |
| iOS students excluded | Unfair experience in a mixed hostel | Documented fallback; iOS on the roadmap |
| Demo fails on stage | Credibility loss | Pre-recorded backup video; scripted demo with two routers |
| Thresholds are wrong | Wrong verdicts | Provisional label; tune with walk test and pilot data |

---

## 13. Open questions

1. Does the hostel provide per-room or per-floor subnets, controller API access, or RADIUS accounting?
2. What window time does the warden want: 22:00–22:30 or 9:55–10:15?
3. Who owns the attendance record after NightRoll, and for how long must it be kept?
4. What consent wording and privacy notice does the hostel administration approve?
5. Will the warden accept NEEDS REVIEW volume during the first week?
6. Is the ground-floor scanner kept as the permanent fallback, or retired after the pilot?
7. How do students remember to open the app at window time, without a push? Options: a warden announcement, a local alarm set from the window time, or a fixed daily routine.

---

## 14. Milestones

| Phase | Scope | Exit criterion |
|-------|-------|----------------|
| M1: Hackathon demo | Signed nonce, room subnet gate with two routers, face match with liveness, room-tile dashboard | Full demo runs end to end on stage |
| M2: Pilot preparation | WiFi fingerprint and walk test, controller or RADIUS adapter, consent flow, warden review queue | Walk test limits agreed; network admin signs off |
| M3: Pilot | One floor or one block, full window for two weeks | Verdict accuracy and review volume measured against manual records |
| M4: Rollout | All blocks, reporting and export | Warden and administration sign off |

---

## 15. Out of scope for this document

Implementation details, code structure, and hosting choices are covered in the README and the architecture diagrams.