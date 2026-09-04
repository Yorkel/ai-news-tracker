-- Migration 019: article_notes
--
-- Curator notes attached to an article: the thought you have while reading it,
-- filed under the article as its own citation.
--
-- A separate table rather than a column on curator_decisions, because there can
-- be several notes on one article over time and each needs its own timestamp.
-- Not on `articles` either: notes are curator judgement and must survive a
-- re-scrape of the article row.

create table if not exists public.article_notes (
  id          uuid        primary key default gen_random_uuid(),
  url         text        not null,
  note        text        not null,
  created_at  timestamptz not null default now()
);

create index if not exists idx_article_notes_url on public.article_notes (url);
create index if not exists idx_article_notes_created on public.article_notes (created_at desc);
