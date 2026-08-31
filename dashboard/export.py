"""
export.py — the reading-list CSV.

The tracker has two outputs:

  1. a CSV of the interesting things read this week, across every theme
  2. the Friday Substack post

This module is (1). The Draft page's Excel export is (2) — it is shaped like a
newsletter, grouped into categories with editable summaries. This is a flat
record: one row per article, every stream in one file, sorted so the themes
read in the dashboard's own order.

"Interesting" means the curator kept it. Rejected articles, save-for-later, and
rows that exist only because a summary was generated (action='summary_only')
are all excluded — see KEPT_ACTIONS.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

# Mirrors data.get_kept_articles(): 'keep' is Triage, the accept_* actions are
# an already-categorised keep. 'save_for_later' and 'summary_only' are NOT
# decisions to include.
KEPT_ACTIONS = {"keep", "accept_top1", "accept_top2", "manual"}

COLUMNS = [
    "stream", "place", "article_date", "source", "title", "url",
    "summary", "topic_sentence", "curator_label", "decided_at",
]


def kept_frame(
    df: pd.DataFrame,
    decisions: dict[str, dict],
    stream: str | None = None,
) -> pd.DataFrame:
    """Rows the curator kept, ready for CSV. `stream` limits it to one lane."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)

    work = df.copy()
    if stream:
        work = work[work.get("stream") == stream]
    if work.empty:
        return pd.DataFrame(columns=COLUMNS)

    urls = set(work["url"]) if "url" in work.columns else set()
    keep = {
        u: d for u, d in (decisions or {}).items()
        if u in urls and (d or {}).get("action") in KEPT_ACTIONS
    }
    if not keep:
        return pd.DataFrame(columns=COLUMNS)

    work = work[work["url"].isin(keep)].copy()
    work["curator_label"] = [keep[u].get("label") or "" for u in work["url"]]
    work["decided_at"] = [keep[u].get("decided_at") or "" for u in work["url"]]
    # Prefer the curator's edited summary over the generated one on the article.
    work["summary"] = [
        keep[u].get("summary") or work.loc[work["url"] == u, "summary"].iloc[0]
        if "summary" in work.columns else keep[u].get("summary") or ""
        for u in work["url"]
    ]

    for c in COLUMNS:
        if c not in work.columns:
            work[c] = ""
    out = work[COLUMNS].fillna("")

    # Sort by the dashboard's own stream order, then newest first, so the file
    # reads in the same sequence as the pages it came from.
    try:
        from dashboard.streams import ORDER
        out["_o"] = out["stream"].apply(lambda s: ORDER.index(s) if s in ORDER else 99)
        out = out.sort_values(["_o", "article_date"], ascending=[True, False]).drop(columns="_o")
    except Exception:
        out = out.sort_values("article_date", ascending=False)
    return out.reset_index(drop=True)


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    frame.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def filename(stream: str | None = None, today: date | None = None) -> str:
    today = today or date.today()
    part = (stream or "all-streams").replace(" ", "-")
    return f"reading-list_{part}_{today:%Y-%m-%d}.csv"
