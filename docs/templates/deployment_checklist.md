# Deployment Checklist

## Before First Run

- [ ] Supabase project created.
- [ ] Migrations applied.
- [ ] `src/scraping/sources.yml` populated and tested.
- [ ] `config/domain.yml` updated.
- [ ] Training CSVs added locally.
- [ ] Model trained and evaluated.
- [ ] Classifier API deployed.
- [ ] Dashboard deployed.
- [ ] GitHub Actions secrets configured.

## Before Enabling Schedules

- [ ] Manual scrape succeeds.
- [ ] Manual classify succeeds.
- [ ] Dashboard reads the expected rows.
- [ ] Summary enrichment produces acceptable output.
- [ ] Monitoring and backup jobs succeed manually.

## Before Public Release

- [ ] Repository history is clean.
- [ ] No private data or credentials are tracked.
- [ ] README describes the new tracker, not the template.
- [ ] Model card and datasheet are filled in.
