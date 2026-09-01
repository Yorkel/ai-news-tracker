# AI News Tracker

AI News Tracker is my production research and editorial system for monitoring
developments in AI governance, safety, research, geopolitics and industry. It
collects material from 124 active sources, filters and summarises relevant
articles, and presents them in a private Streamlit workspace for human review
and newsletter preparation.

## What it does

- Runs a scheduled daily scrape across RSS, Google News and news-sitemap sources.
- Applies an approved-domain gate and configurable relevance filters before storage.
- Generates concise article summaries with deterministic fallbacks when model
  providers are unavailable.
- Organises articles across seven editorial streams and five geographic groupings.
- Supports curator decisions, stream overrides, notes, source suggestions and
  newsletter-ready Excel export.

## System flow

```text
Sources → ingestion and filtering → Neon PostgreSQL
        → summarisation → Streamlit curator dashboard → newsletter preparation
```

## Engineering

The system is written in Python and uses Streamlit for the review interface and
Neon PostgreSQL for persistent storage. The scraper is configuration-driven, the
database client uses parameterised SQL, ingestion is idempotent, and curator
decisions are retained separately from generated article data.

Regression tests cover URL normalisation, relevance filtering, geographic
mapping, summary fallbacks and protection against overwriting valid summaries.

## Scope

This is a personal working system and portfolio repository, not a reusable
software package or public dataset. Credentials, private notes, raw working data
and generated exports are not included.
