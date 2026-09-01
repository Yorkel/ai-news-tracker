# ai-news-tracker

## Commit messages

Do NOT add `Co-Authored-By`, `Generated with Claude Code`, or any other
attribution trailer to commit messages. This is a personal project, the repo is
public, and the commit history is read by people assessing the work.

## What this is

A news ingestion pipeline and curator dashboard feeding a weekly Substack.
124 active RSS/sitemap/Google-News sources across seven editorial streams
(governance, geopolitics, safety, research, technical, deployment, podcasts),
with UK/Ireland/EU/US/Global geography filters.

## Running it

    .venv/bin/streamlit run dashboard/app.py      # dashboard
    python -m src.scraping.run --since-last-run   # scrape

The database is Neon (`DATABASE_URL` in .env). `scripts/local_db.py` runs a
local Postgres instead if you comment that line back in.

## Configuration

Everything editorial lives in `config/domain.yml`: sources-to-stream mapping,
geography, relevance keywords, approved domains, and the Friday week anchor.
`src/scraping/sources.yml` is the source roster. Neither needs code changes.

`src/scraping/pg_client.py` implements the Supabase query API over plain
Postgres, so the same code runs against Neon or Supabase unchanged.
