# Architecture & Discovery Document

*Created: 2026-08-25. Purpose: resolve the "Open — to be resolved in the discovery/architecture document" items from `project-brief.md` §2. Each decision below is a recommendation with rationale — not yet written into `project-brief.md` as Decided. Once you confirm or adjust these, I'll fold the final choices into an updated `project-brief.md`.*

*Research note: framework/hosting/library facts below were verified via web search on 2026-08-25 rather than pulled from training data, per the project's own rule that these can't be assumed stale. Treat exact free-tier limits as a snapshot — worth a quick re-check at the moment you actually sign up, since these change often.*

---

## 1. Decision Summary

| Area | Recommendation | Confidence |
|---|---|---|
| Backend framework | FastAPI | High |
| Package manager | uv | High |
| Password hashing | argon2-cffi (Argon2id) | High |
| ORM / migrations | SQLAlchemy 2.x + Alembic | High |
| Database | PostgreSQL | High |
| DB hosting | Neon (free tier) | Medium-high |
| Backend hosting | Render (free tier) to start | Medium |
| Frontend framework | React + TypeScript (Svelte is a real alternative — your call, see §4.1) | **Needs your input** |
| Offline storage | Dexie.js (IndexedDB wrapper) | High |
| Sync strategy | Manual/foreground-triggered sync as the baseline; Background Sync API as an Android-only bonus, never the backbone | High |

---

## 2. Backend

### 2.1 Framework: FastAPI — confirmed

Your candidate holds up. FastAPI added official Python 3.14 support, and its core dependencies (Starlette, Pydantic v2, Uvicorn) all currently support 3.14 too. One caveat: a few third-party FastAPI *extension* packages (e.g. `fastapi-sqla`) haven't caught up to 3.14 yet — nothing that affects your MVP, but worth checking package-by-package the first time you `uv add` something unfamiliar, rather than assuming.

### 2.2 Package manager: uv (not Poetry)

Your brief flagged this as open. As of 2026, uv has become the default recommendation for new Python projects, including for beginners — it's 10-100x faster than pip, and it replaces pyenv + virtualenv + pip-tools with one tool, which matters for you specifically because you're on Windows with a brand-new Python version (3.14) and no existing toolchain to migrate away from. Poetry remains fine, but there's no reason to start there in 2026 when uv can also manage your Python installation itself.

**⚠️ Pushback on a related default:** Many FastAPI tutorials will point you toward **SQLModel** (also by FastAPI's creator), which merges your database table definition and your API schema into one class. It's convenient, but it directly conflicts with your own constitution (§3, "Clean architecture" — domain logic independent of persistence, and §2's insistence on distinguishing library/template/prescribed/performed/historical exercise concepts). If your ORM model *is* your API schema *is* your domain object, those boundaries blur by construction. Recommendation: use plain **SQLAlchemy 2.x models** for persistence and separate **Pydantic models** for API request/response shapes, with your domain layer (the progression engine, etc.) built on its own plain Python classes that don't import SQLAlchemy or Pydantic at all. More typing upfront, but it's what makes `recommend_next_set(...)` unit-testable without a database — which your constitution explicitly requires.

### 2.3 Password hashing: argon2-cffi (Argon2id)

Your original spec said "a mature library" without naming one. Argon2id is OWASP's current top recommendation (bcrypt is still safe but is the 2014-era default; Argon2 won the Password Hashing Competition and has since become the standard for new projects). `argon2-cffi` officially supports Python 3.14 with no compatibility caveats. This is a small, low-risk decision — flagging it mainly so it's recorded rather than re-litigated later.

Auth *mechanism* (sessions vs. JWT, refresh token design, where tokens live client-side) is a real design question, but it belongs to the Auth milestone itself, not this document — it interacts with the offline architecture (§4.3) in ways worth designing carefully rather than deciding in passing here.

---

## 3. Database & Hosting

### 3.1 Database: PostgreSQL (not SQLite)

Your brief listed both as candidates. Given the constitution's "multi-user from the data model up" principle and that you already have two real concurrent users (you + girlfriend) rather than a single local user, Postgres is the right call now rather than something to migrate to later — SQLite's single-writer model is a poor fit for a system explicitly designed around per-athlete data isolation and eventual multi-user growth.

### 3.2 Database hosting: Neon (free tier)

Free-tier Postgres hosting has consolidated hard in 2026 — Railway and Fly.io both dropped their permanent free tiers, leaving Neon and Supabase as the two realistic options. For your case specifically:
- **Neon**: serverless Postgres, scale-to-zero (you pay/use nothing while idle — relevant since a 2-person training app won't have constant traffic), free tier currently around 0.5 GB storage per project, no credit card required, and it doesn't pause after inactivity the way Supabase's does.
- **Supabase**: more generous raw storage (500 MB) but bundles in auth/storage/realtime features you don't need yet, and its free databases pause after 7 days idle — a bad fit for an app meant to be used *daily* by you but sporadically checked by your girlfriend.

**Recommendation: Neon.** Plain Postgres, nothing to migrate away from later, no idle-pause surprise.

### 3.3 Backend hosting: Render (free tier), with Fly.io as a cheap upgrade

Railway and Fly.io have both removed their meaningful free tiers in 2026 (Railway is now a one-time trial credit; Fly.io requires a card for a couple dollars a month). Render still offers a genuinely free web-service tier with no card required, but it sleeps after 15 minutes of inactivity, with a 30-60 second cold start on the next request.

**⚠️ Pushback / trade-off worth naming explicitly:** a cold start sounds bad for "the workout screen is the most important screen," but your architecture is offline-first by design — logging a set never has to touch the server in the moment. The cold start only affects *sync*, which can happily happen in the background a minute after you open the app, not the logging experience itself. Given that, I'd start on Render's free tier and only move to Fly.io (~$2/month for an always-on shared-CPU box) if the cold start turns out to bother you in practice. Your call — see the question at the end of this document.

---

## 4. Frontend

### 4.1 Framework: React vs. Svelte — this one's genuinely close, your input needed

Your original candidate was React + TypeScript. Having researched this for someone starting from zero JS/TS knowledge, I don't think that's an obvious slam-dunk anymore, so I want to lay out the real trade-off instead of just confirming your first instinct.

**React** — steeper learning curve (JSX, hooks, component lifecycle), but by far the largest ecosystem, the most tutorials and Stack Overflow answers for when you're stuck, mature offline-storage integration (Dexie ships official React hooks), and — relevant to your constitution's explicit goal of being able to "explain this system independently, including in a technical interview" — React is what most companies mean when they say "frontend experience."

**Svelte** — consistently rated as gentler for true beginners (its syntax stays close to plain HTML/CSS/JS, less boilerplate, official tutorial takes hours not days), compiles to smaller bundles which genuinely helps on mobile/PWA, but a much smaller ecosystem and roughly 20x fewer job listings in 2026 — meaning less transferable if the "explain it in an interview" goal matters to you in a general-frontend-skills sense, not just for this specific app.

I lean **React**, mainly because of the interview-relevance principle you wrote into your own constitution, and because "more tutorials exist" matters more than usual when I'm the one teaching you inline from zero. But this is a real preference call, not a technical correctness call — Svelte would work fine here too. I'd rather you pick this one than have me quietly decide it.

### 4.2 PWA installability on iOS in the EU

Worth flagging since you're both in the EU: Apple briefly threatened to break home-screen PWAs in the EU in early 2024 to sidestep Digital Markets Act browser-engine requirements, then reversed the decision two weeks later after public pressure. As of 2026 this is a closed, resolved non-issue — installed PWAs work normally on iOS in the EU, including Portugal. I mention it only because some 2024-era blog posts still circulate the outdated "broken in the EU" claim; it's not current.

One real (not political) iOS constraint remains: there's no Android-style automatic "Add to Home Screen" prompt on iOS. The user has to manually use Safari's Share button. Your girlfriend's onboarding needs a short in-app explainer for this — a small UX task to remember for the onboarding milestone, not an architecture blocker.

### 4.3 Offline storage & sync architecture

This is the constraint your brief specifically asked to be evaluated explicitly rather than assumed, so here's the real picture:

**Storage layer: Dexie.js** on top of IndexedDB. It's the standard recommendation for genuine offline-first apps in 2026 (as opposed to apps that just cache API responses) — typed tables, real queries, schema versioning, and (if you go with React) official `dexie-react-hooks` so your UI reactively re-renders whenever local data changes, whether that change came from the user or from a background sync. This becomes your single source of truth on-device; the workout screen reads and writes here directly, online or not.

**The cross-platform gap that matters:** the **Background Sync API** — the browser feature that lets a service worker retry a failed upload automatically after the tab is closed — is Chromium-only. It works on your Android/Chrome, but Safari (and therefore your girlfriend's iOS device) has never implemented it and Apple has given no indication it will. This is a real, current, well-documented gap, not something that's closing.

**⚠️ Architectural decision this forces:** don't build Background Sync as *the* sync mechanism with a same-origin fallback bolted on. Build the reverse — a **manual/triggered sync** as the actual backbone (queue every write in Dexie regardless of connectivity; attempt to flush the queue whenever the app is opened, whenever the browser fires an `online` event, and via an explicit "Sync now" affordance the user can always see and tap) — and treat Background Sync as a nice-to-have optimization *only* on Chromium browsers, layered on top, never depended on. Built this way, the app behaves identically on both your phones; Android just happens to sometimes sync a little sooner without the app being open.

**Secondary iOS-specific risk:** Safari can evict IndexedDB/cache data for a PWA that goes unused for about 7 days, and caps cache storage more aggressively than Chrome (~50MB-ish). Since the whole point of this app is daily use before the Whoop deadline, this mostly self-mitigates — but it means a real vacation or injury break is a genuine data-loss risk on iOS specifically that isn't a concern on Android. Worth a note-to-self for later (e.g., an eventual "export my data" safety valve), not something to solve now.

---

## 5. Clean Architecture — how the constitution's layering maps to folders

Sketch only (full structure comes in the first implementation milestone):

```
backend/
  domain/         ← plain Python: Athlete, Program, Mesocycle, ProgressionEngine, etc.
                     No SQLAlchemy or Pydantic imports allowed here — this is what
                     stays unit-testable without a running server or database.
  application/     ← use-cases / services that orchestrate domain logic + persistence
  api/             ← FastAPI routers + Pydantic request/response schemas
  infrastructure/  ← SQLAlchemy models, DB session handling, Alembic migrations
```

```
frontend/
  ui/              ← components (dumb, no business rules — constitution §3)
  offline/         ← Dexie schema, sync queue, "flush on reconnect" logic
  api-client/      ← typed calls to the FastAPI backend
```

---

## 6. Explicitly deferred out of this document

- **Exact progression algorithm & deload trigger rules** — this needs its own dedicated design session (inputs, rule table, edge cases per your constitution §5's testing list). Bundling it into an infrastructure/architecture document would violate your own "one coherent milestone at a time" rule, so I'm keeping it as its own upcoming milestone rather than rushing it here.
- **Exact schema-ready column choices for the Future Capabilities backlog** — belongs with the actual data-model design milestone, once we're drawing real tables.
- **Auth flow details** (session vs JWT, refresh tokens, where they live in an offline-capable frontend) — belongs to the Auth milestone; §2.3 above only fixed the hashing algorithm.

---

## 7. Confirmation needed before I update `project-brief.md`

Everything in §1 except the frontend framework and hosting budget is low-risk and I'd suggest just confirming in bulk. The two genuine judgment calls are below.
