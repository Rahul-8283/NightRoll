# NightRoll runbook

For the person running NightRoll on the night. Every step names the exact command or screen. If something here does not match what you see, stop and ask the person who built it.

## Where things are

| What | Where |
|---|---|
| Warden dashboard | `https://<SERVER_NAME>/` (the name in `infra/.env`) |
| System page (admins) | Dashboard, **System** in the left menu |
| API health | `https://<SERVER_NAME>/v1/health` |
| Logs | `docker compose -f infra/docker-compose.yml logs -f <service>` with `api`, `scheduler`, `face-worker` or `nginx` |
| Ground-floor scanner | The fallback for every problem below |

Every log line is JSON and carries a `request_id`. The same ID is in the student's error message (when the app shows one), in nginx's log, in the API's log and in the face worker's log, so one search finds the whole story of a request.

## Start and stop

Start order is handled by Compose: face worker, then API, then scheduler and nginx.

```bash
# from the repo root
docker compose -f infra/docker-compose.yml up -d --build   # start (build the images if the code changed)
docker compose -f infra/docker-compose.yml ps              # every service should say "healthy"
docker compose -f infra/docker-compose.yml stop            # stop everything, keep the containers
docker compose -f infra/docker-compose.yml down            # stop and remove the containers
docker compose -f infra/docker-compose.yml restart face-worker   # restart one service
```

The face worker takes up to two minutes to load its model, so `ps` shows it as "starting" first. Do not restart it during that time.

If the API refuses to start, its log says why in one line. In `pilot` or `production` mode it names the unsafe setting (Play Integrity off, network check off, MFA off, proxy list empty or open, short service token, anti-spoof model missing). In `demo` mode it starts and prints a banner listing everything that is relaxed.

## Before a window

Do this 30 minutes before the window opens. All of it is on the **System** page.

- [ ] `docker compose ... ps` shows every service healthy.
- [ ] System page: Database, Redis, Face worker and Scheduler are all **Healthy**.
- [ ] Scheduler: "Last checked in" is under a minute ago.
- [ ] Face worker: shows the model name, and no "anti-spoof model missing".
- [ ] No red or blue alert banner at the top of any page.
- [ ] **Windows** page: tonight's window has the right times, or is marked off if it is an off night.
- [ ] If Play Integrity is meant to be on (pilot, production): there is no "Relaxed settings are on" box on the System page.
- [ ] One test phone has marked successfully since the last change to the server.

## During a window

Alerts appear as a banner on every page for every warden. They clear on their own about 15 seconds after the cause is fixed.

| Alert | What it means | What to do |
|---|---|---|
| **The face check is down while attendance is open** | The face worker is not answering, or has no model loaded. Students who try to mark are sent to the ground-floor scanner. | `docker compose ... restart face-worker`, then watch **System**. If it stays down, read `docker compose ... logs face-worker`. Tell students to use the ground-floor scanner meanwhile. Nothing is lost: attempts during the outage are not recorded as rejections. |
| **The scheduler has not been seen** | The process that opens and closes windows has stopped. A window may not open or close by itself. | `docker compose ... restart scheduler`. If the window should be open or closed now, use **Open now** or **Close now** on the **Windows** page. |
| **N% of the last M attempts in five minutes were rejected** | More than a fifth of recent attempts failed. It needs at least five attempts to appear. | Open **System**, "Stopped at a gate". One gate dominating tells you where to look: `NETWORK_MISMATCH` means a router (see below); `INTEGRITY_FAILED` means Play Integrity or a build problem; `SIGNATURE_INVALID` means phones that are not enrolled. |

## A router is down in a room

Signs: the room's students are rejected with `NETWORK_MISMATCH`, or the room's tile shows **Check the router**.

1. Power-cycle the router. Check its lamp and that its uplink cable is in.
2. Students in that room use the ground-floor scanner until it is back.
3. For each of those students, record a **manual mark** on the **Absentees** page: find the student, write why you are recording it by hand (at least 10 characters, for example "Router down, seen at the scanner"), and confirm. It is logged in the audit trail.
4. If the router was replaced, its BSSID changed. Update the room's access points in `config/rooms.local.json`, re-run the seed, and follow the **Re-scan this room's Wi-Fi** prompt on the room page.

## The server is down

Students and wardens cannot reach anything.

1. Everyone uses the ground-floor scanner. Write down who is marked on paper.
2. On the server machine: `docker compose -f infra/docker-compose.yml up -d`. If Docker itself is stopped, start Docker Desktop first.
3. If it comes back, the **Windows** page shows the window as it was. If the window passed while the server was down, it is marked closed and the absentee list covers everyone not marked. Record the paper marks as **manual marks** on the **Absentees** page. Wardens can do this for 24 hours after the window closes; an admin can do it for any past night.
4. If it does not come back, read `docker compose ... logs api` and `... logs nginx`. The three common causes are an expired or missing certificate in `infra/certs`, a changed address for the laptop (phones and the certificate use it), and no internet (Supabase and Google need it).

## A student's phone is lost or replaced

1. **Enrollment** page, search the student, and create a code for them. The code lasts 15 minutes and works once.
2. The student enrolls on the new phone. At that moment the old phone's key is switched off for good.
3. If the old phone might be in the wrong hands and the student cannot enroll right away, an admin switches the key off at once in the Supabase SQL editor:

   ```sql
   update devices set active = false where student_id = '<the student id>';
   ```

   The student cannot mark until they enroll again.

## A warden loses their authenticator

An admin resets it. Wardens cannot reset their own.

1. Supabase dashboard, **Authentication**, **Users**, open the warden, and remove their MFA factor ("Remove MFA factors").
2. Tell the warden to sign in again. They are asked to set up a new authenticator and must scan the new QR code before they can use the dashboard.
3. If you cannot find the option, delete the factor through the Auth admin API (`DELETE /auth/v1/admin/users/<user id>/factors/<factor id>` with the service role key, from a trusted machine, never from a browser).

An admin who loses theirs needs another admin. Keep at least two admin accounts.

## A secret was leaked

Assume anyone who saw it can use it. Rotate first, then find out how it got out.

| Secret | Where it lives | How to rotate |
|---|---|---|
| Supabase **service role key** | `backend/.env`, `face/.env` | Supabase, Project settings, API keys: roll the key. Put the new one in both files and restart `api`, `scheduler` and `face-worker`. This key bypasses every row-level rule, so do it first. |
| Supabase **JWT secret** | `backend/.env` | Supabase, Project settings, JWT: generate a new secret. Every signed-in warden is signed out. Update `backend/.env`, restart `api`. |
| Supabase database password | `DATABASE_URL` in `backend/.env` | Supabase, Database settings: reset the password. Update `backend/.env`, restart `api` and `scheduler`. |
| **Upstash Redis** password | `REDIS_URL` in `backend/.env` | Upstash console: reset the password. Update `backend/.env`, restart `api` and `scheduler`. Open nonces are lost; students just try again. |
| **Face worker token** | `backend/.env` and `face/.env` (same value in both) | `openssl rand -hex 32`. Put the same value in both files, restart `face-worker` then `api`. |
| **Google service account** key | `backend/secrets/google-service-account.json` | Google Cloud, IAM, Service accounts: create a new key, delete the old one, replace the file, restart `api`. |
| The local **certificate authority** key (`rootCA-key.pem`) | The machine that ran `mkcert` | Anyone with it can impersonate the server to every phone that trusts the authority. Make a new authority, re-issue the server certificate, install the new authority on every phone, rebuild the app with it (it is pinned in the app), and delete the old one from the phones. |

Never paste a secret into chat, an issue or a commit. If one reached the git history, rotating it is the fix; deleting the commit is not.

## Restoring data

The database is Supabase's, so backups are Supabase's.

- **What the plan includes:** record it here when you know it. Supabase Free has no dashboard backups. Pro keeps daily backups for 7 days, and point-in-time recovery is a paid add-on. Check **Database, Backups** in the Supabase dashboard for this project and write the answer on the next line.
- **Plan and backup option for this project:** _not recorded yet. The Supabase account connected while this was written does not list the NightRoll project, so it could not be read._
- **Restoring:** on a plan with backups, Supabase dashboard, **Database, Backups**, choose the backup or the point in time and restore. A restore replaces the whole database, so ask an admin to agree first and tell wardens that anything after the restore point is gone. On a plan without backups there is nothing to restore from; the audit trail and the exports are the record.
- **Before any risky change** (a migration, a large edit), export the attendance you will need: **Export** page, the date range, CSV.
- Face embeddings are the one thing that cannot be rebuilt from a CSV. Losing them means every affected student enrolls again.
- Captured frames are not backed up. They are deleted after 24 hours on purpose.
