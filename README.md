# AI News Tracker

AI News Tracker is my production research and editorial system for monitoring
developments in AI governance, safety, research, geopolitics and industry. It
collects material from 120 active sources, filters and summarises relevant
articles, and presents them in a private, password-gated web workspace for
human review and newsletter preparation.

## What it does

- Runs a scheduled daily scrape across RSS, Google News and news-sitemap sources.
- Applies an approved-domain gate and configurable relevance filters before storage.
- Generates concise article summaries with deterministic fallbacks when model
  providers are unavailable.
- Organises articles across eight editorial categories and five geographic
  groupings, holding arXiv preprints out of the main view so news is not buried.
- Supports curator decisions, category overrides, per-article notes, a
  high-relevance flag and CSV export.
- Assembles the week's selections into a digest grouped by category, ready to
  paste into Substack.
- Answers questions from the collected articles, citing the ones it read.

## System flow

```text
Sources → ingestion and filtering → Neon PostgreSQL
        → summarisation → FastAPI curator dashboard → weekly digest → Substack
```

## Engineering

The system is written in Python and uses FastAPI with server-rendered Jinja2
templates for the review interface and Neon PostgreSQL for persistent storage.
Actions post in the background so the page never reloads and scroll position is
kept, and every form still works without JavaScript. The scraper is
configuration-driven, the
database client uses parameterised SQL, ingestion is idempotent, and curator
decisions are retained separately from generated article data.

Regression tests cover URL normalisation, relevance filtering, geographic
mapping, summary fallbacks and protection against overwriting valid summaries.

## Scope

This is a personal working system and portfolio repository, not a reusable
software package or public dataset. Credentials, private notes, raw working data
and generated exports are not included.
