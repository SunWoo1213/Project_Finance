# Community Comment Reporting

Date: 2026-05-30

## Objective

Restore authenticated community comment create/edit/delete behavior and add comment reporting with automatic deletion after 100 unique reports.

## Files Changed

- `backend/app/api/auth.py`
- `backend/app/api/community.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/store/authStore.js`
- `frontend/tailwind.config.js`
- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/authentication.md`
- `docs/harness/feature-index.md`
- `docs/harness/community-comment-reporting.md`

## Behavior Changes

- Google login responses now include the authenticated user's numeric `id`.
- The frontend stores that id and can recover it from the JWT for older localStorage user objects.
- Asset detail compares the stored user id with each comment's `user_id`, so owner-only edit/delete controls can appear.
- Comment creation can create the target `assets` row from the warmed market price cache when the asset exists in the UI but has not yet been created by AI report generation.
- `comment_reports` stores one report per user per comment.
- `POST /api/community/comments/{comment_id}/report` records a report, rejects self-reports, returns duplicate-report status without incrementing, and deletes the comment when the unique report count reaches 100.
- The frontend now opens a small report-reason selector before submitting. The reason is not persisted; after the user clicks a reason, the UI only shows `신고가 접수되었습니다.` on success.
- Comment responses include `reports_count`.

## Verification Performed

- `py -m compileall backend\app` passed.
- `npm.cmd run lint` passed from `frontend/`.
- `npm.cmd run build` passed from `frontend/`. Vite reported the existing large chunk warning.
- After adding the report-reason selector, `npm.cmd run lint` and `npm.cmd run build` were rerun and passed. Vite still reported the large chunk warning.

## Commands Not Run And Why

- `npm run build` via PowerShell was not used because `npm.ps1` is blocked by the local execution policy. `npm.cmd run build` was used instead.
- No real Google login, LLM report generation, or external market-data calls were run for this code-level verification.

## Follow-Up Risks

- Existing running backend processes must restart so `Base.metadata.create_all` can create the new `comment_reports` table.
- This repository still lacks Alembic migrations; production databases need an explicit migration plan before deployment.
- Community behavior currently depends on the market price cache being warmed before a first comment can create a missing asset row.

## Feature Docs

- `docs/harness/features/asset-detail-ai-community.md`
- `docs/harness/features/authentication.md`
