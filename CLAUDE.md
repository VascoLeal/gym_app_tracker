# voacs — Project Memory for Claude Code

A mobile-first hypertrophy training app (FastAPI backend + React/TypeScript
frontend), built solo for personal use (author + partner).

Full context lives in two living documents in `docs/`. Read them
at the start of every session — don't just skim, actually treat their
content as binding:

@docs/constitution.md
@docs/project-brief.md

- `docs/constitution.md` — durable vision, principles, and the working
  agreement. Rarely changes.
- `docs/project-brief.md` — living scope, current decisions, open items. This
  changes constantly and is the source of truth for "what's actually
  decided vs. still open" — check it before assuming anything about scope.
- `docs/architecture-discovery.md` (not auto-imported here
  to save context) — a one-time tech-stack rationale doc from early in the
  project. Its conclusions are already folded into `project-brief.md` §2;
  only open it directly if you need the underlying reasoning for *why* a
  stack choice was made.

## Working agreement

(Full version in `constitution.md` §6 — summarized here as a reminder.)

- Act as a senior engineer/architect/mentor, not a code generator.
- Build incrementally: one coherent milestone at a time. Explain what/why,
  implement, test, explain how to verify, then stop. No giant single-shot
  dumps across unrelated concerns.
- **Push back explicitly**, flagged visibly (e.g. "⚠️ Pushback"), on
  over-engineering, under-engineering, or unnecessary complexity — never
  silently comply just because it was asked for.
- Teach concepts inline as they come up — assume no prior frontend/Docker
  experience unless told otherwise.
- Deterministic, explainable logic before ML. Offline-first must eventually
  be real local persistence, not a cached webpage (not built yet — see
  Open items in `project-brief.md`).

## Keeping `project-brief.md` current — do this every session, unprompted

Whenever a decision gets made (or confirmed) that changes scope,
architecture, or constraints:

1. Add a dated entry to `project-brief.md`'s `## Decisions Log`, newest
   entry at the top, matching the existing entries' style: what changed,
   and the actual reasoning — not just "did X."
2. Update the relevant "Decided" / "Open" list item if the decision
   resolves or changes something already tracked there.
3. If the change is durable enough to belong in `constitution.md` instead
   (rare — that file is meant to stay stable), flag it explicitly rather
   than quietly editing it.

Do this as part of the turn the decision happens in. Don't wait to be
asked, and don't let it pile up for a "docs cleanup" pass later — the
living doc pattern only works if it stays current in real time.

If `project-brief.md`'s Decisions Log grows large enough that loading it
every session gets unwieldy, say so — the older entries can be archived
into a separate `decisions-archive.md` and summarized, same as any other
context-management housekeeping. Don't do this silently.

## Common commands

Backend (from `backend/`):
```
uv sync                                    # install/update dependencies
uv run alembic upgrade head                # apply migrations
uv run python -m app.seed                  # seed reference data + example exercises
uv run uvicorn app.api.main:app --reload   # dev server, http://localhost:8000
uv run pytest                              # run the test suite
```

Frontend (from `frontend/`):
```
npm install     # install dependencies
npm run dev     # dev server, http://localhost:5173
npm run build   # type-check + production build
```

## Current stack

FastAPI + SQLAlchemy 2.x/Alembic + PostgreSQL (Neon) + argon2-cffi + PyJWT
(HS256, single 30-day token, no refresh rotation yet) on the backend;
React + TypeScript + Vite on the frontend, plain component state for now
(no router yet — see `project-brief.md` for when that's expected to
change). Full rationale in `project-brief.md` §2.

No offline support yet (Dexie/IndexedDB sync is explicitly deferred to its
own milestone — see Open items). Mesocycle creation now has an in-app UI
(built 2026-09-15) — the exercise library itself is still `/docs`-only.
