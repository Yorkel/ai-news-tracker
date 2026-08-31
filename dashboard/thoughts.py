"""
thoughts.py — the scratchpad.

Somewhere to put a thought the moment it occurs, while triaging. Thoughts are
grouped BY DATE in data/thoughts.json:

    {
      "2026-08-31": [
        {"time": "14:32", "text": "...", "stream": "governance",
         "article_title": "...", "article_url": "..."}
      ]
    }

Date-keyed because the output is a weekly post: "what did I think this week"
is the question being asked of this file, and a date key answers it without
any parsing.

Stored in data/, which is gitignored — thoughts are private working notes and
should not end up in a commit. That also means they are NOT backed up by git;
the Thoughts page has a download button for that.

Writes are atomic (temp file + rename) so an interrupted save cannot leave a
half-written JSON that loses every previous thought.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

THOUGHTS_FILE = Path(__file__).resolve().parents[1] / "data" / "thoughts.json"


def load() -> dict[str, list[dict]]:
    """All thoughts, {date: [thought, ...]}. Never raises — a corrupt or
    missing file yields an empty dict rather than breaking the dashboard."""
    try:
        if not THOUGHTS_FILE.exists():
            return {}
        data = json.loads(THOUGHTS_FILE.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: dict) -> bool:
    """Atomically replace the file. Returns False rather than raising, so a
    failed write surfaces in the UI instead of losing the user's typing to a
    traceback."""
    try:
        THOUGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(THOUGHTS_FILE.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, THOUGHTS_FILE)
        return True
    except Exception:
        return False


def add(text: str, *, stream: str = "", article_title: str = "",
        article_url: str = "", when: datetime | None = None) -> bool:
    """Append one thought under today's date. Empty text is ignored."""
    text = (text or "").strip()
    if not text:
        return False
    now = when or datetime.now()
    day = now.strftime("%Y-%m-%d")
    data = load()
    data.setdefault(day, []).append({
        "time": now.strftime("%H:%M"),
        "text": text,
        "stream": stream or "",
        "article_title": article_title or "",
        "article_url": article_url or "",
    })
    return _save(data)


def delete(day: str, index: int) -> bool:
    """Remove one thought by date and position."""
    data = load()
    items = data.get(day) or []
    if not (0 <= index < len(items)):
        return False
    items.pop(index)
    if items:
        data[day] = items
    else:
        data.pop(day, None)
    return _save(data)


def count() -> int:
    return sum(len(v) for v in load().values())


def dates_desc() -> list[str]:
    """Dates newest first."""
    return sorted(load().keys(), reverse=True)


def since(day: str) -> dict[str, list[dict]]:
    """Thoughts on or after `day` (YYYY-MM-DD) — for pulling one week's worth."""
    return {d: v for d, v in load().items() if d >= day}


def as_markdown(data: dict[str, list[dict]] | None = None) -> str:
    """Render to markdown for pasting into a draft."""
    data = load() if data is None else data
    out: list[str] = []
    for day in sorted(data.keys(), reverse=True):
        out.append(f"## {day}")
        for t in data[day]:
            line = f"- **{t.get('time','')}** {t.get('text','')}"
            if t.get("article_title"):
                line += f"  \n  ↳ _{t['article_title']}_"
                if t.get("article_url"):
                    line += f" — {t['article_url']}"
            out.append(line)
        out.append("")
    return "\n".join(out)


def for_article(url: str) -> list[tuple[str, int, dict]]:
    """Every thought attached to one article, as (date, index, thought).

    The index is the position within that date's list, so the caller can pass
    it straight to delete() without re-deriving it.
    """
    if not url:
        return []
    out: list[tuple[str, int, dict]] = []
    for day, items in load().items():
        for i, t in enumerate(items):
            if t.get("article_url") == url:
                out.append((day, i, t))
    out.sort(key=lambda r: (r[0], r[2].get("time", "")), reverse=True)
    return out
