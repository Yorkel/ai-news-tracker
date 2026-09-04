-- Migration 020: curator_ideas
--
-- A free-text inbox from the dashboard: a thought about the newsletter, a
-- source worth adding, something that is not working. One box, no form to
-- fill in, because anything more than a box does not get used.
--
-- Why the database and not a file in the repo: the dashboard runs on Render,
-- where the filesystem is ephemeral and has no access to the git working
-- tree, so a file written by the live app is gone at the next deploy.
-- scripts/ideas.py pulls these into config/ideas.yml when working in the repo,
-- which is where they get reviewed and cleared.
--
-- `kind` is a hint, not a constraint: it is set from a word in the text and
-- is only there to group the file into sections.

create table if not exists public.curator_ideas (
  id          uuid primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  body        text not null,
  kind        text not null default 'thought',
  status      text not null default 'open',
  reviewed_at timestamptz
);

create index if not exists curator_ideas_open_idx
  on public.curator_ideas (created_at desc) where status = 'open';
