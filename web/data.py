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
               d.action, d.stream_override
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

    if stream and stream != "all":
        rows = [r for r in rows if r["stream"] == stream]
    if place and place != "All":
        rows = [r for r in rows if r["place"] == place]
    if status != "all":
        rows = [r for r in rows if r["status"].lower() == status]

    return rows[offset:offset + limit], len(rows)


def stream_counts(week: tuple[date, date] | None) -> dict[str, int]:
    rows, _ = fetch_articles(None, None, week, "all", "", 0, 10**6)
    out = {s: 0 for s in S.ORDER}
    for r in rows:
        out[r["stream"]] = out.get(r["stream"], 0) + 1
    out["all"] = len(rows)
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


def set_stream(url: str, stream: str) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """insert into curator_decisions (url, action, label, stream_override)
               values (%s, 'summary_only', '', %s)
               on conflict (url) do update set stream_override = excluded.stream_override""",
            (url, stream))
        c.commit()


def kept_rows(week: tuple[date, date] | None, stream: str | None) -> list[dict]:
    rows, _ = fetch_articles(stream, None, week, "kept", "", 0, 10**6)
    return rows
