"""
web/custom_scraper_adapter.py

Thin wrapper around optional per-site custom scrapers.

Each custom scraper module should expose one callable named `scrape_<name>`
or `scrape`, accepting `since_date`, `until_date`, `output_path`, and `append`
keyword arguments where relevant. It should return rows with at least:

    url, title, date, text

Configure per-source via `src/scraping/sources.yml`, for example:

    - name: example_site
      type: web
      scraper: src.scraping.web.custom_scraper_adapter
      params:
        module: src.scraping.web.example_site
"""

from __future__ import annotations

from datetime import date, datetime
from importlib import import_module

from src.scraping.common import Article, normalise_url


def _to_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _find_scrape_function(mod):
    if callable(getattr(mod, "scrape", None)):
        return getattr(mod, "scrape")
    for name in dir(mod):
        if name.startswith("scrape_") and name != "scrape_article" and callable(getattr(mod, name)):
            return getattr(mod, name)
    raise RuntimeError(f"no scrape() or scrape_<name>() function found on {mod.__name__}")


def scrape(*, source: str, module: str,
           since_date: date | None = None, until_date: date | None = None,
           **_ignored) -> list[Article]:
    mod = import_module(module)
    fn = _find_scrape_function(mod)
    rows = fn(since_date=since_date, until_date=until_date,
              output_path=None, append=False) or []

    articles: list[Article] = []
    for r in rows:
        if not r.get("url"):
            continue
        extras = {k: v for k, v in r.items()
                  if k not in ("url", "title", "date", "text")}
        articles.append(Article(
            url=normalise_url(r["url"]),
            title=r.get("title"),
            article_date=_to_date(r.get("date")),
            source=source,
            source_type="web",
            text=r.get("text"),
            extra=extras,
        ))
    return articles
