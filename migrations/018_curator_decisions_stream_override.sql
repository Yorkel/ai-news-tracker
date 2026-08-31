-- Migration 018: curator_decisions.stream_override
--
-- A dashboard stream is normally DERIVED, not stored: config/domain.yml maps
-- each source to a stream, and geopolitics keywords override that on the title
-- (see dashboard/streams.py). That is deterministic and re-buckets the whole
-- corpus on a config edit.
--
-- Derivation is coarse, though: a source sits in one lane, but individual
-- articles from it do not. This column records the curator moving ONE article
-- to a different stream, and takes precedence over both derivation rules.
--
-- Stored on curator_decisions rather than articles so the override is a
-- curator judgement in the decisions log, alongside keep/reject, and so a
-- re-scrape of the article never silently discards it.

alter table public.curator_decisions
  add column if not exists stream_override text;

comment on column public.curator_decisions.stream_override is
  'Curator moved this article to a different stream: governance | geopolitics | safety | technical';

create index if not exists idx_curator_decisions_stream_override
  on public.curator_decisions (stream_override)
  where stream_override is not null;
