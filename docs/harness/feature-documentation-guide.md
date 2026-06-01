# Harness Feature Documentation Guide

Date: 2026-05-30

This guide defines how future harness engineering work should document feature behavior and record changes in `Project_Finance`.

## Purpose

Harness agents should be able to open the repository, read the feature documentation, and understand three things before editing:

1. What user-facing behavior the feature owns.
2. Which frontend, backend, database, service, and configuration files are involved.
3. What previous harness changes altered the feature and what risks remain.

The source of truth is still the current code. When documentation and implementation disagree, inspect the implementation first, then update the documentation as part of the change.

## Required Reading Order

Before modifying a feature, read these in order:

1. `AGENTS.md`
2. Root `DEVELOPMENT_DIRECTION.md`
3. The nearest folder-level `DEVELOPMENT_DIRECTION.md` for every touched area
4. `docs/harness/feature-index.md`
5. The feature document under `docs/harness/features/`
6. Any linked change records under `docs/harness/`

If a feature does not have a document yet, create one before or during the change.

## Feature Document Location

Feature-level documentation belongs under:

```text
docs/harness/features/
```

Use one file per functional area:

- `authentication.md`
- `market-data.md`
- `asset-detail-ai-community.md`
- `frontend-routing-shell.md`

If a feature grows large enough to split, create a more focused file and add it to `docs/harness/feature-index.md`.

## Required Feature Document Sections

Each feature document should include:

- `Current Behavior`: user-visible behavior and important edge cases.
- `Ownership Map`: files that own the route, UI, state, service, model, schema, and configuration.
- `Data Flow`: frontend-to-backend, service, cache, DB, and external API flow.
- `Contracts`: API paths, request/response expectations, stored fields, and auth requirements.
- `Change Rules`: constraints future agents should respect.
- `Verification`: smallest meaningful commands or checks for this feature.
- `Change Records`: links to historical records under `docs/harness/`.
- `Open Risks`: known gaps, migration needs, flaky dependencies, or follow-up work.

Do not include secrets, raw environment values, tokens, passwords, or private account data.

## Report Generation Documentation Rule

For AI report generation and report retrieval, documentation is mandatory before the work is considered complete. Any audit, plan, or implementation touching scheduler cadence, scheduler coverage, report cooldowns, manual generation endpoints, asset detail report loading, or chatbot report responses must:

- Record the current behavior and target behavior under `docs/harness/`.
- Link the record from `docs/harness/features/asset-detail-ai-community.md`.
- Link chatbot-specific report behavior from `docs/harness/features/chatbot-assistant.md` when applicable.
- Link scheduler or market-cache coverage behavior from `docs/harness/features/market-data.md` when applicable.
- State explicitly whether user-facing requests can trigger generation. The target rule is that users and the chatbot read stored scheduled reports only.

## Change Record Rules

Every meaningful harness change should create or update a Markdown record under `docs/harness/`.

Write harness reports, verification summaries, implementation reports, plans, and change records in Korean by default unless the user explicitly requests another language. Keep code identifiers, file paths, commands, API paths, and error strings in their original form.

The record should include:

- Date
- Objective
- Files changed
- Behavior changes
- Verification performed
- Commands not run and why
- Follow-up risks
- Links back to the affected feature documents

Small documentation-only edits may share one record if they belong to the same objective.

## Linking Rules

When a feature changes:

1. Update the relevant feature document.
2. Add the change record link in that feature document.
3. Add or update the feature entry in `docs/harness/feature-index.md`.
4. If a new folder or ownership boundary is involved, update the nearest `DEVELOPMENT_DIRECTION.md`.
5. Keep `AGENTS.md` aligned with this workflow.

## Safety Notes

- Do not inspect `.env` just to document configuration. Document variable names only.
- Treat `ARCHITECTURE.md` and older specs as background, not authority, when they conflict with current React Vite or FastAPI code.
- Do not rewrite unrelated feature docs while changing one feature.
- Do not silently delete old change records. If a record is obsolete, add a note explaining what superseded it.
