"""
web/data.py — database access for the FastAPI dashboard.

Deliberately plain SQL through psycopg rather than the PostgREST-shaped
pg_client used by the Streamlit app: this app renders whole pages server-side,
so it wants ordering, counting and paging done in the database, not in pandas.

Reuses the editorial config (streams, places, week anchor) so both apps agree
on what a stream is and when a week starts.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

from dashboard import streams as S
from src.scraping.common import anchor_on_or_before

KEPT_ACTIONS = ("keep", "accept_top1", "accept_top2", "manual")


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    return dsn


def _conn():
    return psycopg.connect(_dsn(), row_factory=dict_row)


def week_options(limit: int = 12) -> list[tuple[date, date, str]]:
    """Completed publishing weeks, newest first, back to the oldest article."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("select min(article_date) d from articles where article_date is not null")
        row = cur.fetchone()
    earliest = row["d"] if row and row["d"] else date.today()
    current_start = anchor_on_or_before(date.today())
    out: list[tuple[date, date, str]] = []
    cur_start = current_start - timedelta(days=7)
    while cur_start >= anchor_on_or_before(earliest) and len(out) < limit:
        end = cur_start + timedelta(days=6)
        out.append((cur_start, end, f"{cur_start:%a %-d %b} – {end:%a %-d %b %Y}"))
        cur_start -= timedelta(days=7)
    return out or [(current_start - timedelta(days=7), current_start - timedelta(days=1), "this week")]


def fetch_articles(stream: str | None, place: str | None, week: tuple[date, date] | None,
                   status: str, q: str, offset: int, limit: int) -> tuple[list[dict], int]:
    """One page of articles plus the total matching count.

    Stream and place are derived in Python (they come from config, not columns),
    so filtering on them happens after the SQL date/status/search filter. The
    date filter is the selective one, so this stays cheap.
    """
    where, params = ["1=1"], []
    if week:
        where.append("a.article_date >= %s and a.article_date <= %s")
        params += [week[0], week[1]]
    if q:
        where.append("(a.title ilike %s or a.summary ilike %s)")
        params += [f"%{q}%", f"%{q}%"]

    sql = f"""
        select a.url, a.title, a.article_date, a.source, a.summary,
               a.topic_tags, a.geographic_focus,
               d.action, d.stream_override, d.selected_for_newsletter
          from articles a
          left join curator_decisions d on d.url = a.url
         where {' and '.join(where)}
         order by a.article_date desc nulls last, a.url
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    for r in rows:
        r["stream"] = (r.get("stream_override")
                       or S.assign_stream(r["source"], r["title"]))
        r["place"] = S.assign_place(r["source"])
        act = r.get("action")
        r["status"] = ("Kept" if act in KEPT_ACTIONS
                       else "Rejected" if act == "reject" else "Pending")
        r["for_newsletter"] = bool(r.get("selected_for_newsletter"))

    if stream and stream != "all":
        rows = [r for r in rows if r["stream"] == stream]
    elif stream == "all":
        # "All" means all the news. Papers are asked for by name.
        rows = [r for r in rows if r["stream"] not in S.EXCLUDED_FROM_ALL]
    if place and place != "All":
        rows = [r for r in rows if r["place"] == place]
    if status == "newsletter":
        # Not a status alongside kept and rejected: it is a flag on top of
        # one, so it filters on its own rather than through r["status"].
        rows = [r for r in rows if r["for_newsletter"]]
    elif status != "all":
        rows = [r for r in rows if r["status"].lower() == status]

    return rows[offset:offset + limit], len(rows)


def stream_counts(week: tuple[date, date] | None,
                  status: str = "all") -> dict[str, int]:
    """Per-category counts for the week, on the same footing as the list.

    The status is passed through so a tab's number is the number of cards
    that tab actually shows. With the default pending view that means the
    count is the size of the job left, and it drops as you sort.
    """
    rows, _ = fetch_articles(None, None, week, status, "", 0, 10**6)
    out = {s: 0 for s in S.ORDER}
    for r in rows:
        out[r["stream"]] = out.get(r["stream"], 0) + 1
    # The All tab shows what All actually contains, so the count has to match.
    out["all"] = sum(n for s, n in out.items() if s not in S.EXCLUDED_FROM_ALL)
    return out


def set_decision(url: str, action: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """insert into curator_decisions (url, action, label, decided_at)
               values (%s, %s, '', now())
               on conflict (url) do update set action = excluded.action,
                                               decided_at = now()""",
            (url, action))
        c.commit()


def clear_decision(url: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("delete from curator_decisions where url = %s", (url,))
        c.commit()


def set_newsletter(url: str, on: bool) -> None:
    """Flag an article as one for this week's post.

    Independent of keep and reject: an article is flagged *and* kept, so
    ticking it both marks it for Friday and takes it off the unsorted pile.
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """insert into curator_decisions (url, action, label,
                                              selected_for_newsletter, decided_at)
               values (%s, 'keep', '', %s, now())
               on conflict (url) do update set
                   selected_for_newsletter = excluded.selected_for_newsletter,
                   action = case when excluded.selected_for_newsletter
                                 then 'keep' else curator_decisions.action end""",
            (url, on))
        c.commit()


def newsletter_count(week: tuple[date, date] | None) -> int:
    """How many articles are marked for this week's post."""
    rows, _ = fetch_articles(None, None, week, "newsletter", "", 0, 10**6)
    return len(rows)


# Words that hint at what an idea is, so the exported file groups itself.
_IDEA_KINDS = (
    ("source", ("source", "feed", "rss", "substack", "newsletter to", "add ",
                "follow ", "subscribe", "http")),
    ("bug", ("broken", "not working", "doesn't", "does not", "wrong", "bug",
             "error", "missing", "duplicate")),
)


def _idea_kind(body: str) -> str:
    low = body.lower()
    for kind, words in _IDEA_KINDS:
        if any(w in low for w in words):
            return kind
    return "thought"


def add_idea(body: str) -> None:
    """Record a thought, a source worth adding, or something that is broken."""
    body = (body or "").strip()
    if not body:
        return
    with _conn() as c, c.cursor() as cur:
        cur.execute("insert into curator_ideas (body, kind) values (%s, %s)",
                    (body, _idea_kind(body)))
        c.commit()


def open_ideas() -> list[dict]:
    with _conn() as c, c.cursor() as cur:
        return cur.execute(
            """select id, created_at, body, kind from curator_ideas
                where status = 'open' order by created_at desc""").fetchall()


def idea_count() -> int:
    with _conn() as c, c.cursor() as cur:
        return cur.execute(
            "select count(*) n from curator_ideas where status = 'open'"
        ).fetchone()["n"]


def close_ideas(ids: list) -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""update curator_ideas set status = 'reviewed',
                          reviewed_at = now() where id = any(%s)""", (ids,))
        n = cur.rowcount
        c.commit()
        return n


def set_stream(url: str, stream: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """insert into curator_decisions (url, action, label, stream_override)
               values (%s, 'summary_only', '', %s)
               on conflict (url) do update set stream_override = excluded.stream_override""",
            (url, stream))
        c.commit()


def kept_rows(week: tuple[date, date] | None, stream: str | None,
              status: str = "kept") -> list[dict]:
    rows, _ = fetch_articles(stream, None, week, status, "", 0, 10**6)
    return rows


def pending_count(stream: str | None, place: str | None,
                  week: tuple[date, date] | None) -> int:
    """Articles in this view with no keep/reject yet — the size of the job."""
    rows, _ = fetch_articles(stream, place, week, "pending", "", 0, 10**6)
    return len(rows)


def notes_for(urls: list[str]) -> dict[str, list[dict]]:
    """Curator notes keyed by article url."""
    if not urls:
        return {}
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """select url, note, created_at from article_notes
                where url = any(%s) order by created_at desc""", (urls,))
        rows = cur.fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["url"], []).append(r)
    return out


def add_note(url: str, note: str) -> None:
    note = (note or "").strip()
    if not note:
        return
    with _conn() as c, c.cursor() as cur:
        cur.execute("insert into article_notes (url, note) values (%s, %s)", (url, note))
        c.commit()


def delete_note(note_id: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("delete from article_notes where id = %s", (note_id,))
        c.commit()
