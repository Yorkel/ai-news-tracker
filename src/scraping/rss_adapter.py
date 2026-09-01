"""
rss_adapter.py
Ingest any RSS / Atom feed (including Google Alerts) and return Article objects.

Used for all `type: rss` and `type: google_alert` entries in sources.yml:

    - name: bera
      type: rss
      scraper: src.scraping.rss_adapter
      params:
        feed_url: https://www.bera.ac.uk/feed

The adapter handles both standard RSS feeds and Google Alerts' Atom format.
Google Alerts wraps each entry's link as `https://www.google.com/url?...&url=<real>`;
this module unwraps that to the real article URL.
"""

from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlparse

import html as html_lib
import re

import feedparser
from bs4 import BeautifulSoup

from src.scraping.common import Article, build_text_clean, normalise_url

_WS_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    """Strip HTML tags and unescape entities — keeps just clean text."""
    if not s:
        return ""
    text = BeautifulSoup(s, "html.parser").get_text(" ", strip=True)
    text = html_lib.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _unwrap_google_url(link: str) -> str:
    return normalise_url(link)


def _domain_as_source(url: str) -> str | None:
    """Extract a cleaned domain to use as the `source` for an article that came
    in via a Google Alert. The alert itself aggregates many real publishers; we
    want the dashboard to show the publisher, not the alert.

    Examples:
      https://www.bbc.co.uk/news/articles/xyz  →  bbc.co.uk
      https://schoolsweek.co.uk/some-story     →  schoolsweek.co.uk
      https://www.gov.uk/government/news/foo   →  gov.uk
      https://assets.publishing.service.gov.uk/...  →  assets.publishing.service.gov.uk
    """
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or None
    except Exception:
        return None


_ORDINAL_RE = re.compile(r"(\d+)(st|nd|rd|th)\b", re.I)


# Podcast analytics services wrap the real episode URL in a redirect prefix.
# Stripping them yields the canonical page and stops the same episode being
# stored twice if a show changes analytics provider.
_TRACKING_PREFIXES = (
    "pscrb.fm/rss/p/",          # Podscribe
    "mgln.ai/e/",               # Megalodon  (has a numeric segment after /e/)
    "chtbl.com/track/",         # Chartable
    "pdst.fm/e/",               # Podsights
    "dts.podtrac.com/redirect.mp3/",
    "claritaspod.com/measure/",
    "verifi.podscribe.com/rss/p/",
    "prfx.byspotify.com/e/",
)


def _strip_tracking_prefix(url: str) -> str:
    """Unwrap a podcast analytics redirect to the URL it points at."""
    if not url:
        return url
    working = url
    for _ in range(4):  # prefixes are sometimes chained
        low = working.lower()
        for pref in _TRACKING_PREFIXES:
            i = low.find(pref)
            if i == -1:
                continue
            rest = working[i + len(pref):]
            # Megalodon inserts a numeric id segment: /e/211/<real url>
            if pref == "mgln.ai/e/" and "/" in rest:
                head, _, tail = rest.partition("/")
                if head.isdigit():
                    rest = tail
            if not rest:
                continue
            if not rest.startswith(("http://", "https://")):
                rest = "https://" + rest.lstrip("/")
            working = rest
            break
        else:
            break
    return working


def _entry_url(e) -> str:
    """Best available page URL for a feed entry.

    Most feeds set <link>. Podcast feeds from Buzzsprout, Art19 and similar
    often do NOT — they carry only an <enclosure> pointing at the audio, and a
    guid that is an internal id rather than a URL. Without this fallback those
    entries were dropped silently at the top of scrape(), which looks
    identical to an empty feed.
    """
    link = (e.get("link") or "").strip()
    if link:
        return link
    for enc in (e.get("enclosures") or []):
        href = (enc.get("href") or "").strip()
        if href:
            return _strip_tracking_prefix(href)
    guid = (e.get("id") or "").strip()
    if guid.startswith(("http://", "https://")):
        return guid
    return ""


def _entry_date(entry) -> date | None:
    # First try feedparser's pre-parsed dates (works for standard RSS/Atom)
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6]).date()
            except (TypeError, ValueError):
                continue

    # Fallback: parse the raw date string, handling ordinal suffixes like "9th Apr 2026"
    # (Joseph Rowntree Foundation's RSS feed uses this format)
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        cleaned = _ORDINAL_RE.sub(r"\1", raw).strip()
        for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%B %d, %Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def _entry_text(entry) -> str:
    # Prefer content > summary > description
    if entry.get("content"):
        try:
            return entry.content[0].value
        except (AttributeError, IndexError, KeyError):
            pass
    return entry.get("summary") or entry.get("description") or ""


def scrape(*, source: str, feed_url: str,
           since_date: date | None = None,
           until_date: date | None = None,
           **_ignored) -> list[Article]:
    """Parse an RSS / Atom / Google Alert feed, return Articles.

    Per-source relevance filtering is applied centrally in `run.py` after this
    function returns — see `apply_relevance_filter` flag on sources in
    sources.yml. This scraper just produces Articles; it doesn't filter.
    """
    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        print(f"  feedparser bozo for {source}: {parsed.bozo_exception}")
        return []

    is_google_alert = "google.com/alerts" in feed_url or "google.co.uk/alerts" in feed_url
    # Google News SEARCH feeds (news.google.com/rss/search?q=...) are a different
    # thing from Google Alerts. Every item links to an opaque news.google.com
    # token that cannot be resolved to the publisher server-side — following it
    # lands on consent.google.com, and the newer CBMi… tokens are not decodable.
    # The feed does carry the real publisher in <source>, so that is used as the
    # article's source label instead of the query name.
    is_google_news = "news.google.com/rss/search" in feed_url
    articles: list[Article] = []
    seen_urls: set[str] = set()

    for e in parsed.entries:
        url = _entry_url(e)
        if is_google_alert:
            url = _unwrap_google_url(url)
        else:
            url = normalise_url(url)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        article_date = _entry_date(e)
        if since_date and article_date and article_date < since_date:
            continue
        if until_date and article_date and article_date > until_date:
            continue

        title = _strip_html(e.get("title") or "")
        text = _strip_html(_entry_text(e))

        # For Google Alerts (which aggregate many publishers behind one feed),
        # use the article's domain as `source` so the dashboard shows the real
        # publisher rather than the alert's name. For direct RSS feeds, source
        # stays as the configured name from sources.yml.
        article_source = source
        if is_google_alert:
            article_source = _domain_as_source(url) or source
        # NOTE: the publisher IS available here as e["source"]["title"]
        # ("Belfast Telegraph", "Law Society of Scotland"), and an earlier
        # version used it as the article's source. That was reverted: streams
        # and places are both mapped BY SOURCE NAME in config/domain.yml, so
        # relabelling to the publisher meant google_news_wales never appeared
        # in the data and all 133 items fell through to place="Global" —
        # defeating the only Wales/NI/Scotland coverage in the roster.
        # The query name is kept as the source so routing works; the publisher
        # is carried in `extra` below, and surfacing it in the dashboard needs
        # a column of its own rather than overloading `source`.

        articles.append(Article(
            url=url,
            title=title,
            article_date=article_date,
            source=article_source,
            source_type=("google_alert" if is_google_alert
                         else "google_news" if is_google_news else "rss"),
            text=text,
            text_clean=build_text_clean(title, text),
            extra=({"alert_name": source} if is_google_alert
                   else {"query_name": source,
                         "publisher": ((e.get("source") or {}).get("title") or "").strip()}
                   if is_google_news else {}),
        ))

    return articles
