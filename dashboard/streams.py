"""
streams.py — the four dashboard lanes.

The dashboard splits articles into four streams:

    governance   AI governance, policy and news
    geopolitics  Geopolitical and world news
    safety       AI safety and security
    technical    ML technical skills

How an article gets a stream
----------------------------
There is no classifier at Stage 1, so the stream is derived, not predicted:

  1. `geopolitics` keywords are checked against the TITLE first. World and
     security stories cut across every source — a Guardian piece, a CSET
     report and a DSIT announcement can all be geopolitical — so this rule
     overrides source assignment.
  2. Otherwise the article takes its source's stream, from `streams.<id>.sources`
     in config/domain.yml.
  3. Anything unmapped falls back to `governance`, the broadest lane, rather
     than being hidden.

Nothing is written to the articles table, so re-bucketing the entire corpus is
a config edit — no migration, no re-ingest. When a classifier does arrive it
can replace step 2 without changing anything that calls this module.

Title-only matching mirrors the ingest filter in src/scraping/run.py, which
found body matching pulled in articles that mentioned a country in passing.
"""

from __future__ import annotations

import re

import pandas as pd

from dashboard.config import _CONFIG  # parsed config/domain.yml

_STREAMS = (_CONFIG.get("streams") or {}) if isinstance(_CONFIG, dict) else {}

ORDER: list[str] = list(_STREAMS.get("order") or ["governance", "geopolitics", "safety", "technical"])
FALLBACK = "governance"


def _meta(stream_id: str) -> dict:
    return _STREAMS.get(stream_id) or {}


DISPLAY = {s: _meta(s).get("display", s.title()) for s in ORDER}
SHORT = {s: _meta(s).get("short", s.title()) for s in ORDER}
DESCRIPTION = {s: _meta(s).get("description", "") for s in ORDER}

# source name -> stream id
SOURCE_STREAM: dict[str, str] = {}
for _s in ORDER:
    for _src in _meta(_s).get("sources") or []:
        SOURCE_STREAM[_src] = _s

_GEO_KEYWORDS = tuple(_meta("geopolitics").get("keywords") or ())
# Word-boundary patterns, same convention as src/scraping/relevance.py, so
# "chip war" matches but "china" does not fire inside "chinampa".
_GEO_PATTERNS = [
    re.compile(rf"(?<!\w){re.escape(k.lower())}(?!\w)" if (" " in k or "-" in k)
               else rf"\b{re.escape(k.lower())}\b")
    for k in _GEO_KEYWORDS
]


def assign_stream(source: str | None, title: str | None = None) -> str:
    """Return the stream id for one article. See module docstring for order."""
    if title and _GEO_PATTERNS:
        hay = str(title).lower()
        for p in _GEO_PATTERNS:
            if p.search(hay):
                return "geopolitics"
    return SOURCE_STREAM.get(str(source or ""), FALLBACK)


def add_stream_column(df: pd.DataFrame, overrides: dict[str, str] | None = None) -> pd.DataFrame:
    """Attach a `stream` column. Returns the same frame for chaining.

    Precedence: a curator override for that url beats the geopolitics keyword
    rule, which beats the source map. `stream_derived` keeps the value the
    rules produced, so the UI can show what the override changed it from.
    """
    if df is None or df.empty:
        if df is not None and "stream" not in df.columns:
            df["stream"] = []
        return df
    titles = df["title"] if "title" in df.columns else pd.Series([""] * len(df), index=df.index)
    sources = df["source"] if "source" in df.columns else pd.Series([""] * len(df), index=df.index)
    derived = [assign_stream(s, t) for s, t in zip(sources, titles)]
    df["stream_derived"] = derived
    if overrides:
        urls = df["url"] if "url" in df.columns else pd.Series([""] * len(df), index=df.index)
        df["stream"] = [
            overrides.get(u) if overrides.get(u) in ORDER else d
            for u, d in zip(urls, derived)
        ]
    else:
        df["stream"] = derived
    return df


def counts(df: pd.DataFrame) -> dict[str, int]:
    """Article count per stream, always covering every stream in ORDER."""
    if df is None or df.empty or "stream" not in df.columns:
        return {s: 0 for s in ORDER}
    vc = df["stream"].value_counts().to_dict()
    return {s: int(vc.get(s, 0)) for s in ORDER}


# ── Geography ───────────────────────────────────────────────────────────────
# A filter that composes with any stream, rather than a stream of its own —
# see the `places:` note in config/domain.yml.
_PLACES = (_CONFIG.get("places") or {}) if isinstance(_CONFIG, dict) else {}
PLACE_ORDER: list[str] = list(_PLACES.get("order") or [])
SOURCE_PLACE: dict[str, str] = {}
for _pl in PLACE_ORDER:
    for _src in _PLACES.get(_pl) or []:
        SOURCE_PLACE[_src] = _pl
PLACE_FALLBACK = "Global"


def assign_place(source: str | None) -> str:
    """Publisher geography for one article, from its source."""
    return SOURCE_PLACE.get(str(source or ""), PLACE_FALLBACK)


def add_place_column(df):
    """Attach a `place` column. Returns the same frame for chaining."""
    if df is None or df.empty:
        if df is not None and "place" not in df.columns:
            df["place"] = []
        return df
    sources = df["source"] if "source" in df.columns else [""] * len(df)
    df["place"] = [assign_place(s) for s in sources]
    return df
