"""Write summaries for articles that have none.

591 of the 1,353 articles in the database have body text but no summary: they
were scraped before summarising was wired in, or a run failed partway. The
dashboard shows a bare headline for each of them, and the weekly digest and
the corpus chat both read the summary, so the gap is worth closing once.

    python scripts/backfill_summaries.py --dry-run     # count and cost
    python scripts/backfill_summaries.py --limit 5     # check the output first
    python scripts/backfill_summaries.py               # the rest

Resumable: it only ever selects rows that still have no summary, so it can be
interrupted and re-run without repeating work or paying twice.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

import psycopg                                        # noqa: E402
from psycopg.rows import dict_row                     # noqa: E402

from dashboard import streams as S                    # noqa: E402
from src.inference.summarise import enrich_summary    # noqa: E402
from web.data import _dsn                             # noqa: E402

# Below this the "body" is a teaser or a cookie banner, not an article.
MIN_BODY = 400

SELECT = f"""
    select url, title, source, coalesce(text_clean, text) as body
      from articles
     where (summary is null or summary = '')
       and coalesce(text_clean, text) is not null
       and length(coalesce(text_clean, text)) > {MIN_BODY}
     order by article_date desc nulls last
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with psycopg.connect(_dsn(), row_factory=dict_row) as c, c.cursor() as cur:
        rows = cur.execute(SELECT + (f" limit {args.limit}" if args.limit else "")).fetchall()

    if not rows:
        print("Nothing to do — every article with a body has a summary.")
        return 0

    chars = sum(len(r["body"]) for r in rows)
    print(f"{len(rows)} articles to summarise, {chars/1000:.0f}k characters of body text.")
    if args.dry_run:
        # ~4 chars per token in, ~120 tokens out. gpt-4.1-mini is $0.40/$1.60
        # per million at the time of writing.
        cost = (chars / 4 / 1e6) * 0.40 + (len(rows) * 120 / 1e6) * 1.60
        print(f"Rough cost at gpt-4.1-mini rates: ${cost:.2f}. Not calling the API.")
        return 0

    done = failed = 0
    started = time.time()
    for i, r in enumerate(rows, 1):
        try:
            summary = enrich_summary(
                title=r["title"] or "",
                text=r["body"],
                category=S.SHORT.get(S.assign_stream(r["source"], r["title"])),
            )
        except Exception as e:                     # one bad article must not
            failed += 1                            # end a 591-article run
            print(f"  [{i}/{len(rows)}] FAILED {type(e).__name__}: {r['title'][:60]}")
            continue

        # Committed one at a time so an interrupted run keeps what it paid for.
        with psycopg.connect(_dsn()) as c, c.cursor() as cur:
            cur.execute("update articles set summary = %s where url = %s",
                        (summary, r["url"]))
            c.commit()
        done += 1
        if i % 25 == 0 or i == len(rows):
            rate = i / max(time.time() - started, 1)
            left = (len(rows) - i) / max(rate, 0.01) / 60
            print(f"  [{i}/{len(rows)}] {done} written, {failed} failed, "
                  f"~{left:.0f} min left", flush=True)

    print(f"\nDone. {done} summaries written, {failed} failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
