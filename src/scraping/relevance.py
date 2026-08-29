"""
relevance.py
Per-source relevance filter. Used by scrapers (currently rss_adapter)
to drop articles that don't contain at least one domain keyword in
their title or text.

When `apply_relevance_filter=True` is set on a source in sources.yml, the
scraper uses DEFAULT_KEYWORDS (loaded from config/domain.yml). Rejected articles
are written to data/archive/rejected/<YYYY-MM-DD>_<source>.csv for audit.

Designed for broad sources (whole-paper feeds, general gov.uk alerts, etc.)
that mix education content with other topics. Narrow sources domain-specialist sources don't need this filter and shouldn't have it set.

Filter lists live in config/domain.yml, not here. The tuples below are only
fallbacks for when that file is missing.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from src.scraping.domain_config import flag, tuple_from


# Hard-block list: URLs from these domains are dropped before the keyword
# filter runs, regardless of `apply_relevance_filter`. Social media + known
# low-quality clickbait that has been observed slipping through.
BLOCKED_DOMAINS: tuple[str, ...] = tuple_from(
    "relevance", "blocked_domains",
    ("instagram.com", "facebook.com", "twitter.com", "x.com",
     "tiktok.com", "youtube.com", "youtu.be", "linkedin.com",
     "msn.com", "pressreader.com"),
)

# Reject URLs whose path contains any of these substrings, regardless of domain.
# Targets non-UK / non-education sections within otherwise-legitimate sites
# (e.g. Guardian's /us-news/, BBC's /sport/ sub-paths).
BLOCKED_URL_PATTERNS: tuple[str, ...] = tuple_from(
    "relevance", "blocked_url_patterns",
    ("/sport/", "/entertainment/", "/celebrity/", "/fashion/",
     "/lifestyle/", "/travel/", "/iplayer/", "/programmes/"),
)


def is_blocked_domain(url: str) -> bool:
    """True if `url` is on the hard-block domain list (sub-domains included)."""
    if not isinstance(url, str) or not url:
        return False
    netloc = urlparse(url).netloc.lower().lstrip(".")
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return any(netloc == d or netloc.endswith("." + d) for d in BLOCKED_DOMAINS)


def is_blocked_url_pattern(url: str) -> bool:
    """True if the URL path matches a blocked section pattern (case-insensitive)."""
    if not isinstance(url, str) or not url:
        return False
    path = urlparse(url).path.lower()
    return any(p in path for p in BLOCKED_URL_PATTERNS)


# Country-context terms that disqualify an article as non-UK. Matched on
# title + body together. Conservative — common demonyms like "American"/"Indian"
# are excluded because they appear in legitimately-UK-relevant content
# (e.g. "Indian students in UK universities"). Locations + heads-of-state
# are the surer signal.
NEGATIVE_COUNTRY_KEYWORDS: tuple[str, ...] = tuple_from(
    "geography", "negative_country_keywords", (),
)

# Whether the country veto runs at all. Off for domains where overseas coverage
# is in scope; the keyword list above is ignored entirely when this is False.
VETO_NON_UK: bool = flag("geography", "veto_non_uk", False)

_NEGATIVE_COUNTRY_PATTERNS: list | None = None  # lazy — compile_keyword_patterns defined below


def is_non_uk_content(title: str | None, body: str | None) -> str | None:
    """Return the matching negative-country keyword if `title+body` reads as
    non-UK content, else None. Used to filter articles that are about
    education-elsewhere rather than UK education."""
    global _NEGATIVE_COUNTRY_PATTERNS
    if not VETO_NON_UK or not NEGATIVE_COUNTRY_KEYWORDS:
        return None
    if _NEGATIVE_COUNTRY_PATTERNS is None:
        _NEGATIVE_COUNTRY_PATTERNS = compile_keyword_patterns(NEGATIVE_COUNTRY_KEYWORDS)
    haystack = ((title or "") + " " + (body or "")).lower()
    if not haystack.strip():
        return None
    for kw, p in zip(NEGATIVE_COUNTRY_KEYWORDS, _NEGATIVE_COUNTRY_PATTERNS):
        if p.search(haystack):
            return kw
    return None


# Approved-domain allowlist. Articles whose URL netloc isn't in this list are
# dropped at scrape time — regardless of which source/alert surfaced them.
# Derived from data/sources_master.csv URLs (+ a few hand-added approved
# Add exact approved domains for the new tracker.
APPROVED_DOMAINS: tuple[str, ...] = tuple_from(
    "relevance", "approved_domains", (),
)

# Broad subset of APPROVED_DOMAINS where the keyword filter must additionally
# pass before the article is kept. These are general-purpose sources
# (BBC, Guardian, universities, parliaments, broader policy bodies) that
# publish on many topics, not just education.
BROAD_DOMAINS: tuple[str, ...] = tuple_from(
    "relevance", "broad_domains", (),
)


# Title-keyword blocklist — articles whose title contains any of these
# (word-boundary match) are dropped, regardless of source. Editorial scope
# decision: add domain-specific out-of-scope title terms here.
BLOCKED_TITLE_KEYWORDS: tuple[str, ...] = tuple_from(
    "relevance", "blocked_title_keywords", (),
)


# Known paywall domains — articles from these are dropped before the
# approved-domain check, even if the domain were ever added to APPROVED_DOMAINS.
# Belts-and-braces: protects against accidental approval. Curators can add
# observed paywall domains here as they appear.
PAYWALL_DOMAINS: tuple[str, ...] = tuple_from(
    "relevance", "paywall_domains",
    ("telegraph.co.uk", "thetimes.com", "thetimes.co.uk",
     "thesundaytimes.co.uk", "ft.com", "spectator.co.uk", "thesun.co.uk"),
)

_APPROVED_DOMAINS_SET = frozenset(APPROVED_DOMAINS)
_BROAD_DOMAINS_SET = frozenset(BROAD_DOMAINS)
_PAYWALL_DOMAINS_SET = frozenset(PAYWALL_DOMAINS)
_BLOCKED_TITLE_PATTERNS: list | None = None  # lazy-compiled on first use


def _article_netloc(url: str) -> str:
    """Normalise a URL down to its netloc — lowercased, leading dots stripped,
    `www.` stripped. Returns "" for invalid input."""
    if not isinstance(url, str) or not url:
        return ""
    netloc = urlparse(url).netloc.lower().lstrip(".")
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def is_approved_domain(url: str) -> bool:
    """True if `url`'s netloc exactly matches an entry in APPROVED_DOMAINS.

    NOTE: exact match only — sub-domains of an approved domain are NOT
    automatically approved. This avoids accidentally approving e.g.
    subdomains when only a parent domain was intended. Add sub-domains explicitly if needed.
    """
    return _article_netloc(url) in _APPROVED_DOMAINS_SET


def matched_blocked_title_keyword(title: str | None) -> str | None:
    """Return the first matching BLOCKED_TITLE_KEYWORDS entry if `title`
    contains any of them (word-boundary), else None. Used to drop articles
    on out-of-scope topics regardless of which approved source surfaced them."""
    global _BLOCKED_TITLE_PATTERNS
    if not isinstance(title, str) or not title.strip():
        return None
    if _BLOCKED_TITLE_PATTERNS is None:
        _BLOCKED_TITLE_PATTERNS = compile_keyword_patterns(BLOCKED_TITLE_KEYWORDS)
    haystack = title.lower()
    for kw, p in zip(BLOCKED_TITLE_KEYWORDS, _BLOCKED_TITLE_PATTERNS):
        if p.search(haystack):
            return kw
    return None


def is_paywall_domain(url: str) -> bool:
    """True if `url`'s netloc exactly matches a known paywall domain
    (see PAYWALL_DOMAINS). Checked before is_approved_domain() so paywall
    rejections get a specific reason in the rejection log."""
    return _article_netloc(url) in _PAYWALL_DOMAINS_SET


def is_broad_domain(url: str) -> bool:
    """True if `url`'s netloc is on the BROAD_DOMAINS subset of approved
    sources. Broad-domain articles need the education keyword filter to
    pass before being kept (general news / university news / parliaments
    cover many topics, not just education). Exact match only — same rule
    as is_approved_domain()."""
    return _article_netloc(url) in _BROAD_DOMAINS_SET


DEFAULT_KEYWORDS: tuple[str, ...] = tuple_from(
    "relevance", "keywords",
    ("ai", "artificial intelligence", "machine learning"),
)

# Back-compat alias — run.py and cleanup_existing_articles.py import this name.
DEFAULT_EDUCATION_KEYWORDS: tuple[str, ...] = DEFAULT_KEYWORDS


def compile_keyword_patterns(keywords: tuple[str, ...] | list[str]) -> list[re.Pattern]:
    """Compile keyword strings into word-boundary regex patterns (case-insensitive)."""
    patterns = []
    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l or "-" in kw_l:
            patterns.append(re.compile(rf"(?<!\w){re.escape(kw_l)}(?!\w)"))
        else:
            patterns.append(re.compile(rf"\b{re.escape(kw_l)}\b"))
    return patterns


def matched_keywords(text: str, patterns: list[re.Pattern],
                     keywords: tuple[str, ...] | list[str] | None = None) -> list[str]:
    """Return the list of keywords that match in `text`. Empty list = filter rejects."""
    if not isinstance(text, str) or not text.strip():
        return []
    t = text.lower()
    if keywords is None:
        # Return abstract markers when caller didn't supply the original keyword list
        return [p.pattern for p in patterns if p.search(t)]
    return [kw for kw, p in zip(keywords, patterns) if p.search(t)]


REJECTION_DIR = Path("data/archive/rejected")
_REJECTION_LOCK = Lock()
_REJECTION_HEADER = (
    "url", "title", "source", "source_type", "article_date",
    "matched_keywords_attempted", "rejected_at"
)


def log_rejection(*, source: str, url: str, title: str, source_type: str,
                  article_date: date | None, matched_keywords_attempted: list[str]) -> None:
    """Append one rejected-article row to data/archive/rejected/<date>_<source>.csv.

    Thread-safe (we use a process-wide lock — scrapers are single-threaded per
    source, but multiple sources may share this module). Idempotent in spirit:
    even if called twice for the same URL, both rows go in — the rejection log
    is an audit trail, not a deduplicated store.
    """
    REJECTION_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REJECTION_DIR / f"{datetime.now().date().isoformat()}_{source}.csv"
    write_header = not out_path.exists()
    row = (
        url,
        title or "",
        source,
        source_type,
        article_date.isoformat() if article_date else "",
        ";".join(matched_keywords_attempted),
        datetime.now().isoformat(timespec="seconds"),
    )
    with _REJECTION_LOCK:
        with open(out_path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(_REJECTION_HEADER)
            w.writerow(row)
