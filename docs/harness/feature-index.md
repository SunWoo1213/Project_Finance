# Harness Feature Index

Date: 2026-05-30

This index tells future harness agents which feature document to read before changing a functional area. The current implementation is the final source of truth; update this index whenever a feature boundary or ownership map changes.

## Documentation Workflow

- Documentation guide: `docs/harness/feature-documentation-guide.md`
- Feature docs: `docs/harness/features/`
- Change records: `docs/harness/`
- Existing detailed product spec: `PROJECT_FUNCTION_DETAIL_SPEC.md`

Read the feature doc first, then inspect the current code paths listed in its ownership map.

## Feature Map

| Feature | Read first | Primary frontend files | Primary backend files | Change records |
| --- | --- | --- | --- | --- |
| Authentication and Google login | `docs/harness/features/authentication.md` | `frontend/src/pages/Login.jsx`, `frontend/src/store/authStore.js`, `frontend/src/components/Header.jsx`, `frontend/src/App.jsx` | `backend/app/api/auth.py`, `backend/app/api/deps.py`, `backend/app/core/config.py`, `backend/app/core/security.py`, `backend/app/models.py`, `backend/app/schemas.py` | `docs/harness/harness-feature-documentation.md`, `docs/harness/google-login-only.md`, `docs/harness/community-comment-reporting.md` |
| Market data, prices, news, history | `docs/harness/features/market-data.md` | `frontend/src/pages/Home.jsx`, `frontend/src/pages/MarketSnapshot.jsx`, `frontend/src/pages/CategoryView.jsx`, `frontend/src/pages/AssetDetail.jsx`, `frontend/src/utils/constants.js`, `frontend/src/utils/formatters.js` | `backend/app/main.py`, `backend/app/core/cache.py`, `backend/app/services/market_service.py`, `backend/app/services/macro_service.py` | `docs/harness/harness-feature-documentation.md`, `docs/harness/latest-context-report-quality.md`, `docs/harness/main-market-snapshot-and-news.md` |
| Asset detail, AI report, community | `docs/harness/features/asset-detail-ai-community.md` | `frontend/src/pages/AssetDetail.jsx`, `frontend/src/components/ReportCard.jsx`, `frontend/src/components/SparklineChart.jsx` | `backend/app/main.py`, `backend/app/api/community.py`, `backend/app/services/ai_service.py`, `backend/app/services/graph/`, `backend/app/models.py`, `backend/app/schemas.py` | `docs/harness/harness-feature-documentation.md`, `docs/harness/latest-context-report-quality.md`, `docs/harness/google-login-only.md` for auth-dependent behavior, `docs/harness/community-comment-reporting.md` |
| Frontend routing, shell, shared UI/state | `docs/harness/features/frontend-routing-shell.md` | `frontend/src/App.jsx`, `frontend/src/pages/MarketSnapshot.jsx`, `frontend/src/components/Header.jsx`, `frontend/src/components/`, `frontend/src/store/`, `frontend/src/utils/` | Auth and API contracts as needed | `docs/harness/harness-feature-documentation.md`, `docs/harness/google-login-only.md` for removed register route, `docs/harness/main-market-snapshot-and-news.md` |
| Asset favorites | `docs/harness/features/favorites.md` | `frontend/src/store/favoriteStore.js`, `frontend/src/pages/CategoryView.jsx`, `frontend/src/pages/AssetDetail.jsx` | None currently; browser-local localStorage state | `docs/harness/asset-favorites.md` |

All feature documentation was introduced and linked by `docs/harness/harness-feature-documentation.md`.

## When To Add A Feature Doc

Add a new file under `docs/harness/features/` when a change introduces a new user workflow, route group, backend service area, external integration, or cross-cutting state model.

Update this index in the same change so future harness work can find the document without searching the whole repository.
