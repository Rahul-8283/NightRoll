# Phase 8: Verification API and Hard Gates

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 2, 3, 7 |
| **Unlocks** | Phase 9 |
| **Lead** | Backend |

## Goal

The server receives a submission and runs the hard gates in a fixed order. Any failure rejects the mark with a reason, before any face is compared. A submission that passes every gate is handed to scoring. After this phase, four of the five demo steps already produce the right rejection.

## Outcome

- `POST /v1/attendance/verify` accepts the envelope from Phase 7.
- Six gates run in order, each returning pass or a reason code.
- Device-signature authentication replaces the stubs left in Phase 3.
- A repeated submission returns the original result.
- Every attempt is recorded with its outcome.

## Scope

**In:** the verify endpoint, the gate runner, six gates, device authentication for student routes, idempotency, rate limiting, attempt recording.
**Out:** scoring and verdicts for submissions that pass (Phase 9). Until then, a passing submission returns a placeholder verdict.

---

## Tasks

### 1. Gate runner

| # | Task |
|---|---|
| 1.1 | Define a gate as a function that takes the submission context and returns pass, or fail with a reason code |
| 1.2 | Keep the gates in an ordered list in one file. Adding a gate means adding one function and one line. |
| 1.3 | Stop at the first failure |
| 1.4 | Record how long each gate took and its result, for logs and for the dashboard's gate-failure counts |

### 2. Request handling before the gates

| # | Step |
|---|---|
| 2.1 | Enforce size limits: payload at most 64 KB, each frame at most 1 MB, at most 5 frames |
| 2.2 | Keep the raw `payload` bytes exactly as received. Do not re-encode them. |
| 2.3 | Parse the payload as JSON only to read `student_id`, so the device's public key can be looked up. Nothing else in it is trusted yet. |
| 2.4 | Find the real client address (task 8.1) |
| 2.5 | Apply the rate limit: one submission per student per 20 seconds. Excess returns `429`. |

### 3. Gate order

| # | Gate | Reason on failure |
|---|---|---|
| 1 | Device and signature | `DEVICE_NOT_ENROLLED`, `SIGNATURE_INVALID` |
| 2 | Window | `OUTSIDE_WINDOW` |
| 3 | Nonce | `NONCE_INVALID` |
| 4 | Integrity | `INTEGRITY_FAILED` |
| 5 | Environment | `ENVIRONMENT_FLAGGED` |
| 6 | Network | `NETWORK_MISMATCH` |

The signature gate is first because nothing in the payload can be believed until the signature is checked. This changes the order written in `docs/TRD.md` section 6.2, which lists the window first. Update the TRD in this phase.

### 4. Gate 1: device and signature

| # | Task |
|---|---|
| 4.1 | Load the student's active device. No active device fails with `DEVICE_NOT_ENROLLED`. |
| 4.2 | Verify the ECDSA P-256 signature over the raw payload bytes with the device's public key |
| 4.3 | Only after this passes, validate the payload against its schema, rejecting unknown fields |
| 4.4 | Check the payload version `v` is supported |
| 4.5 | Check each uploaded frame's SHA-256 against the hash in the payload. A mismatch fails with `SIGNATURE_INVALID`, since the frames are not the ones that were signed. |

### 5. Gate 2: window

| # | Task |
|---|---|
| 5.1 | The payload's `window_id` must be the currently open window |
| 5.2 | The server's own clock must be between `opens_at` and `closes_at` |
| 5.3 | The phone's `client_time` is recorded but never used for the decision |
| 5.4 | The student must be active and enrolled |

### 6. Gate 3: nonce

| # | Task |
|---|---|
| 6.1 | Call `consume_nonce` from Phase 3 with the payload's nonce |
| 6.2 | `missing`, `mismatch` and `already_used` all fail with `NONCE_INVALID` |
| 6.3 | Check the payload's `challenge` actions match, in order, the challenge stored with the nonce. A mismatch fails with `NONCE_INVALID`. |

The nonce is consumed here, after the signature is known to be good. A forged request therefore cannot burn a real student's nonce.

**Retry rule.** When a mark is rejected and a retry is allowed, the server issues a fresh nonce and challenge for that student, which the app fetches from the nonce endpoint. A student gets at most 3 attempts per window. After that the response says `retry_allowed: false` and points to the ground-floor scanner.

### 7. Gate 4: integrity

| # | Task |
|---|---|
| 7.1 | Send the token to Google's Play Integrity decode method using the backend's service account |
| 7.2 | The verdict's package name must equal `PLAY_INTEGRITY_PACKAGE_NAME` |
| 7.3 | The verdict's request hash must equal the SHA-256 of the raw payload bytes |
| 7.4 | The verdict's timestamp must be within 2 minutes of now |
| 7.5 | The device verdict must include `MEETS_DEVICE_INTEGRITY` |
| 7.6 | Record the app recognition verdict. For a build installed directly on the phone, apply the rule decided from the Phase 0 spike. |
| 7.7 | `PLAY_INTEGRITY_ENFORCE=false` turns a failure into a recorded warning instead of a rejection. The API refuses to start with this setting when `APP_ENV` is `pilot` or `production`. |
| 7.8 | If Google's service cannot be reached, return `503`. Never pass the gate by default. |

### 8. Gate 5: environment

| # | Task |
|---|---|
| 8.1 | Fail if the payload reports `vpn`, `proxy` or `mock_location` as true, or `on_wifi` as false |
| 8.2 | Record `developer_options` without failing |

### 9. Gate 6: network

| # | Task |
|---|---|
| 9.1 | Work out the client address. Use the forwarded-for header only when the direct connection comes from an address in `TRUSTED_PROXY_IPS`. Otherwise use the connection's own address. |
| 9.2 | Define a `NetworkVerifier` interface with one method: given the student, the room, the client address and the reported BSSID, return pass or fail with detail |
| 9.3 | Implement `SubnetVerifier`: the client address must fall inside the room's `subnet` |
| 9.4 | Also require the payload's connected BSSID to be one of the room's access points |
| 9.5 | `NETWORK_VERIFY_MODE` selects the implementation. `controller` and `radius` are placeholders that raise "not configured", filled in when the campus network allows. |
| 9.6 | `off` skips the gate and records a warning. The API refuses to start with `off` when `APP_ENV` is `pilot` or `production`. |

For the demo, each router hides its phones behind one address. The room's `subnet` in the room map is therefore set to that router's address as a single-address range. In a routed campus network it is the room's real subnet.

### 10. Device authentication for other student routes

| # | Task |
|---|---|
| 10.1 | Write a `current_device` dependency that verifies the three signed headers from Phase 4 |
| 10.2 | Reject a timestamp more than 60 seconds from server time |
| 10.3 | Replace the stubs on `GET /v1/attendance/nonce` and `POST /v1/rooms/{id}/fingerprint` |
| 10.4 | Remove the `APP_ENV=local` guard from those routes |

### 11. Idempotency

| # | Task |
|---|---|
| 11.1 | After the signature gate, compute a submission ID from the payload hash |
| 11.2 | Store the final response in Redis under that ID until the window closes |
| 11.3 | A repeat of the same submission returns the stored response and runs no gate again |
| 11.4 | If the first copy is still being processed, the repeat waits briefly, then returns the result |

### 12. Recording attempts

| # | Task |
|---|---|
| 12.1 | Every attempt that passes the signature gate inserts an `attendance_marks` row with the attempt number |
| 12.2 | A gate failure is stored as `REJECTED` with the reason code and the per-gate timings in `scores` |
| 12.3 | Attempts that fail the signature gate are not tied to a student. They are logged with the client address and counted, since the sender is unproven. |
| 12.4 | Write an audit row for each recorded attempt |

### 13. Response

A gate failure is a normal `200` response so the app can show the reason:

```json
{
  "mark_id": "uuid",
  "verdict": "REJECTED",
  "score": null,
  "reasons": [{"code": "NETWORK_MISMATCH", "message": "Request did not come from your room network"}],
  "retry_allowed": true,
  "attempts_left": 2,
  "fallback": "NONE"
}
```

The message never reveals detail that helps an attacker, such as which subnet was expected.

---

## Exit criteria

- [ ] A genuine submission from an enrolled test phone on its own room's router passes all six gates.
- [ ] The same phone on the other router is rejected with `NETWORK_MISMATCH`. *(Demo step 2)*
- [ ] A submission signed by a different phone for that student is rejected with `SIGNATURE_INVALID`. *(Demo step 4)*
- [ ] Changing one byte of the payload after signing is rejected with `SIGNATURE_INVALID`.
- [ ] Replacing a frame after signing is rejected.
- [ ] Sending the same nonce in a new submission is rejected with `NONCE_INVALID`.
- [ ] A submission after the window closes is rejected with `OUTSIDE_WINDOW`, whatever the phone's clock says.
- [ ] A submission with `vpn: true` is rejected with `ENVIRONMENT_FLAGGED`.
- [ ] Resending an identical envelope returns the identical response, and creates no second row.
- [ ] After three rejected attempts, the response says no retry is allowed.
- [ ] The nonce endpoint now refuses a request without valid signed headers.
- [ ] Starting the API with enforcement off and `APP_ENV=pilot` fails with a clear message.

## Deferred to Phase 13

- Unit tests for each gate with recorded submissions.
- Tests that the forwarded-for header is ignored from untrusted sources.
- Replay and tamper tests as an automated suite.

## Risks

| Risk | What to do |
|---|---|
| Forwarded-for header spoofed to fake a room address | Trusted only from listed proxy addresses (task 9.1) |
| Play Integrity verdict weaker than expected for directly installed builds | Rule set from the Phase 0 spike; recorded, and stated in the demo |
| Clock difference between phone and server breaks header checks | 60-second allowance, and the marking decision uses server time only |
| A gate turned off for testing reaches the demo | Startup check refuses unsafe settings outside local |

## Hand-off to Phase 9

Phase 9 replaces the placeholder verdict with scoring. It needs the verified payload, the frames and the room record.
