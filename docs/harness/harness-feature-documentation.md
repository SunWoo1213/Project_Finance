# Harness Feature Documentation Change Record

Date: 2026-05-30

## Objective

Create a reusable documentation workflow so future harness engineering can find feature explanations, understand ownership, and record modification history in the correct place.

## Files Changed

- `AGENTS.md`
  - Added feature documentation reading and update rules.
  - Connected change records to feature documents and the feature index.
- `DEVELOPMENT_DIRECTION.md`
  - Added the root harness documentation workflow.
- `backend/DEVELOPMENT_DIRECTION.md`
  - Added backend feature documentation links.
- `backend/app/DEVELOPMENT_DIRECTION.md`
  - Added guidance for syncing app-layer changes to feature docs.
- `backend/app/api/DEVELOPMENT_DIRECTION.md`
  - Linked API work to auth, community, market, and report docs.
- `backend/app/services/DEVELOPMENT_DIRECTION.md`
  - Linked service changes to market and AI report docs.
- `frontend/DEVELOPMENT_DIRECTION.md`
  - Added frontend documentation links.
- `frontend/src/DEVELOPMENT_DIRECTION.md`
  - Added source-level documentation update rules.
- `frontend/src/pages/DEVELOPMENT_DIRECTION.md`
  - Linked route pages to feature docs.
- `frontend/src/components/DEVELOPMENT_DIRECTION.md`
  - Linked shared UI changes to shell and feature docs.
- `frontend/src/store/DEVELOPMENT_DIRECTION.md`
  - Linked auth state changes to the authentication doc.
- `frontend/src/utils/DEVELOPMENT_DIRECTION.md`
  - Linked formatter/constants changes to market data and shell docs.
- `PROJECT_FUNCTION_DETAIL_SPEC.md`
  - Added a harness note pointing future agents to the current feature docs when older product spec details conflict with current implementation.
- `docs/harness/feature-documentation-guide.md`
  - Added the feature documentation and change-record workflow.
- `docs/harness/feature-index.md`
  - Added a feature-to-file map for harness navigation.
- `docs/harness/features/authentication.md`
  - Documented current Google-only auth behavior and change rules.
- `docs/harness/features/market-data.md`
  - Documented market cache, endpoints, ticker contracts, and provider risks.
- `docs/harness/features/asset-detail-ai-community.md`
  - Documented detail page, AI report, and community data flows.
- `docs/harness/features/frontend-routing-shell.md`
  - Documented route shell, shared UI, state, and utility boundaries.

## Behavior Changes

No runtime behavior changed. This is a documentation and harness-process change only.

## Verification Performed

- `git status --short`: inspected before editing.
- Documentation was reviewed for secret-safety and linked workflow consistency.

## Commands Not Run

- Backend tests were not run because no backend runtime code changed.
- Frontend build/lint were not run because no frontend runtime code changed.

## Follow-Up Risks

- Existing product specs still contain some outdated local credential auth descriptions. Future feature work should prefer the new harness feature docs plus current code.
- If new feature areas are added, future agents must add new docs under `docs/harness/features/` and update `docs/harness/feature-index.md`.
