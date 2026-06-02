# Project Structure Analysis

Date: 2026-06-02

This document summarizes the current `Project_Finance` repository structure for future agents and maintainers. It reflects the actual files in the repository as of this date.

## Current Stack

- Frontend: React + Vite + JavaScript + Tailwind CSS + Zustand + React Router.
- Backend: FastAPI + async SQLAlchemy + Pydantic settings.
- Database: PostgreSQL for runtime, Alembic for migrations.
- AI/report workflow: LangGraph/LangChain services, scheduled stored reports, quality metadata.
- Deployment notes: Vercel-ready frontend config, backend expected to run on a persistent runtime for scheduler jobs.

## Top-Level Ownership

```text
backend/                    FastAPI backend, database models, services, tests
frontend/                   React/Vite frontend application
docs/harness/               Feature docs, change records, harness workflow docs
docker-compose.yml          Local PostgreSQL service
ARCHITECTURE.md             High-level architecture and runtime boundaries
DEVELOPMENT_DIRECTION.md    Root development rules and ownership guidance
PROJECT_FUNCTION_DETAIL_SPEC.md
test_api.py, test_db.py     Root helper scripts
```

## Backend Breakdown

```text
backend/app/api/            API routers and auth/entitlement dependencies
backend/app/core/           Runtime settings, security helpers, market cache
backend/app/db/             SQLAlchemy Base, async engine, session dependency
backend/app/services/       Business logic and external integrations
backend/app/services/graph/ LangGraph report generation workflow
backend/app/main.py         FastAPI app, CORS, lifespan, scheduler, market/report endpoints
backend/app/models.py       ORM tables
backend/app/schemas.py      Pydantic contracts
backend/alembic/            Migration config and revisions
backend/tests/              Backend test suite
```

Important boundaries:

- Add API routes under `backend/app/api/` unless the change is specifically maintaining the existing market/report routes in `main.py`.
- Keep external API calls, data normalization, report generation, and payment processing inside `backend/app/services/`.
- Keep settings in `backend/app/core/config.py`; document variable names only, never secret values.
- Represent production-like DB schema changes with Alembic revisions.

## Frontend Breakdown

```text
frontend/src/pages/         Route-level screens
frontend/src/components/    Shared UI and feature components
frontend/src/components/ui/ Small reusable UI primitives
frontend/src/store/         Zustand stores
frontend/src/utils/         API client, constants, formatters, category metadata
frontend/src/assets/        Imported static assets
frontend/public/            Public static assets
frontend/src/App.jsx        Route map and application shell
frontend/src/main.jsx       React entrypoint
```

Current route ownership:

| Route | Owner |
| --- | --- |
| `/` | `frontend/src/pages/Home.jsx` |
| `/category/:type` | `frontend/src/pages/CategoryView.jsx` |
| `/market/:ticker` | `frontend/src/pages/MarketSnapshot.jsx` |
| `/detail/:ticker` | `frontend/src/pages/AssetDetail.jsx` |
| `/login` | `frontend/src/pages/Login.jsx` |
| `/pricing` | `frontend/src/pages/Pricing.jsx` |
| `/billing/success` | `frontend/src/pages/BillingSuccess.jsx` |
| `/billing/cancel` | `frontend/src/pages/BillingCancel.jsx` |

## Feature Documentation Index

Use `docs/harness/feature-index.md` before changing feature behavior. The current feature documents cover:

- authentication and Google login.
- subscription billing and entitlements.
- market data, prices, news, and history.
- asset detail, AI reports, and community comments.
- frontend routing, shell, shared UI, and shared state.
- asset favorites.
- chatbot assistant.
- deployment and hosted runtime.

## Known Documentation Notes

- `ARCHITECTURE.md` has been refreshed to match the current React/Vite + FastAPI implementation.
- `PROJECT_STRUCTURE_ANALYSIS.md` is a concise structure map, while `ARCHITECTURE.md` explains runtime boundaries and data flow.
- Some older Korean comments or docs may display mojibake in certain terminals. Treat current source behavior as authoritative and update stale documentation when it affects the task.
- Local runtime configuration must not expose secrets. If a committed file contains real credentials, rotate them and move the values into environment variables.
