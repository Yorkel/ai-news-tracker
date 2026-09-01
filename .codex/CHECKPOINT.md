# Repository checkpoint

Last updated: 2026-09-01T14:23:36+0100
Repository: `/Users/qtnzlyo/GitHub/ai-news-tracker`
Status: active

## Repository state

- Branch: `main`
- Commit: `617f764`
- Working tree: clean before this checkpoint update; local `main` matches `origin/main`.
- Relevant session IDs: `01a05cd2-b581-77e2-83d1-5271861a91b6`

## Last completed

- Diagnosed the current Streamlit Cloud `ModuleNotFoundError`: `DATABASE_URL` selects `src.scraping.pg_client.PgClient`, which imports `psycopg`, but Cloud's app-adjacent `dashboard/requirements.txt` omits `psycopg[binary]`. The package appears only in root `requirements.txt`.
- Corrected the portfolio audit scope to the GitHub repository itself: code organisation, documentation, reproducibility, tests, security, Git history, and public readiness.
- Provisional repository portfolio rating: 6.5/10. The engineering is substantial, but stale template documentation, absent project-specific evaluation artefacts, failing lint, placeholder files, and repository-history hygiene materially weaken the presentation.

## Deliverables and changed files

- `.codex/CHECKPOINT.md` — continuity checkpoint updated with the deployment diagnosis; the file is currently tracked in repository history.
- No website, application, configuration, data, deployment, commit, or remote changes were made.

## Decisions confirmed

- 2026-09-01: user requested an audit, rating, and recommended changes; no implementation was requested or authorised.
- 2026-09-01: user clarified that “portfolio piece” means assessment of the repository, not the deployed dashboard.

## Validation

- Verified the failing import chain at `dashboard/data.py:85-88` and `src/scraping/pg_client.py:36-37`.
- Verified `dashboard/requirements.txt` lacks `psycopg`, while root `requirements.txt:22` pins `psycopg[binary]==3.3.4`; local system Python also reproduces `ModuleNotFoundError: No module named 'psycopg'`.
- Rendered the password gate and authenticated first dashboard screen at 1440px and 390px widths using the current local app and configured database.
- `python -m pytest tests/ -q`: 47 passed.
- `ruff check .`: failed with 25 unused-import findings.
- Verified current scope: 125 configured source entries, 124 enabled, 121 approved domains, 7 streams, and 6 category labels.
- Verified a misleading pipeline metric: `dashboard/app.py` adds unclassified and blank-summary counts, double-counting articles missing both.
- Verified README/config documentation is stale relative to the live implementation and scheduled workflows.
- Verified `origin/main` contains five public commits, including the non-descriptive commit `d`; local `main` is on a separate duplicate-looking five-commit chain plus the checkpoint commit.
- Verified project-specific model/data governance artefacts are absent: the repository ships generic templates and template-language guidance rather than completed model card, datasheet, evaluation report, or threat model.

## Currently active

- Reporting the Streamlit Cloud dependency diagnosis; no fix has been authorised.

## Not done

- No dependency, application, deployment, commit, or remote change has been made for the Cloud failure.
- No README rewrite, history reconciliation, lint cleanup, template removal, reproducibility fixture, or project-specific evaluation documentation has been implemented.

## Blockers and unresolved questions

- Restoring the Cloud app requires a dependency-source change and redeployment; the smallest fix is to add `psycopg[binary]==3.3.4` to `dashboard/requirements.txt`, subject to user approval.
- The checkpoint contains prior private workflow notes but is currently tracked and present on `origin/main`; whether to privatise it is unresolved.
- Repo-local `PROJECT_CONTEXT.md` and `AGENTS.md` are absent; creating them requires user approval.

## Exact next action

1. If the user authorises the fix, add the existing root pin `psycopg[binary]==3.3.4` to `dashboard/requirements.txt`, validate dependency installation/imports, then commit and redeploy only with explicit approval.
