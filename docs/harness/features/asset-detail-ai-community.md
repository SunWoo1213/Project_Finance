# Asset Detail, AI Report, And Community Feature Notes

Date: 2026-05-30

## Current Behavior

The asset detail screen combines market summary, favorite toggling, chart history, latest news/calendar context, AI report access, and the per-asset discussion area. AI reports are visible only to authenticated users. Comments can be read by anyone, but creating, editing, deleting, liking, and reporting comments require an app JWT.

Comment reports are one-per-user per comment. When a comment reaches 100 accumulated reports, the backend automatically deletes that comment.

If an authenticated user requests a report and the latest report is missing, the frontend may call report generation and then retry the report fetch. Manual report generation is authenticated-only. If the evaluator rejects the final draft after the retry loop, the backend returns a failure response and does not save the draft as a final report.

## Ownership Map

- Detail page workflow: `frontend/src/pages/AssetDetail.jsx`
- Favorite state: `frontend/src/store/favoriteStore.js`
- Report display support: `frontend/src/components/ReportCard.jsx`
- Chart support: `frontend/src/components/SparklineChart.jsx`
- Auth state dependency: `frontend/src/store/authStore.js`
- Report endpoints: `backend/app/main.py`
- Report orchestration: `backend/app/services/ai_service.py`
- LangGraph report pipeline: `backend/app/services/graph/`
- Community router: `backend/app/api/community.py`
- DB models: `backend/app/models.py`
- API schemas: `backend/app/schemas.py`

## Data Flow

1. Detail route `/detail/:ticker` loads `AssetDetail.jsx`.
2. The page fetches cached prices to find the selected ticker and asset group.
3. The page reads local favorite state and can toggle the current ticker into `favoriteAssets`.
4. The page fetches history for the selected ticker and period.
5. The page fetches `GET /api/market/latest-context/{ticker}` for ticker-specific recent news and calendar events.
6. If authenticated, the page fetches `GET /api/reports/{ticker}`.
7. If no report exists, the page can call `POST /api/ai/generate/{ticker}` and retry the report fetch.
8. Report generation merges broad cached news with latest-context news, builds structured report facts, and invokes the LangGraph workflow.
9. Structured report facts include asset-category requirements, price/source timestamps, market metadata, provider status, missing required facts, and explicit data limitations.
10. Financial, news, and macro graph nodes can pass structured provider facts from FMP, Finnhub, and CoinGecko alongside free-form research context.
11. The writer output goes through a deterministic numeric fact checker before the LLM evaluator.
12. If the fact checker finds unsupported numeric claims, it routes feedback back to the writer until the revision limit.
13. The graph evaluates fact-check-passing reports. Passing reports are saved with real bull and bear summaries derived from structured facts.
14. Failed fact checker or evaluator results raise a quality failure and are not committed to the database.
15. The page fetches comments using the ticker or asset key.
16. Community writes send the JWT and the backend resolves the asset, creating an asset row from the warm market cache when a comment is posted before a report has created one.
17. Edit/delete ownership checks happen on the backend.
18. The frontend asks the user to pick a short report reason before sending the report. The selected reason is a UI confirmation only and is not stored by the current backend contract.
19. Comment reports are stored separately from likes and can auto-delete the comment at the 100-report threshold.

## Contracts

- Detail route: `/detail/:ticker`
- Report fetch: `GET /api/reports/{ticker}` requires auth.
- Report generation: `POST /api/ai/generate/{ticker}` requires auth and may trigger LLM-backed work.
- Report generation success response includes `metadata` with `is_pass`, `feedback`, `fact_check_pass`, `fact_check_feedback`, `revision_count`, `generated_at`, `data_as_of`, `source_status`, `missing_required_facts`, and `risk_summary`.
- Report generation quality failure returns HTTP 422 and does not save an `AIReport`.
- Latest context fetch: `GET /api/market/latest-context/{ticker}` is public and TTL-cached.
- Comment list: `GET /api/community/{asset_id}/comments`
- Comment create: `POST /api/community/{asset_id}/comments`
- Comment update: `PUT /api/community/{asset_id}/comments/{comment_id}`
- Comment delete: `DELETE /api/community/{asset_id}/comments/{comment_id}`
- Like toggle: `POST /api/community/comments/{comment_id}/like`
- Report comment: `POST /api/community/comments/{comment_id}/report`

`asset_id` can currently be a numeric asset ID or ticker-like key because the backend resolver accepts both.

Comment list responses include `likes_count`, `reports_count`, and `author_nickname`.

The report reason selector in `AssetDetail.jsx` does not change the API request body; the backend currently records only the reporter/comment pair.

## Change Rules

- Do not add ordinary tests that make real LLM calls.
- Report generation behavior can increase cost; ask for confirmation before increasing automatic generation frequency or broadening triggers.
- Latest context may call free external providers; preserve ticker-level TTL caching before increasing refresh behavior.
- Keep read-only community access separate from authenticated write access.
- Ownership checks for comment edit/delete must stay server-side.
- Keep duplicate report prevention server-side.
- If report schema changes, update both backend response and markdown rendering/fallback UI.

## Verification

- Backend syntax/import check: `py -m compileall backend\app`
- For community changes, add or run backend tests around auth, asset resolution, ownership, and like toggling when feasible.
- For UI changes, run `npm run build` from `frontend/`.
- For report changes, prefer mocked or isolated service tests.

## Change Records

- `docs/harness/harness-feature-documentation.md`
- `docs/harness/google-login-only.md` affects report visibility and authenticated community writes.
- `docs/harness/latest-context-report-quality.md`
- `docs/harness/community-comment-reporting.md`
- `docs/harness/asset-favorites.md`
- `docs/harness/report-quality-improvement-plan.md`
- `docs/harness/report-quality-phase-1.md`
- `docs/harness/report-quality-phase-2.md`
- `docs/harness/report-quality-fact-checker.md`

## Open Risks

- Report generation is coupled to external APIs and LLM configuration.
- Latest news/calendar coverage depends on yfinance provider availability and may be sparse for Korean assets, bonds, and macro tickers.
- `AssetDetail.jsx` still owns several responsibilities and may need future decomposition.
- There is no migration workflow documented for report/comment schema changes.
- Existing running database instances need the backend lifespan to run again so `comment_reports` is created.
- Rich report metadata is exposed on the generation response but is not yet persisted because adding fields to `ai_reports` needs migration confirmation.
- Structured provider facts and missing required facts are used during generation but are not yet displayed or persisted as first-class report metadata.
- The current fact checker focuses on numeric support and does not yet catch unsupported qualitative claims.
