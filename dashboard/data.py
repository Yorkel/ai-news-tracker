"""
Data loading and Supabase persistence helpers for the curator dashboard.

Replaces the old CSV / local-JSON model. Reads articles + predictions from the
Supabase `v_dashboard` view (joins articles + classify_newsletter on URL).
Writes curator decisions and summaries to the `curator_decisions` table.

The only session-state we still own here is the curator-added rows
(`st.session_state.curator_articles`) and the in-page UI category overrides
(`st.session_state.category_overrides`) - those are managed in their page
modules, not here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

# Streamlit does not read .env, so nothing here saw DATABASE_URL / SUPABASE_*
# unless they were exported into the shell first. Load it explicitly.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional; env vars may be set another way
    pass


def _secrets_into_environ() -> None:
    """Copy st.secrets into os.environ.

    Streamlit Cloud exposes secrets ONLY through st.secrets; it does not put
    them in the environment. Everything else in this project reads os.environ
    (get_client, the Anthropic/OpenAI SDKs, src.scraping.*), so without this
    bridge a correctly-configured Cloud deploy still fails with "No database
    configured" — which is exactly what happened on the first deploy.

    Existing environment variables win, so a local .env keeps overriding.
    """
    try:
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float, bool)) and k not in os.environ:
                os.environ[str(k)] = str(v)
    except Exception:
        # No secrets.toml locally is normal and not an error.
        pass


_secrets_into_environ()


# ── Null-safe text cleaning ──────────────────────────────────────────────────
def clean_text(v):
    """Coerce a possibly-null value to a clean display string.

    pandas NaN is a *truthy* float, so the usual `x or ''` guard lets it slip
    through and renders the literal string 'nan' in the UI / Excel. This is the
    single shared cleaner for the whole dashboard (Triage, Categorise, Draft,
    export). Returns '' for None / NaN / NaT / the strings 'nan'/'none'/'nat'.
    Lists/tuples (e.g. topic_tags) are returned unchanged so callers can iterate.
    """
    if isinstance(v, (list, tuple)):
        return v
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"nan", "none", "nat"} else s


# ── Client ────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client():
    """Single cached database client per Streamlit process.

    Mirrors src.scraping.supabase_client.get_client(): DATABASE_URL selects the
    Postgres backend, otherwise Supabase. Both expose the same fluent API, so
    every read and write below is unchanged either way. The Supabase SDK is
    imported lazily so the dashboard runs without it installed.
    """
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        from src.scraping.pg_client import PgClient
        return PgClient(dsn)

    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError(
            "No database configured. Set DATABASE_URL for Postgres, or "
            "SUPABASE_URL and SUPABASE_ANON_KEY (or SERVICE_KEY) for Supabase"
        )
    return create_client(url, key)


# ── Reads ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_classified_articles(min_week: int | None = None) -> pd.DataFrame:
    """Pull article + prediction rows from the `v_dashboard` view.

    `min_week` lets a page narrow to recent weeks; pass None to fetch all.
    """
    client = get_client()
    # Page through the view: PostgREST caps a single response at 1000 rows, so
    # a bare .execute() silently dropped the oldest articles once v_dashboard
    # passed 1000 rows (e.g. "search all weeks" missing old items). Loop in
    # 1000-row pages until a short page signals the end. Matches the pagination
    PAGE = 1000
    rows: list[dict] = []
    off = 0
    while True:
        q = client.table("v_dashboard").select("*")
        if min_week is not None:
            q = q.gte("week_number", min_week)
        batch = q.range(off, off + PAGE - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        off += PAGE
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Ensure week_number is integer (Supabase may return as int or float depending)
    if "week_number" in df.columns:
        df["week_number"] = pd.to_numeric(df["week_number"], errors="coerce").astype("Int64")
    return df

@st.cache_data(ttl=60)
def load_decisions() -> dict[str, dict]:
    """Return {url: {action, label, summary, summary_generated_at, decided_at, notes}}.

    Fresher cache than articles (60s) so accept/reject updates show quickly.
    """
    client = get_client()
    # Page through: PostgREST caps a single response at 1000 rows, so a bare
    # .execute() silently drops decisions once curator_decisions passes 1000 rows
    # (inevitable — the weekly reset is non-destructive). A missing decision here
    # makes a kept/accepted article vanish from Categorise, Draft, and the Excel
    # export. Loop in 1000-row pages, matching load_classified_articles.
    PAGE = 1000
    rows: list[dict] = []
    off = 0
    while True:
        batch = (
            client.table("curator_decisions")
            .select("*")
            .range(off, off + PAGE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        off += PAGE
    return {row["url"]: row for row in rows}


# ── Weekly reset (archive + week boundary) ────────────────────────────────────
@st.cache_data(ttl=60)
def get_week_boundary() -> str | None:
    """ISO timestamp of the most recent 'Start a new week' reset, or None if
    never reset. Decisions made before this are archived and hidden from the
    Categorise + Draft pages (see get_kept_articles / get_accepted_articles)."""
    client = get_client()
    try:
        resp = (
            client.table("curator_resets")
            .select("reset_at").order("reset_at", desc=True).limit(1).execute()
        )
    except Exception:
        # Table not created yet (migration 015 not run) - treat as "no boundary
        # set" so Categorise/Draft show everything instead of crashing. Once the
        # migration is applied this path stops being hit.
        return None
    rows = resp.data or []
    return rows[0]["reset_at"] if rows else None


def _before_boundary(decided_at, boundary) -> bool:
    """True if a decision's decided_at falls strictly before the week boundary
    (so it belongs to a previous, archived week). Parses both to UTC datetimes
    rather than comparing ISO strings, which is fragile across tz/microsecond
    formatting. A row with no parseable decided_at is treated as current."""
    if not boundary:
        return False
    b = pd.to_datetime(boundary, utc=True, errors="coerce")
    d = pd.to_datetime(decided_at, utc=True, errors="coerce")
    return bool(pd.notna(b) and pd.notna(d) and d < b)


def archive_and_reset_week(week_label: str) -> dict:
    """Snapshot this week's curator decisions into curator_decisions_archive,
    then record a new week boundary. NON-DESTRUCTIVE: curator_decisions is left
    intact, so kept/rejected articles keep their status (they won't reappear in
    Review) and pending articles are untouched. The new boundary just hides this
    week's work from Categorise + Draft. Returns {'archived': n}."""
    client = get_client()
    boundary = get_week_boundary()
    q = client.table("curator_decisions").select("*")
    if boundary:
        q = q.gte("decided_at", boundary)
    rows = q.execute().data or []
    if rows:
        client.table("curator_decisions_archive").insert(
            [{"week_label": week_label, "url": r.get("url"), "decision": r} for r in rows]
        ).execute()
    client.table("curator_resets").insert(
        {"week_label": week_label, "n_archived": len(rows)}
    ).execute()
    # Bust caches so the pages reflect the new boundary immediately.
    load_decisions.clear()
    get_week_boundary.clear()
    return {"archived": len(rows)}


# ── Writes ───────────────────────────────────────────────────────────────────

def record_decision(url: str, action: str, label: str) -> None:
    """Upsert a curator decision on the given URL.

    `action` ∈ {keep, reject, accept_top1, accept_top2, manual,
    save_for_later, summary_only}. Page 1 (Review) uses keep/reject;
    Page 2 (Organise) upgrades keep → accept_top1/top2/manual once a
    category is assigned.
    Invalidates the decisions cache so the next render picks it up.
    """
    client = get_client()
    client.table("curator_decisions").upsert(
        {
            "url": url,
            "action": action,
            "label": label,
            "decided_at": "now()",
        },
        on_conflict="url",
    ).execute()
    load_decisions.clear()


def record_stream_override(url: str, stream: str) -> None:
    """Move one article into a different dashboard stream.

    Streams are normally derived from the source (see dashboard/streams.py), so
    this records the curator disagreeing about a single article. Written to
    curator_decisions, which is keyed on url and NOT NULL on `action`: an
    article moved before it has been kept or rejected gets the same
    'summary_only' placeholder record_summary() uses, and a later keep/reject
    overwrites the action while leaving the override in place.
    """
    if not url or not stream:
        return
    client = get_client()
    existing = client.table("curator_decisions").select("action").eq("url", url).limit(1).execute()
    if existing.data:
        client.table("curator_decisions").update(
            {"stream_override": stream}
        ).eq("url", url).execute()
    else:
        client.table("curator_decisions").insert({
            "url": url, "action": "summary_only", "label": "",
            "stream_override": stream,
        }).execute()
    load_stream_overrides.clear()
    load_decisions.clear()


def clear_stream_override(url: str) -> None:
    """Return an article to its derived stream."""
    if not url:
        return
    get_client().table("curator_decisions").update(
        {"stream_override": None}
    ).eq("url", url).execute()
    load_stream_overrides.clear()
    load_decisions.clear()


@st.cache_data(ttl=60)
def load_stream_overrides() -> dict[str, str]:
    """{url: stream} for every article the curator has moved."""
    try:
        rows = (
            get_client().table("curator_decisions")
            .select("url, stream_override").execute().data or []
        )
    except Exception:
        return {}
    return {
        r["url"]: r["stream_override"]
        for r in rows
        if r.get("url") and r.get("stream_override")
    }


def fetch_article_text(url: str) -> str:
    """Pull full article body text from `articles.text` for one URL.

    `v_dashboard` only exposes `text_clean` (a truncated 80-word snippet that
    often starts with nav cruft). The on-demand Generate-Summary buttons on
    Triage and Draft need the full body to produce a good summary, so this
    helper fetches it directly from `articles` on click.
    """
    if not url:
        return ""
    client = get_client()
    resp = client.table("articles").select("text").eq("url", url).limit(1).execute()
    rows = resp.data or []
    return (rows[0].get("text") if rows else "") or ""


def is_authenticated() -> bool:
    """True if the curator has entered the correct password this session.
    Read-only browsing is allowed without auth; mutating buttons are gated
    on this flag (see app.py's curator login widget in the sidebar)."""
    import streamlit as st
    return bool(st.session_state.get("authenticated", False))


def delete_decision(url: str) -> None:
    """Remove the curator_decisions row for `url` entirely. The article
    returns to Pending status in Review and disappears from Organise/Draft.
    Used by Organise's 'Send back to Review' button when the curator wants
    to reconsider an accept decision from scratch."""
    client = get_client()
    client.table("curator_decisions").delete().eq("url", url).execute()
    load_decisions.clear()


def set_newsletter_pick(url: str, selected: bool) -> None:
    """Persist a 'shortlist for newsletter' click on an already-accepted article.

    Uses UPDATE (not upsert) because Organise only shows articles with an
    existing decision row - and upsert would fail the NOT NULL on `action`
    if it ever hit the insert path.
    """
    client = get_client()
    client.table("curator_decisions").update(
        {"selected_for_newsletter": selected}
    ).eq("url", url).execute()
    load_decisions.clear()


def set_category_override(url: str, override: str | None) -> None:
    """Persist a 'move to <category>' override on an already-accepted article."""
    client = get_client()
    client.table("curator_decisions").update(
        {"newsletter_category_override": override}
    ).eq("url", url).execute()
    load_decisions.clear()


def add_curator_article(
    *, url: str, title: str, article_date_iso: str, source: str,
    text_clean: str, top1: str, top2: str,
) -> None:
    """Persist a curator-added article so its URL exists in `articles`.

    Without this, accepting / rejecting / saving a manually-added article
    would fail the curator_decisions → articles FK. We also write a row to
    classify_newsletter using the curator's two suggested categories with
    fake 1.0 / 0.0 confidences, so v_dashboard renders the article with the
    same shape as a scraped+classified one.

    Idempotent on URL: re-submitting the same URL is a no-op rather than
    an error (uses upsert with on_conflict=url).
    """
    client = get_client()

    client.table("articles").upsert({
        "url": url,
        "title": title,
        "article_date": article_date_iso,
        "source": source or "manually added",
        "source_type": "manually added",
        "text_clean": text_clean or title,
        "text": text_clean or None,
        "country": "eng",
        "dataset_type": "inference",
        "classification_status": "classified",
    }, on_conflict="url").execute()

    client.table("classify_newsletter").upsert({
        "url": url,
        "top1": top1,
        "top1_confidence": 1.0,
        "top2": top2,
        "top2_confidence": 0.0,
        "confidence_gap": 1.0,
    }, on_conflict="url").execute()

    load_classified_articles.clear()


def record_feedback(suggestions: str) -> None:
    """Append a free-text feedback row to curator_feedback (table from migration 008).
    Anonymous - no curator identity is recorded, per the Page 3 feedback-box spec.
    """
    if not suggestions or not suggestions.strip():
        return
    client = get_client()
    client.table("curator_feedback").insert({
        "suggestions": suggestions.strip(),
    }).execute()


PENDING_SOURCES_FILE = (
    __import__("pathlib").Path(__file__).resolve().parents[1] / "config" / "pending_sources.yml"
)


def record_source_suggestion(
    source_name: str,
    url: str = "",
    stream: str = "",
    coverage_hint: str = "",
    notes: str = "",
) -> dict:
    """Log a curator's suggested source to BOTH the holding file and the table.

    The holding file (config/pending_sources.yml) is the primary record: it
    lives in the repo, shows up in a diff, and survives the database being
    unavailable. The source_suggestions table is written too so the dashboard
    can list pending items without reading the filesystem.

    Deliberately does NOT touch src/scraping/sources.yml. A suggestion must be
    promoted by hand — finding and testing the feed, and adding the domain to
    approved_domains — because run.py fails closed and a half-added source
    scrapes and silently drops everything.

    Returns {"file": bool, "db": bool} so the caller can tell the curator what
    actually persisted rather than claiming success for both.
    """
    import pathlib

    import yaml

    name = (source_name or "").strip()
    if not name:
        return {"file": False, "db": False}

    entry = {
        "name": name,
        "url": (url or "").strip(),
        "stream": (stream or "").strip(),
        "coverage_hint": (coverage_hint or "").strip(),
        "notes": (notes or "").strip(),
        "suggested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "pending",
    }

    wrote_file = False
    try:
        path = pathlib.Path(PENDING_SOURCES_FILE)
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
        header = ""
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            header = raw.split("pending:")[0]
        items = list((doc or {}).get("pending") or [])
        items.append(entry)
        path.write_text(
            header + "pending:\n" + yaml.safe_dump(items, sort_keys=False, allow_unicode=True,
                                                   default_flow_style=False, indent=2),
            encoding="utf-8",
        )
        wrote_file = True
    except Exception:
        # A filesystem failure must not lose the suggestion — the DB write below
        # is still attempted, and the return value reports what happened.
        wrote_file = False

    wrote_db = False
    try:
        get_client().table("source_suggestions").insert({
            "source_name": entry["name"],
            "url": entry["url"] or None,
            "stream": entry["stream"] or None,
            "coverage_hint": entry["coverage_hint"] or None,
            "notes": entry["notes"] or None,
        }).execute()
        wrote_db = True
    except Exception:
        wrote_db = False

    return {"file": wrote_file, "db": wrote_db}


def load_source_suggestions() -> list[dict]:
    """Pending suggestions from the holding file (the record that lives in git)."""
    import pathlib

    import yaml

    try:
        path = pathlib.Path(PENDING_SOURCES_FILE)
        if not path.exists():
            return []
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return list(doc.get("pending") or [])
    except Exception:
        return []


def record_summary(url: str, summary: str) -> None:
    """Persist a generated LLM summary onto a curator_decisions row.

    Safe to call before any keep/reject - Page 1 (Review) lets the curator
    Generate Summary on a pending article. If no row exists yet, we insert
    a placeholder with action='summary_only' so the NOT NULL constraint on
    `action` is satisfied. Any subsequent keep/reject via record_decision()
    overwrites the placeholder.
    """
    client = get_client()
    existing = client.table("curator_decisions").select("action").eq("url", url).limit(1).execute()
    if not existing.data:
        client.table("curator_decisions").insert({
            "url": url,
            "action": "summary_only",
        }).execute()
    client.table("curator_decisions").update(
        {
            "summary": summary,
            "summary_generated_at": "now()",
        }
    ).eq("url", url).execute()
    load_decisions.clear()


def record_topic_sentence(url: str, sentence: str) -> None:
    """Persist an extractive topic sentence onto the article (articles.topic_sentence).

    Unlike record_summary (a curator override stored in curator_decisions), the
    topic sentence is article-level enrichment shown on the Triage page, so it's
    written straight to `articles` - same place the scrape/sweep populate it.
    """
    client = get_client()
    client.table("articles").update(
        {
            "topic_sentence": sentence,
            "topic_sentence_generated_at": "now()",
        }
    ).eq("url", url).execute()
    load_classified_articles.clear()


# ── Helpers used by pages ─────────────────────────────────────────────────────

def init_session_state() -> None:
    """Lazy-initialise the UI-only state the pages depend on.

    Decisions and summaries no longer live in session_state - they're in
    Supabase. Only purely-UI ephemeral state remains here.
    """
    if "curator_articles" not in st.session_state:
        st.session_state.curator_articles = []
    if "category_overrides" not in st.session_state:
        st.session_state.category_overrides = {}
    if "newsletter_picks" not in st.session_state:
        st.session_state.newsletter_picks = set()
    if "draft_descriptions" not in st.session_state:
        st.session_state.draft_descriptions = {}


def get_kept_articles(df: pd.DataFrame) -> list[dict]:
    """Return articles the curator has kept on Page 1 (action='keep') or
    already categorised (action ∈ {accept_top1, accept_top2, manual}).

    Used by Page 2 (Select Categories). Excludes rejected and save_for_later.
    Each row carries `action` and `curator_label` so the page can render the
    correct status badge.
    """
    decisions = load_decisions()
    boundary = get_week_boundary()
    KEPT_ACTIONS = {"keep", "accept_top1", "accept_top2", "manual"}
    out: list[dict] = []
    for url, dec in decisions.items():
        if dec.get("action") not in KEPT_ACTIONS:
            continue
        if _before_boundary(dec.get("decided_at"), boundary):
            continue  # archived in a previous week
        match = df[df["url"] == url] if (not df.empty and "url" in df.columns) else pd.DataFrame()
        row = match.iloc[0].to_dict() if len(match) else {"url": url, "title": "Unknown"}
        row["action"] = dec.get("action")
        row["curator_label"] = dec.get("label") or None
        # Curator edit > pre-generated articles.summary (from v_dashboard)
        row["summary"] = dec.get("summary") or row.get("summary")
        out.append(row)
    return out


def get_accepted_articles(df: pd.DataFrame) -> list[dict]:
    """Join `v_dashboard` rows with current curator_decisions; return only
    articles the curator has actually accepted (top1, top2, or manual).

    Used by the Organise and Draft pages. Excludes:
      - rejected articles
      - save-for-later articles (curator hasn't decided yet)
      - rows that exist only because of a summary (no action set)
    Curator-added rows (session-only for now) are appended on top.
    """
    decisions = load_decisions()
    boundary = get_week_boundary()
    accepted: list[dict] = []

    ACCEPT_ACTIONS = {"accept_top1", "accept_top2", "manual"}
    for url, dec in decisions.items():
        if dec.get("action") not in ACCEPT_ACTIONS:
            continue
        if _before_boundary(dec.get("decided_at"), boundary):
            continue  # archived in a previous week
        match = df[df["url"] == url] if (not df.empty and "url" in df.columns) else pd.DataFrame()
        row = match.iloc[0].to_dict() if len(match) else {"url": url, "title": "Unknown"}
        row["curator_label"] = dec.get("label") or row.get("top1")
        if url in st.session_state.get("category_overrides", {}):
            row["curator_label"] = st.session_state.category_overrides[url]
        # Summary precedence: curator's edit > pre-generated (articles.summary
        # from v_dashboard). Without the fallback to row.get("summary"),
        # Draft page would show empty for articles the curator never edited
        # even after the pre-gen backfill.
        row["summary"] = dec.get("summary") or row.get("summary")
        accepted.append(row)

    for art in st.session_state.get("curator_articles", []):
        art_copy = dict(art)
        art_copy["curator_label"] = art.get("top1")
        art_copy["curator_added"] = True
        if art.get("url") in st.session_state.get("category_overrides", {}):
            art_copy["curator_label"] = st.session_state.category_overrides[art["url"]]
        accepted.append(art_copy)

    return accepted
