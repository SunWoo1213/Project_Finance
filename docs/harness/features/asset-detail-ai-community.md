# Asset Detail, AI Report, And Community Feature Notes

Date: 2026-05-30

## Current Behavior

The asset detail screen combines market summary, favorite toggling, chart history, latest news/calendar context, AI report access, and the per-asset discussion area. AI reports are visible only to users with report entitlement and render through `ReportCard.jsx`, including bull/bear summaries plus the final Markdown report. Comments can be read by anyone, but creating, editing, deleting, liking, and reporting comments require an app JWT.

Comment reports are one-per-user per comment. When a comment reaches 100 accumulated reports, the backend automatically deletes that comment.

If an authenticated user requests a report and the latest report is missing, the frontend now shows a scheduled-report-pending state and does not call report generation. Manual report generation is disabled for ordinary authenticated users. This aligns with the target product rule documented in `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md` and implemented in `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`: user-facing report views read only pre-generated stored reports, while generation runs from the backend scheduler.

AI report generation is now additionally controlled by backend-only `ENABLE_AI_REPORT_GENERATION`. When it is `false`, scheduled report jobs are not registered and service-level report generation returns before opening a DB session or invoking providers/LLM workflow. Stored report reads remain available.

## Ownership Map

- Detail page workflow: `frontend/src/pages/AssetDetail.jsx`
- Favorite state: `frontend/src/store/favoriteStore.js`
- Report display support: `frontend/src/components/ReportCard.jsx`
- Chart support: `frontend/src/components/SparklineChart.jsx`
- Auth state dependency: `frontend/src/store/authStore.js`
- Report endpoints: `backend/app/main.py`
- Chatbot report/community guidance: `backend/app/api/chat.py`, `backend/app/services/chat_service.py`
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
6. If authenticated and entitled, the page fetches `GET /api/reports/{ticker}`. Current tier behavior is Free: no report access, Plus: report access, Pro: report access.
7. If no stored report exists, the page displays a scheduled-report-pending state and does not call `POST /api/ai/generate/{ticker}`.
8. Report generation merges broad cached news with latest-context news and builds structured report facts before deciding whether to invoke the LangGraph workflow.
9. Structured report facts include asset-category requirements, an auditable fact matrix, asset-specific analysis frameworks, price/source timestamps, market metadata, provider status, missing required facts, and explicit data limitations.
10. A deterministic readiness grade marks the report `ready`, `limited`, or `blocked` from the fact matrix. Blocked reports do not call the LangGraph/LLM pipeline.
11. Financial, news, and macro graph nodes can pass structured provider facts from FMP, Finnhub, and CoinGecko alongside free-form research context.
12. After synthesis, deterministic Bull, Bear, and Risk role nodes split `structured_facts` into `bull_thesis`, `bear_thesis`, and `risk_review` without adding extra LLM calls.
13. A deterministic research packet is assembled from structured facts, Bull/Bear role outputs, Risk review output, source-table entries, data limitations, catalysts, and watchlist items before the writer runs.
14. The writer consumes the research packet, separated role outputs, and the selected asset analysis framework before finalizing the Markdown report. It is also given an `allowed_numbers` whitelist of raw numeric tokens derived from the same fact sources the numeric fact checker uses, so the first draft avoids unsupported numbers; numbers outside the whitelist (plus integers 0-10 and years) must be replaced with qualitative wording or a data-limitation note rather than invented. The whitelist is capped by `ALLOWED_NUMBERS_LIMIT` (150), raised to stay aligned with the fact checker's unbounded supported set so data-rich assets are not under-informed.
15. The writer output goes through a deterministic fixed-format validator that checks for the 10 required Markdown section headings and requires asset-framework topic coverage inside the `자산군별 분석` section with supporting evidence or data-limit text.
16. Format-passing output then goes through a deterministic numeric fact checker. Numeric matching is sign-insensitive (absolute-value normalization), so a magnitude present in the facts (for example a `change_pct` of `-3.62`) is accepted even when the writer expresses direction in words (`3.62% 하락`); increase/decrease direction correctness is left to the evaluator and qualitative checks, not the numeric gate.
17. Numeric-passing output goes through a deterministic qualitative claim checker for narrow high-risk claims such as unsupported regulatory, ETF, institutional-flow, policy-shift, earnings, supply, or on-chain statements.
18. If the format validator, numeric fact checker, or qualitative checker fails, it routes feedback back to the writer until the revision limit, which is `settings.REPORT_MAX_REVISIONS` (default 7). Reaching the limit routes the graph to END (then the numeric sanitization fallback in step 20 is attempted).
19. The graph evaluates format-, numeric-, and qualitative-check-passing reports. Passing reports are saved with bull and bear summaries derived from role outputs when available.
20. Failed format checker, fact checker, qualitative checker, or evaluator results raise a quality failure and are not committed to the database. As a single exception, when the revision loop is exhausted and the only failing gate is the numeric fact checker (format already passed), `generate_report_for_ticker` deterministically sanitizes the unsupported numeric tokens (replacing them with a `(수치 미확인)` placeholder, no LLM re-call) and re-runs the format, framework, numeric, and qualitative gates; only if all gates then pass is the sanitized report saved (`metadata_json.fallback_sanitized=true` with `sanitized_numbers`). If sanitization still does not pass, the report is not saved (404 preserved).
21. Scheduled report generation runs only when both `ENABLE_SCHEDULER=true` and `ENABLE_AI_REPORT_GENERATION=true`.
22. Scheduled report generation seeds and covers only the configured representative target list by default: `DGS10`, `XAU`, `BTC-USD`, `NVDA`, and `005930.KS`.
23. The startup scheduled report job is delayed by `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS` so market warm-up and provider queues can begin before the first report attempt. If a scheduled report still starts before market warm-up has populated the target ticker, `generate_report_for_ticker()` asks `market_service.ensure_price_cache_for_ticker()` to fill that ticker's price cache once, then rechecks the cache before building report facts. For US stock targets such as `NVDA`, successful Finnhub quote data can still populate the cache even when optional profile or Stooq history calls fail. This is a scheduler/background safeguard only; user-facing report pages and chatbot requests still do not trigger report generation.
24. Stooq-backed market facts (US index, commodity, US stock history, USD/KRW history/change) degrade through stale cache when available. USD/KRW keeps the open.er-api.com current rate even if Stooq history times out. This improves report fact availability but does not create a user-facing report generation trigger.
25. Passing reports persist quality/source metadata, fact matrix summaries, source-table entries, and research packet metadata on `AIReport`, and existing report fetches return the stored metadata to `ReportCard.jsx`.
26. The page fetches comments using the ticker or asset key.
27. Community writes send the JWT and the backend resolves the asset, creating an asset row from the warm market cache when a comment is posted before a report has created one.
28. Edit/delete ownership checks happen on the backend.
29. The frontend asks the user to pick a short report reason before sending the report. The selected reason is a UI confirmation only and is not stored by the current backend contract.
30. Comment reports are stored separately from likes and can auto-delete the comment at the 100-report threshold.
31. The chatbot can guide users to detail, report, and community areas. For authenticated users it can summarize an already stored report, but it does not call the report-generation endpoint.

## Contracts

- Detail route: `/detail/:ticker`
- Report fetch: `GET /api/reports/{ticker}` requires active Plus or Pro entitlement.
- Report generation: `POST /api/ai/generate/{ticker}` requires auth but is disabled for ordinary users with HTTP 403; LLM-backed generation is scheduled-only.
- Report fetch responses include persisted `metadata` when available.
- Report generation success response includes `metadata` with `quality_status`, `is_pass`, `feedback`, `format_check_pass`, `format_check_feedback`, `fact_check_pass`, `fact_check_feedback`, `qualitative_check_pass`, `qualitative_check_feedback`, `revision_count`, `generated_at`, `data_as_of`, `source_status`, `missing_required_facts`, `fact_matrix`, `fact_matrix_summary`, `readiness`, `critic_mode`, `llm_report_critics_enabled`, `research_packet`, `source_table`, and `risk_summary`.
- Report generation metadata also includes `role_outputs` with `bull_thesis`, `bear_thesis`, and `risk_review` for newly generated reports.
- Report generation metadata also includes `analysis_framework`, which identifies the asset-category framework used by the writer.
- Report readiness blocked and report quality failure responses return HTTP 422 and do not save an `AIReport`.
- Persisted `AIReport` quality columns include `quality_status`, `quality_feedback`, `format_check_pass`, `fact_check_pass`, `qualitative_check_pass`, `revision_count`, `data_as_of`, `source_summary`, `risk_summary`, `analysis_framework`, and `metadata_json`.
- FastAPI lifespan attempts `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for local bootstrap only when `ENABLE_DB_SCHEMA_BOOTSTRAP=true`. Production-like deployments should set that flag to `false` and rely on Alembic migration coverage for report metadata columns.
- Optional structured provider environment variable names for report-quality context: `FMP_API_KEY`, `FINNHUB_API_KEY`. They are optional; missing values produce provider limitation metadata rather than blocking report generation.
- Optional report runtime policy variables: `ENABLE_AI_REPORT_GENERATION`, `ENABLE_LLM_REPORT_CRITICS`, `REPORT_CRITIC_MODE`, `REPORT_MAX_REVISIONS` (writer retry limit, default 7), `REPORT_SCHEDULER_COVERAGE`, `REPORT_SCHEDULER_INTERVAL_HOURS`, `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`, `REPORT_SCHEDULER_MAX_REPORTS_PER_RUN`, `REPORT_SCHEDULER_ASSET_COOLDOWN_HOURS`, and `REPORT_SCHEDULER_TARGET_TICKERS`.
- Latest context fetch: `GET /api/market/latest-context/{ticker}` is public and TTL-cached.
- Comment list: `GET /api/community/{asset_id}/comments`
- Chat guidance: `POST /api/chat/message`
- Comment create: `POST /api/community/{asset_id}/comments`
- Comment create requires `users.nickname_confirmed_at`; unconfirmed users receive HTTP 403 with `NICKNAME_REQUIRED`.
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
- User-facing report views should read stored `AIReport` rows only. Do not make page load, button click, or chatbot request paths trigger report generation.
- Any audit, plan, or implementation touching report generation cadence, report viewing, manual generation, or chatbot report responses must add/update a `docs/harness/` record and link it here.
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
- `docs/harness/report-quality-role-nodes.md`
- `docs/harness/report-quality-asset-frameworks.md`
- `docs/harness/report-quality-format-validator.md`
- `docs/harness/report-quality-framework-format-validation.md`
- `docs/harness/feature-implementation-fixes-2026-05-31.md`
- `docs/harness/feature-implementation-fixes-verification-2026-05-31.md`
- `docs/harness/report-quality-heading-validator-and-neutral-badge.md`
- `docs/harness/report-quality-follow-up-plan-2026-05-31.md`
- `docs/harness/report-quality-follow-up-implementation-2026-05-31.md`
- `docs/harness/chatbot-feature-implementation-2026-05-31.md`
- `docs/harness/report-generation-schedule-alignment-plan-2026-06-01.md`
- `docs/harness/report-generation-schedule-alignment-implementation-2026-06-01.md`
- `docs/harness/report-writing-method-feedback-2026-06-01.md`
- `docs/harness/report-writing-method-implementation-plan-2026-06-01.md`
- `docs/harness/report-writing-method-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-feedback-implementation-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-plan-2026-06-01.md`
- `docs/harness/subscription-tier-payment-provider-db-implementation-2026-06-01.md`
- `docs/harness/vercel-supabase-deployment-implementation-2026-06-01.md`
- `docs/harness/mypage-profile-implementation-2026-06-02.md`
- `docs/harness/project-gap-remediation-plan-2026-06-02.md`
- `docs/harness/project-defect-remediation-plan-2026-06-02.md`
- `docs/harness/report-scheduler-structured-output-error-fix-2026-06-02.md`
- `docs/harness/report-generation-env-switch-plan-2026-06-03.md`
- `docs/harness/report-generation-env-switch-implementation-2026-06-03.md`
- `docs/harness/report-scheduler-market-cache-miss-fallback-2026-06-04.md`
- `docs/harness/report-404-and-secret-log-leak-remediation-plan-2026-06-04.md`
- `docs/harness/report-404-and-secret-log-leak-remediation-implementation-2026-06-04.md`
- `docs/harness/nvda-report-factchecker-loop-root-cause-2026-06-04.md`
- `docs/harness/nvda-factchecker-loop-404-remediation-plan-2026-06-04.md`
- `docs/harness/nvda-factchecker-loop-404-remediation-implementation-2026-06-04.md`
- `docs/harness/report-max-revisions-increase-to-7-2026-06-04.md`
- `docs/harness/report-generation-deployment-failure-remediation-plan-2026-06-07.md`
- `docs/harness/render-standard-market-provider-timeout-remediation-2026-06-07.md`
- `docs/harness/stooq-timeout-fallback-2026-06-07.md`
- `docs/harness/demo-free-tier-data-cadence-plan-2026-06-08.md`
- `docs/harness/data-io-pipeline-remediation-plan-2026-06-08.md`

## Open Risks

- Report generation is coupled to external APIs and LLM configuration.
- Latest news/calendar coverage depends on Finnhub, Naver news, and provider-specific cache/cooldown behavior; Korean events, bonds, and macro tickers may still be sparse.
- `AssetDetail.jsx` still owns several responsibilities and may need future decomposition.
- Report metadata columns now have Alembic baseline coverage, but existing hosted databases still need `python -m alembic upgrade head` before running with `ENABLE_DB_SCHEMA_BOOTSTRAP=false`.
- Existing running database instances need the backend lifespan to run again so `comment_reports` is created.
- Structured provider facts are summarized in persisted metadata, but raw provider payloads are still not persisted as first-class rows.
- The qualitative checker is intentionally narrow and deterministic; it catches selected high-risk unsupported claims but is not a full claim-evidence verifier.
- Bull, Bear, and Risk role outputs are deterministic graph state for now; fully independent LLM-backed debate agents would increase token cost and need explicit approval.
- Asset-specific framework depth validation is deterministic and conservative; it checks section placement and minimal evidence/limitation text, not full analytical quality.
- Broadening scheduled AI report generation beyond the five representative target tickers remains disabled because it would increase LLM call volume.
- Startup scheduled report generation is delayed by `REPORT_SCHEDULER_STARTUP_DELAY_SECONDS`, but can still encounter missing provider keys or slow providers. A ticker-level market cache fill handles warm-up race conditions, and US stock snapshots keep primary Finnhub quote data when optional profile/Stooq history calls fail. Primary provider failures still lead to readiness-blocked reports instead of fabricated data.
- Detail pages no longer trigger manual report generation on 404, so unsupported or not-yet-generated assets can show a pending report state until the scheduler produces a stored report.
- Free users and users without loaded report entitlement now see a paywall and should not trigger report fetches from the detail page.
- Remaining report-quality follow-ups are prioritized in `docs/harness/report-quality-follow-up-plan-2026-05-31.md`.
