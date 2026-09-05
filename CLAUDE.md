# ai-news-tracker

## Commit messages

Do NOT add `Co-Authored-By`, `Generated with Claude Code`, or any other
attribution trailer to commit messages. This is a personal project, the repo is
public, and the commit history is read by people assessing the work.

## What this is

A news ingestion pipeline and curator dashboard feeding **Earnest Evaluation**,
a weekly Substack published on Fridays. 120 enabled RSS/sitemap/Google-News
sources (124 in the roster) across eight categories — governance, geopolitics,
safety, research, technical, deployment, podcasts, papers — with
UK/Ireland/EU/US/Global geography filters.

`papers` is arXiv and is held out of the All view and the main CSV: it alone
was a quarter of the week's volume. `config/domain.yml` lists which categories
are held back in `streams.exclude_from_all`.

The workflow is two-stage. Triage daily with Keep/Reject; tick "High relevance"
on what belongs in the post. Sorted articles leave the pile, so the default
view is the unsorted week.

## Running it

    .venv/bin/uvicorn web.app:app --reload --port 8000   # dashboard
    python -m src.scraping.run --since-last-run          # scrape
    python scripts/backfill_summaries.py --dry-run       # summarise what has none
    python scripts/ideas.py                              # the Notes to self box

The dashboard is FastAPI + Jinja2 in `web/`, which replaced Streamlit in
September 2026: Streamlit re-ran the whole script on every click, which was the
latency and was architectural rather than tunable. `dashboard/` still holds the
shared config readers (`dashboard/streams.py`), so it is not dead code.

Pages: `/` sorting, `/digest` the week's picks grouped for Substack with a
Copy as Markdown button, `/ask` questions answered from the collected articles.

The database is Neon (`DATABASE_URL` in .env). `scripts/local_db.py` runs a
local Postgres instead if you comment that line back in.

Deployed on Render at https://ai-news-tracker-gqwq.onrender.com, auto-deploying
from `main`. Render does not read `.env`, so the deployed app is always gated by
`LOGIN_PASSWORD`; `TRACKER_NO_AUTH=1` in `.env` skips the gate locally, which
also means `/login` cannot be seen locally without `TRACKER_NO_AUTH=0`.

The scheduled scrape is `.github/workflows/scrape.yml`, daily. GitHub queues
scheduled jobs under load — an 06:00 UTC cron was firing at 10:54 — so the cron
is set for where the run actually lands, not where it is written.

## Configuration

Everything editorial lives in `config/domain.yml`: sources-to-stream mapping,
geography, relevance keywords, approved domains, and the Friday week anchor.
`src/scraping/sources.yml` is the source roster. Neither needs code changes.

`src/scraping/pg_client.py` implements the Supabase query API over plain
Postgres, so the same code runs against Neon or Supabase unchanged.
