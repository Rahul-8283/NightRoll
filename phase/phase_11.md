# Phase 11: Review, Override, Absentees, Export and Audit

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 9, 10 |
| **Unlocks** | Phase 12 |
| **Leads** | Backend, Dashboard |

## Goal

Give the warden the final say. Borderline marks land in a queue with the evidence beside them. The warden can approve, decline, override any verdict, or record a mark by hand. At the end of the night there is an absentee list, a record that can be exported, and a trail of who decided what.

## Outcome

- A review queue with a clear decision for each borderline mark.
- Override and manual mark, each requiring a written reason.
- An absentee list after the window closes.
- CSV export by date range, floor or room.
- A read-only audit view.
- The student's app shows the outcome of a review.

## Scope

**In:** review endpoints and page, override, manual mark, frame viewing for disputes, absentee page, export, audit page, notifying the student, room health flags.
**Out:** deployment and hardening (Phase 12).

---

## Tasks

### 1. Effective status

A student can have several rows in a window: rejected attempts, then a mark in review, then a review decision. One function decides what counts.

| Order | Condition | Effective status |
|---|---|---|
| 1 | A review with decision `OVERRIDDEN` exists | The status the override set |
| 2 | A `MANUAL` mark exists | Present (manual) |
| 3 | A `PRESENT` mark exists | Present |
| 4 | A `NEEDS_REVIEW` mark with decision `APPROVED` | Present (approved) |
| 5 | A `NEEDS_REVIEW` mark with decision `DECLINED` | Absent |
| 6 | A `NEEDS_REVIEW` mark with no decision | Pending review |
| 7 | An `ABSENT` mark, or only rejected attempts after close | Absent |
| 8 | Window still open, nothing above | Not yet marked |

| # | Task |
|---|---|
| 1.1 | Implement this as one database view, `student_window_status`, so the dashboard, the export and the room counts all agree |
| 1.2 | Marks are never edited or deleted. A decision adds a `reviews` row. |
| 1.3 | Change the room counts in Phase 10's snapshot to read from this view |

### 2. Review endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/reviews?window_id=` | Warden | Marks awaiting a decision, oldest first |
| GET | `/v1/attendance/marks/{mark_id}` | Warden | One mark: scores, reasons, earlier attempts |
| POST | `/v1/attendance/marks/{mark_id}/review` | Warden | `{decision: APPROVED or DECLINED, note}` |
| POST | `/v1/attendance/marks/{mark_id}/override` | Warden | `{status: PRESENT or ABSENT, note}` |
| POST | `/v1/attendance/manual` | Warden | `{student_id, window_id, note}` |

Rules:
- `review` applies only to a mark in `NEEDS_REVIEW` with no decision yet. A second decision returns `409`.
- `override` applies to any mark. It replaces an earlier decision on that mark, and both stay in the audit log.
- `note` is required for `DECLINED`, for every override and for every manual mark. At least 10 characters.
- A manual mark is allowed during the window and for 24 hours after it closes. Later corrections need an admin.
- A manual mark for a student who is already present returns `409`.
- Every action writes an audit row in the same transaction, with the warden's ID, the decision and the note.
- Every action publishes a room update, so all open dashboards change at once.

### 3. Review page

| # | Task |
|---|---|
| 3.1 | A queue of cards, one per mark awaiting review, with a count in the navigation |
| 3.2 | Each card shows: student, room, time, trust score, and the five signal scores as labelled bars |
| 3.3 | Plain-language reasons for the low signals. For Wi-Fi, list what was off: "Expected neighbour networks missing: 3 of 5", "Unknown networks seen: 4" |
| 3.4 | Earlier attempts by the same student tonight, with their reasons |
| 3.5 | The room's fingerprint age, so a stale fingerprint is obvious |
| 3.6 | Buttons: Approve, Decline. Decline opens a note field. |
| 3.7 | New review items appear live. A card decided by another warden disappears live. |
| 3.8 | Keyboard shortcuts for approve and decline, to clear a queue quickly |

### 4. Viewing frames for a disputed mark

Frames exist for 24 hours so a dispute can be settled. Access is narrow.

| # | Task |
|---|---|
| 4.1 | `POST /v1/attendance/marks/{mark_id}/frames/view` (warden): requires a written reason, writes an audit row, then asks the face worker for links |
| 4.2 | Add `POST /frames/links` to the face worker: returns signed links for one mark's frames that expire in 60 seconds |
| 4.3 | The backend passes the links through. It never downloads or stores the frames itself. |
| 4.4 | The review card has a "View captured frames" button, which shows the reason prompt first |
| 4.5 | If the frames were already deleted, say so: "Frames are removed after 24 hours" |

Every frame view is in the audit log with the warden's name and reason.

### 5. Absentee page

| # | Task |
|---|---|
| 5.1 | `GET /v1/attendance/absentees?window_id=` returns students whose effective status is absent, with room, floor and the reason: no attempt, rejected attempts only, or declined in review |
| 5.2 | A page listing them, grouped by floor |
| 5.3 | While the window is open, the page is titled "Not yet marked" and offers "Send reminder" |
| 5.4 | After close, each row has "Record manual mark", for a student who was verified in person |
| 5.5 | Students with no enrolled device are shown separately, since they use the ground-floor scanner |

### 6. Export

| Method | Path | Auth |
|---|---|---|
| GET | `/v1/exports/attendance?from=&to=&floor=&room=` | Warden or admin |

| # | Task |
|---|---|
| 6.1 | Stream a CSV: date, roll number, name, room, floor, effective status, marked-at time, how it was decided (automatic, approved, manual, override), decided by, note |
| 6.2 | No scores, no reasons, no network details and nothing biometric in the export |
| 6.3 | Limit a single export to 31 days |
| 6.4 | Guard against spreadsheet formula injection: any cell starting with `=`, `+`, `-` or `@` is prefixed with a single quote |
| 6.5 | Write an audit row for every export, with the filters used |
| 6.6 | An Export page with date pickers, floor and room filters, and a download button |

### 7. Audit page

| Method | Path | Auth |
|---|---|---|
| GET | `/v1/audit?from=&to=&actor=&action=` | Admin |

| # | Task |
|---|---|
| 7.1 | Paged, newest first, filterable by date, person and action type |
| 7.2 | Actions covered: window changes, enrollment codes, enrollments, withdrawals, reviews, overrides, manual marks, frame views, exports, fingerprint resets |
| 7.3 | Read-only. There is no edit or delete anywhere. |

### 8. Telling the student

| # | Task |
|---|---|
| 8.1 | Add `GET /v1/attendance/status` (device signature): the student's effective status for tonight |
| 8.2 | When a review or override changes a student's status, send a data push with `type=status_changed`. No detail in the message. |
| 8.3 | The app fetches the status on receiving it and updates the Home screen: "Approved by your warden" or "Marked absent by your warden. Please see the warden." |
| 8.4 | The Home screen also fetches the status whenever the app opens |

### 9. Room health flags

| # | Task |
|---|---|
| 9.1 | Flag a room when more than 30% of its marks over the last 7 days went to review or were rejected for Wi-Fi reasons |
| 9.2 | Flag a room when none of its students has seen the room's own access point tonight, which suggests the router is down |
| 9.3 | Show flags on the room tile and the room page, with a suggested action: "Re-scan this room's Wi-Fi" or "Check the router" |

---

## Exit criteria

- [ ] A mark in `NEEDS_REVIEW` appears in the queue with its scores and reasons.
- [ ] Approving it turns the room tile and the student's app to present.
- [ ] Declining it requires a note and makes the student absent.
- [ ] A second decision on the same mark returns `409`.
- [ ] Overriding a rejected mark to present requires a note and is reflected everywhere.
- [ ] A manual mark for an absent student works within 24 hours of close and is refused for a warden after that.
- [ ] Viewing frames asks for a reason, shows the frames, and the links stop working after a minute.
- [ ] The absentee list after close matches the students with no present status.
- [ ] The CSV opens in a spreadsheet with the right columns and contains no scores.
- [ ] Every action above has a row in the audit page with the right person and note.
- [ ] Two dashboards open side by side stay in step when one warden acts.

## Deferred to Phase 13

- Tests for the effective-status view across every combination of marks and reviews.
- Tests for the export's injection guard and date limit.
- Permission tests: warden against admin for each action.

## Risks

| Risk | What to do |
|---|---|
| Review queue too long on the first nights | Keyboard shortcuts, clear reasons, and threshold tuning in Phase 13 |
| Overrides used to bypass the system | Required notes and a full audit trail an admin can read |
| Frame access misused | Reason required, logged, links expire in a minute, frames gone in 24 hours |
| Status logic disagrees between screens | One database view is the single source for all of them |

## Hand-off to Phase 12

Phase 12 packages everything. It needs the full list of services, ports and env variables as they now stand.
