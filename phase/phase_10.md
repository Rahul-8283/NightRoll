# Phase 10: Warden Dashboard and Live Updates

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 2, 3, 9 |
| **Unlocks** | Phase 11 |
| **Lead** | Dashboard |
| **Can start early** | Login and layout need only Phase 2 |

## Goal

The warden opens a web page, logs in with a password and a one-time code, and watches the hostel fill in room by room as students mark attendance. This is the screen the judges look at during the demo.

## Outcome

- A React dashboard with login, a live floor view, window controls and an enrollment desk.
- A room tile changes colour within two seconds of a verdict.
- The page recovers on its own if the live connection drops.

## Scope

**In:** project setup, login with multi-factor, layout, floor heatmap, room detail, window controls, enrollment desk, live updates, the WebSocket endpoint.
**Out:** review actions, overrides, manual marks, exports and the audit view (Phase 11).

---

## Tasks

### 1. Project setup

| # | Task |
|---|---|
| 1.1 | Create the dashboard in `dashboard/` with Vite, React and TypeScript |
| 1.2 | Add `@supabase/supabase-js` for login only, a router, and a data-fetching library with caching |
| 1.3 | Read the four variables in `dashboard/.env.example` |
| 1.4 | Write `dashboard/README.md` with install, run and build steps |

```text
dashboard/
├── src/
│   ├── api/              Typed client for the NightRoll API
│   ├── auth/             Supabase session, MFA steps, route guard
│   ├── live/             WebSocket client and state
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Tonight.tsx
│   │   ├── Room.tsx
│   │   ├── Windows.tsx
│   │   └── Enrollment.tsx
│   ├── components/
│   └── theme/
├── .env.example
└── README.md
```

The dashboard never queries Supabase tables. It uses Supabase to log in, then sends the access token to the NightRoll API.

### 2. Login

| # | Task |
|---|---|
| 2.1 | Email and password form, using Supabase Auth |
| 2.2 | On first login, guide the warden through setting up an authenticator app: show the QR code, confirm with a code |
| 2.3 | On later logins, ask for the six-digit code after the password |
| 2.4 | Only a session that has passed the code step can reach any page past login |
| 2.5 | Refresh the access token before it expires. If refresh fails, return to login. |
| 2.6 | A logged-in user without the `warden` or `admin` role sees "This account has no access" and nothing else |
| 2.7 | Log out clears the session and closes the live connection |
| 2.8 | There is no sign-up link. Accounts are created by an admin. |

### 3. Layout

| Area | Content |
|---|---|
| Top bar | Hostel name, tonight's window with a countdown, connection status, account menu |
| Side navigation | Tonight, Review, Absentees, Windows, Enrollment, Audit (the middle items arrive in Phase 11) |
| Main | The current page |

Design notes:
- The Tonight page must be readable from across a room on a projector: large tiles, strong contrast.
- Works on a tablet at the warden's desk as well as a laptop.
- Status is never shown by colour alone. Each state also has a label or icon.

### 4. Tonight page

**Summary strip**

| Tile | Value |
|---|---|
| Present | Count and share of enrolled students |
| Needs review | Count, links to the review queue |
| Not yet marked | Count |
| Rejected attempts | Count |
| Time left | Countdown to close |

**Floor heatmap**

| # | Task |
|---|---|
| 4.1 | One section per floor, one tile per room, ordered by room number |
| 4.2 | Each tile shows the room number and "present of total", for example "3 / 4" |
| 4.3 | Tile states: all present, some present, none yet, needs review, problem |
| 4.4 | A tile that just changed pulses once, so the eye catches it during the demo |
| 4.5 | Clicking a tile opens the room page |
| 4.6 | Before the window opens, tiles are neutral with a "Window opens at 10:00 PM" banner |
| 4.7 | After the window closes, the view freezes on the final state, with a "Closed" banner |

**Recent activity**

| # | Task |
|---|---|
| 4.8 | A short live list of the latest verdicts: time, room, student, verdict |
| 4.9 | Rejected attempts show the reason code in plain words |

### 5. Room page

| # | Task |
|---|---|
| 5.1 | List the room's students with tonight's status and the time of their mark |
| 5.2 | For each mark, show the trust score and the five signal scores as labelled bars |
| 5.3 | Show the room's fingerprint status: version, when it was captured, how many access points it holds |
| 5.4 | A "Reset room fingerprint" button, with a confirmation step |
| 5.5 | Show enrollment status per student: face, device, and the device's key security level |

Faces and frames are never shown here. Viewing frames for a disputed mark is a Phase 11 feature.

### 6. Windows page

| # | Task |
|---|---|
| 6.1 | Show tonight's window with its state |
| 6.2 | A form to set opening and closing times for a date |
| 6.3 | A calendar to mark off days |
| 6.4 | "Send reminder" to students who have not marked |
| 6.5 | For an admin only: "Open now" and "Close now", each with a confirmation. These drive the demo. |
| 6.6 | A list of past windows with their final counts |

### 7. Enrollment page

The warden's desk tool.

| # | Task |
|---|---|
| 7.1 | Search for a student by roll number or name |
| 7.2 | Show their enrollment status |
| 7.3 | "Create enrollment code" shows the code large on screen, with a countdown to its expiry. It is shown once. |
| 7.4 | The status updates live when the student's phone finishes enrolling |
| 7.5 | "Withdraw consent" for a student, with a typed confirmation |
| 7.6 | "Change room" for a student |

### 8. Live updates

**Backend: `WS /v1/ws/rooms`**

| # | Task |
|---|---|
| 8.1 | The browser cannot set headers on a WebSocket, so the first message from the client carries the access token. The server closes the connection if no valid warden token arrives within 5 seconds. |
| 8.2 | On a valid token, send a `snapshot` message with every room's current counts |
| 8.3 | Subscribe to the Redis channel from Phase 9 and forward each event as a `room_update` |
| 8.4 | Also forward `window_state` changes and `enrollment_update` events |
| 8.5 | Send a `ping` every 20 seconds. Drop clients that stop answering. |
| 8.6 | Close the connection when its token expires. The client reconnects with a fresh one. |
| 8.7 | Add `GET /v1/attendance/tonight`, which returns the same data as the snapshot, for the fallback |

Message shapes:

```json
{"type": "snapshot", "window": {"id": "uuid", "state": "open", "closes_at": "..."}, "rooms": [{"room_id": "uuid", "present": 3, "total": 4, "pending_review": 1}]}
{"type": "room_update", "room_id": "uuid", "present": 4, "total": 4, "pending_review": 0, "last": {"student": "…", "verdict": "PRESENT", "at": "..."}}
{"type": "window_state", "window_id": "uuid", "state": "closed"}
```

Using Redis as the channel means updates still reach every dashboard if the API later runs as more than one process.

**Dashboard client**

| # | Task |
|---|---|
| 8.8 | Connect after login, authenticate, apply the snapshot, then apply updates as they arrive |
| 8.9 | On disconnect, retry after 1, 2, 4, 8 seconds, up to 30 seconds between tries |
| 8.10 | After reconnecting, apply the new snapshot so nothing missed while offline is lost |
| 8.11 | If the WebSocket cannot connect after several tries, poll `GET /v1/attendance/tonight` every 5 seconds |
| 8.12 | Show the connection state in the top bar: Live, Reconnecting, Polling |

### 9. Error and empty states

| Case | Shown |
|---|---|
| API unreachable | A banner with retry, and the last known data greyed |
| No window tonight | "No attendance window tonight", with a link to the Windows page |
| No rooms seeded | A message pointing to the seed script |
| Action failed | The error message from the API and its request ID |

---

## Exit criteria

- [ ] A warden logs in with password and authenticator code and reaches the Tonight page.
- [ ] A session that skipped the code step cannot open any page past login.
- [ ] An account without a role sees the no-access message.
- [ ] With a window open, a test phone marking present turns its room tile within 2 seconds, with no page refresh. *(Demo step 1, visible half)*
- [ ] A rejected attempt appears in recent activity with its reason.
- [ ] Stopping and restarting the API, the dashboard reconnects on its own and shows the correct state.
- [ ] With WebSocket blocked, the page falls back to polling and still updates.
- [ ] An admin can open and close the window from the Windows page. A warden does not see those buttons.
- [ ] Creating an enrollment code shows it once, and the status flips live when a phone enrolls.
- [ ] The Tonight page is readable on a projector and usable on a tablet.

## Deferred to Phase 13

- Component tests for tile states and the live reducer.
- A check of the reconnect logic under repeated drops.
- Accessibility pass: keyboard use and contrast.

## Risks

| Risk | What to do |
|---|---|
| Venue Wi-Fi blocks WebSockets | Polling fallback (task 8.11) |
| Token expires mid-demo | Automatic refresh, and the live connection re-authenticates |
| Too many tiles for one screen | Collapse floors, and show only the demo floor on stage |
| Warden loses their authenticator | An admin resets the factor in Supabase; document the steps |

## Hand-off to Phase 11

Phase 11 adds pages to this app and needs the layout, the API client and the live connection.
