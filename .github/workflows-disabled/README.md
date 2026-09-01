# Disabled workflows

Inherited from newstracker-template. Moved out of `.github/workflows/` on
2026-09-01 so GitHub stops running them: they reference `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY`, which this project does not use (it runs on Postgres
via `DATABASE_URL`), so every scheduled run failed and emailed.

They are kept rather than deleted because several become useful once there is
a classifier: `classify.yml`, `drift.yml`, `fairness.yml`, `health_check.yml`.

To re-enable one: move it back into `.github/workflows/` and swap its Supabase
secrets for `DATABASE_URL`, as `scrape.yml` already does.
