"""Pull the dashboard's "Notes to self" box into a file you can read in the repo.

The dashboard runs on Render, where the filesystem is ephemeral and there is
no access to the git working tree, so the box writes to the database. This
brings them here.

    python scripts/ideas.py              # write config/ideas.yml
    python scripts/ideas.py --clear      # ...and mark them reviewed

--clear is separate on purpose: read the file first, act on it, then clear.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from web import data as D  # noqa: E402

OUT = ROOT / "config" / "ideas.yml"
SECTIONS = [("source", "Sources to add"), ("bug", "Things that look broken"),
            ("thought", "Thoughts")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true",
                    help="mark everything written out as reviewed")
    args = ap.parse_args()

    ideas = D.open_ideas()
    if not ideas:
        print("Nothing waiting.")
        return 0

    lines = ["# Written from the dashboard's Notes to self box.",
             "# Read, act, then: python scripts/ideas.py --clear", ""]
    for kind, heading in SECTIONS:
        rows = [i for i in ideas if i["kind"] == kind]
        if not rows:
            continue
        lines.append(f"{heading.lower().replace(' ', '_')}:")
        for r in rows:
            # Block scalars, so an idea containing a colon or a quote is not a
            # YAML parse error later.
            lines.append(f"  - |-   # {r['created_at']:%d %b %Y}")
            for ln in r["body"].splitlines() or [""]:
                lines.append(f"      {ln}")
        lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"{len(ideas)} written to {OUT.relative_to(ROOT)}")

    if args.clear:
        n = D.close_ideas([i["id"] for i in ideas])
        print(f"{n} marked reviewed.")
    else:
        print("Still open. Run again with --clear once you have acted on them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
