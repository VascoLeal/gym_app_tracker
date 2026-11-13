# Deployment

Production runs on two Render services, defined in [`render.yaml`](../render.yaml), and a Neon database:

| Piece | Where | Notes |
|---|---|---|
| Frontend (`voacs`) | Render static site | Free. Serves the built React app over HTTPS. |
| Backend (`voacs-api`) | Render web service, Frankfurt | Free. Sleeps after 15 idle minutes and takes about a minute to wake. |
| Database | Neon, a project separate from dev | Starts empty. Test data stays in the dev project. |

The `main` branch is production: **every push to `main` deploys**, and that includes running any new migrations. Build on `feature/*` branches and merge a milestone when it's finished.

## First-time setup

### 1. Create the production database

You end up with two databases that never mix:

| Database | Used by | Holds | Where its URL goes |
|---|---|---|---|
| Your existing Neon project (dev) | Your PC: `uv run ...`, tests, scripts | Test data you can throw away | `backend/.env`. **Leave it as it is.** |
| `voacs-prod` (new) | The deployed app only | Your real training history | Render only. **Never in `.env`.** |

Keeping them apart means nothing you do locally, such as a broken migration or a test script, can touch real training data.

1. In [Neon](https://console.neon.tech), create a **new project** named `voacs-prod`, in the AWS Frankfurt region. The free plan allows many projects, so this costs nothing.
2. Open **Connect**, turn **connection pooling off**, and copy the connection string. Neon recommends a direct connection for migrations, and production runs its migrations on every deploy. Your dev `.env` can stay pooled.
3. Change the start of the string from `postgresql://` to `postgresql+psycopg://`. The app won't connect without this.

### 2. Put the code on `main`

```
git checkout main
git merge --ff-only feature/frontend
git push origin main feature/frontend
git checkout feature/frontend
```

### 3. Create the Render services

1. Sign in to [Render](https://dashboard.render.com) with GitHub and allow it to access the `gym_app_tracker` repo. If a screen asks for a card, check that both services still say Free before continuing.
2. Choose **New → Blueprint**, pick the repo and the `main` branch.
3. Render asks for four values. Two of them are the services' own web addresses. Render builds each one from the service's name, so the backend `voacs-api` is normally at `https://voacs-api.onrender.com` and the frontend `voacs` at `https://voacs.onrender.com`. The two services point at each other:

| Variable | Set on | Value | Why |
|---|---|---|---|
| `DATABASE_URL` | `voacs-api` | The `voacs-prod` string from step 1 | Where the backend stores data |
| `CORS_ALLOWED_ORIGINS` | `voacs-api` | The **frontend's** address: `https://voacs.onrender.com` | The backend only accepts browser requests from this site |
| `REGISTRATION_ALLOWED_EMAILS` | `voacs-api` | `you@example.com,her@example.com` | Only these emails can create an account |
| `VITE_API_BASE_URL` | `voacs` | The **backend's** address: `https://voacs-api.onrender.com` | Where the app sends its requests |

4. Apply it and wait for both services to go green. The backend's first build also creates the tables and seeds the reference data.

### 4. Confirm the addresses

The two addresses in step 3 are a guess. If someone else on Render already uses a name, Render adds a random suffix, for example `https://voacs-k3f9.onrender.com`. Open each service and read its real address at the top of the page. If both match what you typed, skip to the phone check.

If one differs, update the variable that holds it:

- **The frontend's address differs:** on `voacs-api`, under **Environment**, set `CORS_ALLOWED_ORIGINS` to the real frontend address and save.
- **The backend's address differs:** on `voacs`, under **Environment**, set `VITE_API_BASE_URL` to the real backend address and save. This value is built into the app, so also run **Manual Deploy → Deploy latest commit**.

## Adding or removing users

`REGISTRATION_ALLOWED_EMAILS` only controls who can **create** an account. To let someone else in, add their email to the list on `voacs-api` (comma-separated, no spaces needed) and save; Render restarts the backend with the new list. They then register normally.

Taking an email off the list doesn't stop an account that already exists from logging in. There's no account deletion yet; it's in the constitution's security baseline but not built.

## Renaming the app later

The display name ("voacs" on the home-screen icon and the browser tab) is two lines of code: `name`/`short_name` in `frontend/public/manifest.webmanifest`, and `<title>` in `frontend/index.html`.

The **address** can't be renamed: Render fixes the `.onrender.com` address when a service is created, and renaming a service doesn't change it. If you want a new address, you have two options:

- **Your own domain (recommended if the name matters):** buy one (about €10 a year) and connect it under the frontend's **Settings → Custom Domains**. Render's free Hobby workspace includes two, with HTTPS. Later name changes then only mean changing the domain.
- **New services:** create the services again under new names. Your data is safe because it lives in Neon, not on Render.

Either way the frontend's address changes, which has two side effects. Each address keeps its own saved login, so everyone logs in once more. Home-screen icons still point at the old address, so everyone reinstalls the app. Also update `CORS_ALLOWED_ORIGINS` for the new frontend address.

## Verify on a phone

1. Open the frontend URL. Wait up to a minute if you see "Waking the server".
2. Try to register with an email that isn't on the list. You should see "Registration is closed."
3. Register with your own email. You should land on Home.
4. Refresh the page. You should stay on Home, not get a "Not Found" page.
5. Install it:
   - **Android:** open the address in **Chrome**, then menu → **Add to Home screen** or **Install app**. Use Chrome even if another browser is your default. Some other browsers, such as Samsung Internet, build the app's Android package themselves, and Google Play Protect blocks it as "built for an older version of Android". Don't override that warning; install from Chrome instead.
   - **iPhone (Safari):** Share → **Add to Home Screen**. iOS never prompts for this by itself.
6. Open it from the icon. It should show the barbell icon and open without a browser address bar.
7. Close it, wait at least 20 minutes, and open it again. It should say the server is waking, then reach Home **still logged in**.
8. Repeat steps 3–6 on the iPhone with the second account.

## Normal log lines that look alarming

| Line | What it is |
|---|---|
| `warning: VIRTUAL_ENV=/opt/render/project/src/.venv does not match the project environment path .venv` | Render expects the virtual environment at the repo root, but the backend lives in `backend/`, so uv uses `backend/.venv`. Build and start both use that same folder, so it's harmless. |
| `"HEAD / HTTP/1.1" 404` or `"GET / HTTP/1.1" 404` | Nothing lives at the API's root address. Render probes it once at startup, and bots scan every public address. The app itself never calls `/`. |
| A steady stream of `GET /health ... 200` from `10.x.x.x` addresses | Render's own health checks, from inside its network. |
| No `Running upgrade` line after `Will assume transactional DDL` | The database is already up to date, so there was no migration to run. |

Seeing `{"detail":"Not Found"}` at `https://voacs-api.onrender.com/` is expected for the same reason as the 404s. The app lives at the frontend address. `https://voacs-api.onrender.com/health` should answer `{"status":"ok"}`, and `/docs` lists every API endpoint.

## When something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend build fails with `No module named 'psycopg2'` | `DATABASE_URL` still starts with `postgresql://` | Add `+psycopg` |
| "Can't reach the server" on every attempt | Wrong `VITE_API_BASE_URL`, or the backend is down | Check the value, redeploy the frontend, and read the backend's logs |
| The app won't load data, and the browser console mentions CORS | `CORS_ALLOWED_ORIGINS` doesn't match the frontend's URL | It must be `https://` plus the host, with no path |
| Frontend build fails with `VITE_API_BASE_URL must be set` | The variable is missing | Add it and redeploy |
| Play Protect: "Unsafe app blocked … built for an older version of Android" | The install was started from a browser other than Chrome | Remove any half-installed icon, then install from Chrome |
| "Registration is closed" for an invited user | Their email isn't on the list | Fix `REGISTRATION_ALLOWED_EMAILS` on `voacs-api` |

## Limits of the free plan

- The free plan has no shell or pre-deploy step, so migrations and the seed run in the build command. A migration that succeeds followed by a failed deploy leaves the database ahead of the running code, so keep migrations compatible with the previous version.
- Until offline support ships, a sleeping backend also delays logging, not just syncing.
- `JWT_SECRET_KEY` is generated by Render. Changing it logs everyone out but loses no data.
