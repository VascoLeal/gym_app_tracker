# Project Constitution

*Last updated: 2026-08-29 (domain hierarchy corrected to drop the Program layer — see project-brief.md decisions log). This document rarely changes — it captures durable vision and principles, not current scope or tech decisions. Scope, constraints, and decisions live in `project-brief.md`.*

## 1. What This Is

A mobile-first workout and hypertrophy training application, inspired by (not copying) apps like RP Hypertrophy, built primarily as a personal tool for the author and his girlfriend, architected so it could later support more users without a rewrite.

The core differentiator: this is **not** a workout logger. It is an intelligent training system that prescribes workouts, records what actually happened, compares expected vs. actual, and uses that history to recommend future weight/reps/sets — deterministically and explainably.

## 2. Domain Hierarchy (conceptual, not final schema)

Athlete → Mesocycle → Week → Workout Template → Exercise Prescription → Set Prescription / Set Performance, plus a standalone Exercise Library, Exercise History, Performance History, and (future) Muscle Volume and health/recovery data.

Explicitly distinguish, throughout the system:

- An exercise in the library vs. an exercise in a workout template vs. an exercise prescribed inside a real program vs. an exercise actually performed vs. a historical performance record.
- A planned set vs. an executed set vs. a modified set vs. an automatically generated recommendation.

These are different concepts with different lifecycles and must not be collapsed into one table/class out of convenience.

## 3. Non-Negotiable Principles

**Recommendation engine**
- Deterministic and explainable first. No ML until there's a demonstrated need rules/statistics genuinely can't meet.
- Every recommendation states *why* in plain language (e.g. "increased load because you hit the top of the rep range at target RIR on all sets"), not just a number.
- Progression/deload logic is independently testable — `recommend_next_set(...)` runs and is unit-tested without a web server.

**Offline-first, for real**
- Logging a workout works with zero connectivity, using genuine local persistence — not a cached webpage.
- Sync, conflict handling, retry, and local/synced state tracking are core architecture, not an afterthought.

**Mobile-first UX**
- The workout screen is the most important screen in the app. It stays fast and usable when the user is tired, sweaty, distracted, or in bad lighting: minimal typing, large touch targets, dark UI, sensible defaults, few taps.
- Every working set distinguishes: what was prescribed, what was performed, how hard it was, and any deviation.

**Data model must not assume the obvious**
- Set types are heterogeneous (a drop set has multiple load/rep segments; a myo-rep set has an activation set + mini-sets). New set types must be addable without a redesign.
- Muscles are granular (e.g. upper chest ≠ chest, rear delts ≠ lateral delts) to support future contribution-weighting.
- Training structure (frequency, split, rep ranges, RIR targets) is athlete-specific and configurable — never hardcoded to one person's program.

**Multi-user from the data model up**
- Even with ~2 current users, every table/entity belongs to an athlete. No shortcuts that assume a single global user.
- Full commercial multi-tenant SaaS features (coach dashboards, sharing, billing) are explicitly **not** built until asked for — only the data model needs to not preclude them.

**Clean architecture**
- UI → API/application layer → domain/business logic → persistence → database. Domain logic (especially the progression engine) stays independent of HTTP and UI code and is unit-testable in isolation.
- Frontend never contains training-science business rules.

**Extensibility without premature building** *(decided 2026-08-25)*
- Ideas from the Future Capabilities backlog get **schema-ready** treatment only where cheap (don't design in a way that blocks adding them later) — never UI or business logic, until explicitly requested in a session.

## 4. Fitness-Science Honesty

When making training-science decisions (RIR, volume, progression, deloads, fatigue), always distinguish:

- Established evidence
- Reasonable interpretation of evidence
- Practical heuristic
- Personal preference
- Algorithmic design decision (a modeling choice, not a physical fact)

Never present a derived measure (e.g. "effective sets") as an objectively measured quantity — it's a model. Never phrase output as medical or guaranteed truth.

## 5. Engineering Standards

**Use:** type hints, Pydantic where appropriate, clear domain models, explicit dependency management, automated tests, linting/formatting/static analysis, meaningful error handling, env-var configuration, secret management, database migrations from day one, Git with meaningful commits and no secrets committed.

**Avoid:** giant files, global mutable state, hardcoded config, duplicated business logic, magic constants, hidden side effects, unnecessary abstraction, premature microservices, premature ML, unnecessary cloud infrastructure, async complexity for its own sake.

**Security baseline (even early):** proper password hashing via a mature library, real session/token auth, per-user data isolation enforced at the query level, input validation, no SQL injection surface, HTTPS, secure cookies/tokens, sane CORS, backups, an account deletion path.

**Testing** is written alongside implementation, not after — especially for the progression engine, which needs realistic edge-case coverage (hit top of range at target RIR, missed reps, exceeded RIR, partial reps, skipped workouts, exercise swaps, added/removed sets, partial workout completion, etc.).

## 6. Working Agreement

- Act as senior engineer/architect/mentor, not a code generator.
- Build incrementally: one coherent milestone at a time — explain what/why, what to learn, directory structure, implement, explain the code, add tests, explain how to run/verify, note common mistakes, then move on. No giant single-shot dumps.
- Teach concepts inline as they come up (ORM, Docker, React/PWA concepts, etc.) — assume no prior web/frontend/Docker experience.
- **Push back explicitly.** Call out over-engineering, under-engineering, unnecessary complexity, or a simpler alternative — flagged visibly (e.g. "⚠️ Pushback") rather than silently complying.
- Prioritize a working, understandable system over a theoretically perfect one. Goal: the author can maintain, extend, and explain this system independently — including in a technical interview.
- Sequence always: fast workout logging → accurate history → useful recommendations → better analytics → advanced coaching. Never build dashboards/social/analytics ahead of a solid core loop.

## 7. Document Map

- `constitution.md` (this file) — durable vision & principles. Rarely changes.
- `project-brief.md` — living document: current constraints, MVP scope (decided/deferred/open), Future Capabilities backlog, dated decision log. Check this for current project state at the start of a session.
