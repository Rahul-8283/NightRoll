# Phase 9: Scoring, Room Fingerprint and Verdict

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 5, 6, 8 |
| **Unlocks** | Phases 10, 11 |
| **Leads** | Backend, Face |

## Goal

A submission that passed every gate is scored on five signals, combined into one trust score, and turned into a verdict: present, needs review, or rejected. After this phase the full marking loop works from phone to verdict.

## Outcome

- Five scorers each return a number from 0 to 1 and a reason.
- The fusion step produces a trust score and a verdict from configured weights and cutoffs.
- A genuine student in their own room gets `PRESENT`.
- A photo of a face, or a phone outside the room, does not.
- Every verdict stores the individual scores, so the warden can see why.

## Scope

**In:** five scorers, fingerprint matching, fusion, verdict rules, storing results, publishing a verdict event.
**Out:** the dashboard that displays it (Phase 10), the review actions (Phase 11), tuning the numbers against real measurements (Phase 13).

---

## Tasks

### 1. Scorer interface

| # | Task |
|---|---|
| 1.1 | A scorer is a function taking the verified submission and returning `{score, reason, detail}` |
| 1.2 | Scorers have no side effects and read no clock, so the same input always gives the same score |
| 1.3 | Run the face worker call and the local scorers at the same time |
| 1.4 | Every threshold a scorer uses comes from settings. No number is written into scorer code. |

Add these settings to `backend/.env.example`, with the starting values shown. All are provisional until Phase 13.

```dotenv
FACE_SIM_LOW=0.45
FACE_SIM_HIGH=0.50
ANTISPOOF_MIN=0.90
OWN_AP_RSSI_LOW=-75
OWN_AP_RSSI_HIGH=-55
FP_NEIGHBOUR_LOW=0.3
FP_NEIGHBOUR_HIGH=0.7
FP_UNKNOWN_FREE=2
FP_UNKNOWN_STEP=0.1
FP_UNKNOWN_CAP=0.5
SCAN_STALE_MS=30000
```

### 2. Face match scorer

| # | Task |
|---|---|
| 2.1 | Call the face worker's `/verify` with the frames and their hashes |
| 2.2 | Use only the two frames tagged `neutral` for matching, since they face the camera |
| 2.3 | Map `best_similarity` to a score: at or below `FACE_SIM_LOW` gives 0, at or above `FACE_SIM_HIGH` gives 1, straight line between |
| 2.4 | Fewer than one usable neutral frame gives 0 with reason `FACE_MISMATCH` |
| 2.5 | Save the returned `frames_path` on the mark |

### 3. Liveness scorer

Three things must all hold for a score of 1. Otherwise the score is 0 with reason `LIVENESS_FAILED`.

| # | Check |
|---|---|
| 3.1 | Every challenge action has a detection time, and the times are in order and humanly plausible: no action completed in under 200 ms |
| 3.2 | The anti-spoof median from the face worker is at least `ANTISPOOF_MIN` |
| 3.3 | The frames tagged with an action show that action: the face worker reports a head turn in the right direction for `turn_left` and `turn_right` frames |

Check 3.3 is the server's own evidence that the challenge happened. Without it the server would be trusting the phone's word. Add head-turn angle per frame to the face worker's `/verify` response for this.

If the face worker reports that anti-spoof is unavailable, the liveness score is 0. It is never assumed to have passed.

### 4. Room fingerprint scorer

Inputs: tonight's scan from the payload and the room's latest stored fingerprint.

| # | Step |
|---|---|
| 4.1 | If the room has no fingerprint, return score 0.5 with reason `FINGERPRINT_MISSING`, so the mark goes to review rather than being rejected for something the student cannot fix |
| 4.2 | `own_present`: 1 if any of the room's own BSSIDs is in the scan, else 0. If 0, the fingerprint score is 0. |
| 4.3 | `neighbour_ratio`: of the stored BSSIDs labelled `hostel` that were seen in at least half the enrollment scans, the fraction visible tonight. Scale from `FP_NEIGHBOUR_LOW` (0) to `FP_NEIGHBOUR_HIGH` (1). |
| 4.4 | `rank_agreement`: over BSSIDs present both tonight and in the fingerprint, the Spearman rank correlation of signal strengths, with negative values treated as 0. With fewer than 3 shared BSSIDs, use 0.5. |
| 4.5 | `unknown_penalty`: count BSSIDs tonight that are neither in the fingerprint nor in the room map. Beyond `FP_UNKNOWN_FREE`, add `FP_UNKNOWN_STEP` each, up to `FP_UNKNOWN_CAP`. |
| 4.6 | Combine: `own_present × (0.4 × neighbour_ratio + 0.4 × rank_agreement + 0.2 × (1 − unknown_penalty))`, clamped to 0–1 |
| 4.7 | If `scan_age_ms` is above `SCAN_STALE_MS`, multiply the score by 0.5 and note it in the detail |
| 4.8 | A score below 0.5 carries reason `WIFI_PATTERN_MISMATCH` |

Put the detail in the result: which expected neighbours were missing and how many unknown networks appeared. The warden sees this in review.

### 5. Own access point scorer

| # | Task |
|---|---|
| 5.1 | Take the strongest signal among the room's own BSSIDs in tonight's scan |
| 5.2 | Map it to a score: `OWN_AP_RSSI_LOW` or weaker gives 0, `OWN_AP_RSSI_HIGH` or stronger gives 1, straight line between |
| 5.3 | If the room's own access point is not seen at all, the score is 0 |

### 6. Access point agreement scorer

| # | Task |
|---|---|
| 6.1 | Ask the `NetworkVerifier` for the signal strength the access point measured for this phone |
| 6.2 | If available, score 1 when it is within 10 dB of the phone's own reading, falling to 0 at 25 dB apart |
| 6.3 | In `subnet` mode there is no access point reading. Return 0.5 with reason `AP_UNAVAILABLE`. |

In the demo this scorer always returns 0.5, so its 0.05 weight contributes 0.025. That is expected and is stated in the response detail.

### 7. Fusion

```text
score = WEIGHT_FACE × face
      + WEIGHT_FINGERPRINT × fingerprint
      + WEIGHT_LIVENESS × liveness
      + WEIGHT_OWN_AP × own_ap
      + WEIGHT_AP_AGREEMENT × ap_agreement
```

| # | Task |
|---|---|
| 7.1 | Compute the weighted sum from settings |
| 7.2 | Round to three decimal places for storage |

### 8. Verdict rules

Score cutoffs alone are not enough: a weighted sum could let a strong Wi-Fi match carry a face that does not match. Two floors apply before the cutoffs.

| Order | Rule | Verdict |
|---|---|---|
| 1 | Face score is 0 | `REJECTED`, reason `FACE_MISMATCH` |
| 2 | Liveness score is 0 | `REJECTED`, reason `LIVENESS_FAILED` |
| 3 | Score at or above `THRESHOLD_PRESENT` | `PRESENT` |
| 4 | Score at or above `THRESHOLD_REVIEW` | `NEEDS_REVIEW` |
| 5 | Otherwise | `REJECTED`, reason `LOW_SCORE` plus the reason from the lowest scorer |

Add these floors to `docs/TRD.md` section 6.4 and to the trust score section of the README in this phase.

### 9. Storing and returning the result

| # | Task |
|---|---|
| 9.1 | Update the mark row created in Phase 8 with verdict, score, reasons and the per-scorer breakdown in `scores` |
| 9.2 | A `PRESENT` verdict relies on the unique index to block a second one. If the insert conflicts, return the existing mark. |
| 9.3 | Apply the retry rule from Phase 8: a `REJECTED` verdict issues a fresh nonce while attempts remain. `NEEDS_REVIEW` does not allow a retry; the warden decides. |
| 9.4 | Write the audit row |
| 9.5 | Store the response under the submission ID for idempotency |
| 9.6 | Publish a `mark_recorded` event on a Redis channel with the room ID, verdict and mark ID. Phase 10 listens to it. |

The response to the student carries the verdict, the overall score and plain reasons. It does not carry the per-scorer breakdown, which would tell someone exactly what to work around.

### 10. Timing

| Stage | Budget |
|---|---|
| Gates, including the Play Integrity call | 600 ms |
| Face worker | 900 ms |
| Local scorers and fusion | 50 ms |
| Database writes | 150 ms |
| **Total, 95th percentile** | **under 2 s** |

Log each stage's duration on every request.

---

## Exit criteria

- [ ] An enrolled teammate marking from their own room's router gets `PRESENT`. *(Demo step 1)*
- [ ] Holding up a printed photo or a second phone showing the teammate's face does not get `PRESENT`. *(Demo step 3)*
- [ ] A different teammate using the enrolled phone is rejected with `FACE_MISMATCH`.
- [ ] Marking while connected to the room Wi-Fi from far outside the room gives a visibly lower fingerprint score than marking inside. *(Demo step 5; final limits come from the walk test in Phase 13)*
- [ ] A room with no fingerprint produces `NEEDS_REVIEW`, not `REJECTED`.
- [ ] The stored mark shows all five scores and their reasons.
- [ ] The student's response does not include the per-scorer breakdown.
- [ ] Changing a weight or cutoff in `.env` and restarting changes the verdict accordingly, with no code change.
- [ ] A second genuine submission after `PRESENT` returns the existing mark.
- [ ] End-to-end time from upload to response is under 2 seconds on the demo laptop.

## Deferred to Phase 13

- Unit tests for each scorer and for fusion, using recorded inputs.
- The walk test that sets the fingerprint and signal limits.
- Measured false-accept and false-reject rates for face and liveness.

## Risks

| Risk | What to do |
|---|---|
| Starting thresholds reject genuine students | Everything is a setting. Phase 13 tunes it. Until then, borderline cases go to review. |
| Fingerprint varies with doors, people and time of night | It is one scored signal, not a gate, and the pattern uses several access points |
| Face worker slow under load | Score two frames for matching; run anti-spoof on action frames only |
| Two demo routers give too few neighbours for a meaningful fingerprint | Add any other visible networks in the demo room to the room map as `hostel`, or lower `FP_NEIGHBOUR_LOW` for the demo and say so |

## Hand-off to Phase 10

Phase 10 needs the `mark_recorded` event and the stored marks.
