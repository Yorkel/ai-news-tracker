"""
news_sitemap_adapter.py
Ingest a Google News sitemap (<urlset> with news:news entries) as Articles.

Why this exists
---------------
Some publishers serve no RSS at all. The Business Post advertises /feed/ in its
homepage <link rel="alternate">, but that URL returns the site's HTML shell —
the feed is disabled — while /news-sitemap.xml carries 106 recent articles with
title and publication date. gov.scot, NFER and IPPR are the same shape: no feed,
a live sitemap.

A Google News sitemap gives URL, title and date, which is everything the
pipeline needs to create an Article. It does NOT give body text, so `text` is
left empty and run.py's body backfill fetches the page — the same path an RSS
source with a headline-only feed already takes.

Same interface as rss_adapter.scrape(), so a source only needs:

    - name: business_post
      type: web
      scraper: src.scraping.news_sitemap_adapter
      params: {feed_url: "https://www.businesspost.ie/news-sitemap.xml"}
"""

from __future__ import annotations

import re
from datetime import date, datetime

from src.scraping.common import (
    Article,
    DEFAULT_HEADERS,
    build_text_clean,
    http_get,
    normalise_url,
)

# Namespaced tags vary in prefix between publishers, so match on local name.
_URL_BLOCK = re.compile(r"<url>(.*?)</url>", re.S | re.I)
_LOC = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_TITLE = re.compile(r"<(?:\w+:)?title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</(?:\w+:)?title>", re.S | re.I)
_PUBDATE = re.compile(r"<(?:\w+:)?publication_date>\s*(.*?)\s*</(?:\w+:)?publication_date>", re.S | re.I)
_LASTMOD = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.S | re.I)


def _parse_date(raw: str) -> date | None:
    """Parse a W3C datetime as used in sitemaps (date, or date + time + zone)."""
    if not raw:
        return None
    s = raw.strip()
    # Trailing Z is not understood by fromisoformat before 3.11 in all forms.
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s[:len(fmt) + 6], fmt).date()
        except ValueError:
            continue
    return None


def scrape(*, source: str, feed_url: str,
           since_date: date | None = None,
           until_date: date | None = None,
           **_ignored) -> list[Article]:
    """Fetch a news sitemap and return Articles. Filtering happens in run.py."""
    try:
        resp = http_get(feed_url, headers=DEFAULT_HEADERS)
    except Exception as e:
        print(f"  sitemap fetch failed for {source}: {str(e)[:120]}")
        return []
    if resp is None or getattr(resp, "status_code", 0) != 200:
        code = getattr(resp, "status_code", "?")
        print(f"  sitemap HTTP {code} for {source}")
        return []

    xml = resp.text or ""
    if "<urlset" not in xml.lower():
        print(f"  {source}: not a sitemap (no <urlset>) — got {len(xml)} chars")
        return []

    out: list[Article] = []
    seen: set[str] = set()
    for block in _URL_BLOCK.findall(xml):
        loc = _LOC.search(block)
        if not loc:
            continue
        url = normalise_url(loc.group(1).strip())
        if not url or url in seen:
            continue

        d = _PUBDATE.search(block) or _LASTMOD.search(block)
        article_date = _parse_date(d.group(1)) if d else None
        if since_date and article_date and article_date < since_date:
            continue
        if until_date and article_date and article_date > until_date:
            continue

        t = _TITLE.search(block)
        title = (t.group(1).strip() if t else "")
        if not title:
            # A sitemap entry with no news:title is a plain URL record, not an
            # article — skip rather than storing an untitled row.
            continue

        seen.add(url)
        out.append(Article(
            url=url,
            title=title,
            article_date=article_date,
            source=source,
            source_type="web",
            text="",          # sitemaps carry no body; run.py backfills it
            text_clean=build_text_clean(title, ""),
        ))
    return out
