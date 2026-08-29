# AI News Tracker

Tracks AI governance, AI news, and AI/ML research: ingests sources, stores them
in Supabase, enriches them with short summaries, and surfaces them in a Streamlit
dashboard for triage.

Built from [newstracker-template](https://github.com/Yorkel/newstracker-template),
which was in turn generalised from the education newsletter system.

## Current state

Stage 1 — **no classifier, no categories.** Articles are ingested, filtered,
summarised and listed. Nothing sorts them into categories yet, and nothing needs
to: `v_dashboard` LEFT JOINs predictions, so uncategorised articles render fine.

Categories become worth adding once the daily volume makes a flat list
unreadable. At that point the curator decisions already accumulated in
`curator_decisions` are the labelled training data, so the labelling step that
would otherwise come first does itself.

Category names are already settled in `config/domain.yml` under `labels:`,
unused until then.

## Before this ingests anything

`is_approved_domain()` fails closed: `src/scraping/run.py` drops every article
whose domain is not listed under `relevance.approved_domains` in
`config/domain.yml`. That list is currently **empty**, and `src/scraping/sources.yml`
is an empty roster. A fresh clone therefore scrapes zero articles by design.

Both are filled in during the sources step:

1. Add the source to `src/scraping/sources.yml` with `disabled: true`.
2. Add its domain to `relevance.approved_domains` in `config/domain.yml`.
3. Test it: `python -m src.scraping.try_source <name>`.
4. Flip `disabled: false`.

## Configuration lives in config/domain.yml

The template documented `config/domain.yml` as the place to set relevance terms,
but only `dashboard/config.py` actually read it — the filter lists were hard-coded
in `src/scraping/relevance.py`. That is now wired up via
`src/scraping/domain_config.py`, so keywords, approved/blocked/broad/paywall
domains, blocked URL paths and blocked title terms are all YAML edits. The tuples
in `relevance.py` remain only as fallbacks if the YAML is missing.

### Differences from the education tracker this inherited from

- **The country veto is off.** `geography.veto_non_uk: false`. The education
  tracker dropped any article mentioning a non-UK place; for AI that would
  discard the White House, Brussels, Beijing, Stanford and every US lab.
- **`/us-news/` and `/world/` are not blocked paths.** Same reason.
- Blocked paths are now only genuine noise: sport, celebrity, lifestyle, travel,
  TV listings.

## What is included

- Python scraping and ingestion modules under `src/scraping/`.
- Sentence-transformer embedding and scikit-learn classifier training under `src/classify/`.
- FastAPI model serving under `src/serving/`.
- Streamlit curator dashboard under `dashboard/`.
- Supabase migrations under `migrations/`.
- Manual GitHub Actions workflows under `.github/workflows/`.
- Reusable governance templates under `docs/templates/`.

## What is intentionally not included

- No trained model files.
- No original labelled training data.
- No real source roster or Google Alert feed URLs.
- No previous project history.
- No client/stakeholder notes.

## Required labelled data schema

The training scripts expect:

- `data/modelling/train.csv`
- `data/modelling/val.csv`

Each file should contain at least:

- `text_clean`: text used for classification.
- `target`: class label matching one of the label keys in `config/domain.yml`.
- `title` and `url` are optional but useful for evaluation outputs.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

Run the dashboard locally:

```bash
streamlit run dashboard/app.py
```

Run the API locally after training a model:

```bash
uvicorn src.serving.api:app --host 0.0.0.0 --port 8000
```

## Secrets

Start from `.env.example`. For a deployed tracker, configure secrets in the hosting
provider and in GitHub Actions rather than committing local `.env` files.

Typical runtime secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `CLASSIFIER_API_URL`
- `CLASSIFIER_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` if you use Anthropic fallback enrichment

## Automation defaults

The included workflows are templates. Keep them manual until a new tracker has:

- a fresh Supabase project,
- a deployed classifier,
- configured secrets,
- reviewed schedules,
- curated source and relevance config.

## Governance docs

Use the files in `docs/templates/` as starting points for a new tracker:

- model card,
- dataset datasheet,
- threat model,
- deployment checklist.
