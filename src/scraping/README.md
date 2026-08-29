# Scraping Pipeline

This package ingests candidate articles from RSS feeds, listing pages, saved
newsletter HTML, or custom scraper modules. Output flows into Supabase `articles`
and then through the inference pipeline.

## Layout

```
src/scraping/
├── config.py              loads sources.yml
├── sources.yml            tracker source registry
├── supabase_client.py     get_client + upsert_articles + log_run
├── common.py              Article shape, HTTP retries, dates, text cleaning
├── try_source.py          test one source without writing to Supabase
├── run.py                 orchestrator that iterates sources.yml
├── web/
│   ├── _base.py           listing-page helper
│   ├── auto_listing.py    configurable listing scraper
│   └── custom_scraper_adapter.py
└── newsletters/
    ├── parse_html.py      generic inbound-newsletter HTML parser
    ├── from_disk.py       reads data/inbound_newsletters/<source>/*.html
    └── gmail.py           Gmail API ingestion stub
```

## Add a source

1. Add a disabled source entry to `src/scraping/sources.yml`.
2. Test it with `try_source.py`:

   ```bash
   python -m src.scraping.try_source --source example_feed --since 2026-01-01 --save
   ```

3. Review the saved rows in `data/scratch/`.
4. Enable the source once titles, dates, URLs, and text look clean.

## Source types

RSS feed:

```yaml
- name: example_feed
  type: rss
  params:
    feed_url: "https://example.org/feed.xml"
  apply_relevance_filter: true
```

Listing page:

```yaml
- name: example_listing
  type: web
  scraper: auto_listing
  params:
    start_url: "https://example.org/news"
    link_selector: "a"
  apply_relevance_filter: true
```

Saved newsletter HTML:

```yaml
- name: example_newsletter
  type: newsletter
  ingestion: disk
  params: {}
```

Save files as `data/inbound_newsletters/example_newsletter/YYYY-MM-DD.html`.

## Run

```bash
python -m src.scraping.run --since 2026-01-01 --dry-run
python -m src.scraping.run --source example_feed --since 2026-01-01
python src/pipeline.py --inference
```

## Schema

Apply the SQL files in `migrations/` in numeric order when bootstrapping a new
Supabase project. The core objects are `articles`, `classify_newsletter`,
`curator_decisions`, feedback logs, monitoring logs, and `v_dashboard`.
