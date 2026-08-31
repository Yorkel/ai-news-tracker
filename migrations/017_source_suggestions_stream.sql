-- Migration 017: source_suggestions.stream
--
-- The dashboard splits articles into four streams (see `streams:` in
-- config/domain.yml). When a curator suggests a new source they say which
-- stream it belongs in, so the suggestion can be promoted straight into
-- src/scraping/sources.yml and the stream map without a second decision.
--
-- Nullable: suggestions made before this column existed keep working, and a
-- curator who is unsure can leave it blank.

alter table public.source_suggestions
  add column if not exists stream text;

comment on column public.source_suggestions.stream is
  'Target dashboard stream: governance | geopolitics | safety | technical';
