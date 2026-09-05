"""
web/app.py — FastAPI dashboard.

Replaces the Streamlit app. Streamlit re-runs the entire script on every
interaction, so a week of articles meant re-rendering hundreds of widgets per
click over a websocket; that was the latency, and it is architectural rather
than something tuning could fix.

This renders plain HTML server-side. A click is a form POST and a redirect:
nothing re-renders except the page you asked for.

Run:  .venv/bin/uvicorn web.app:app --reload --port 8000
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import (HTMLResponse, RedirectResponse, Response,
                               StreamingResponse)
from fastapi.templating import Jinja2Templates

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from dashboard import streams as S       # noqa: E402
from web.labels import display as source_display  # noqa: E402
from web import auth                     # noqa: E402
from web import data as D                # noqa: E402

BASE = Path(__file__).resolve().parent
app = FastAPI(title="AI News Tracker")
templates = Jinja2Templates(directory=str(BASE / "templates"))

PER_PAGE = 25

# Sentinel week meaning "do not filter by date at all".
ALL_TIME = -1


def _week_range(weeks: list, week: int):
    """Return (index, date range) for a requested week. None range = all time."""
    if week == ALL_TIME:
        return ALL_TIME, None
    idx = max(0, min(week, len(weeks) - 1))
    return idx, (weeks[idx][0], weeks[idx][1])


def _build() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=str(BASE.parent), capture_output=True,
                              text=True, timeout=4).stdout.strip() or "?"
    except Exception:
        return "?"


BUILD = _build()


def _spotify_search(show: str, title: str) -> str:
    """A Spotify search for one episode.

    The feeds point at whoever hosts the audio — acast, buzzsprout,
    transistor, art19 — never at Spotify, so there is no episode link to
    reuse. A search on the show plus the episode title lands on the episode
    without needing API credentials, and degrades to the show page rather
    than to nothing when the title does not match exactly.
    """
    # Leading episode numbers ("344 Data Vampires", "#255 - Gemini") are
    # numbering from the host, and only ever hurt the match.
    clean = re.sub(r"^[#\d]+[\s.\-–—:]+", "", (title or "").strip())
    return "https://open.spotify.com/search/" + quote(f"{show} {clean}"[:180])


def _split_summary(text: str | None) -> tuple[str, str]:
    """Separate the factual summary from the 'Why this matters' paragraph."""
    t = (text or "").strip()
    if not t:
        return "", ""
    marker = "Why this matters:"
    if marker in t:
        head, _, tail = t.partition(marker)
        return head.strip(), tail.strip()
    return t, ""


@app.get("/", response_class=HTMLResponse)
def index(request: Request, stream: str = "all", place: str = "All",
          status: str = "pending", week: int = 0, q: str = "", page: int = 1):
    # Default to the unsorted pile. Once something is kept or rejected it has
    # been dealt with, so it leaves the list; ?status=kept still works if you
    # want to look back at what you chose.
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    weeks = D.week_options()
    week_idx, wk = _week_range(weeks, week)

    counts = D.stream_counts(wk, status)
    offset = (max(page, 1) - 1) * PER_PAGE
    rows, total = D.fetch_articles(stream, place, wk, status, q, offset, PER_PAGE)

    for r in rows:
        r["source_label"] = source_display(r["source"])
        r["stream_label"] = S.SHORT.get(r["stream"], r["stream"])
        r["article_date"] = r["article_date"].strftime("%d %b") if r["article_date"] else ""
        main, why = _split_summary(r.get("summary"))
        r["summary_main"], r["summary_why"] = main, why
        r["spotify"] = (_spotify_search(r["source_label"], r["title"])
                        if r["stream"] == "podcasts" else "")

    notes = D.notes_for([r["url"] for r in rows])
    for r in rows:
        r["notes"] = notes.get(r["url"], [])
    to_sort = D.pending_count(stream, place, wk)
    ideas = D.idea_count()

    tabs = [("all", "All", counts.get("all", 0))] + [
        (s, S.SHORT[s], counts.get(s, 0)) for s in S.ORDER
    ]
    back = str(request.url)
    # Starlette's current signature is (request, name, context); passing
    # (name, context) makes it read the context dict as the template name.
    return templates.TemplateResponse(request, "index.html", {
        "title": "AI News Tracker", "build": BUILD,
        "total_articles": counts.get("all", 0),
        "articles": rows, "total": total, "stream": stream, "place": place,
        "status": status, "q": q, "page": max(page, 1),
        "pages": max(1, -(-total // PER_PAGE)),
        "stream_tabs": tabs, "places": ["All"] + S.PLACE_ORDER,
        "week_idx": week_idx, "to_sort": to_sort,
        "ideas": ideas,
        "week_labels": ([(ALL_TIME, "All time")]
                        + [(i, w[2]) for i, w in enumerate(weeks)]),
        "move_targets": [(s, S.SHORT[s]) for s in S.ORDER],
        "back": back,
    })


def _done(request: Request, back: str):
    """Answer an action.

    The page submits these with fetch, and then removes the card itself, so
    there is nothing to send back and no navigation: that is what keeps your
    scroll position. Without JavaScript the same form posts normally and gets
    the redirect, so the dashboard still works.
    """
    if request.headers.get("x-requested-with") == "fetch":
        return Response(status_code=204)
    return RedirectResponse(back, status_code=303)


@app.post("/act")
def act(request: Request, url: str = Form(...), action: str = Form(...),
        back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    if action == "clear":
        D.clear_decision(url)
    elif action == "newsletter":
        D.set_newsletter(url, True)
    elif action == "unnewsletter":
        D.set_newsletter(url, False)
    else:
        D.set_decision(url, action)
    return _done(request, back)


@app.post("/idea")
def idea(request: Request, body: str = Form(""), back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    D.add_idea(body)
    return _done(request, back)


@app.post("/move")
def move(request: Request, url: str = Form(...), stream: str = Form(""),
         back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    if stream:
        D.set_stream(url, stream)
    return _done(request, back)


@app.get("/digest", response_class=HTMLResponse)
def digest(request: Request, week: int = 0):
    """This week's picks, grouped by category, ready to paste into Substack."""
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    weeks = D.week_options()
    week_idx, wk = _week_range(weeks, week)
    rows = D.digest_rows(wk)

    for r in rows:
        r["source_label"] = source_display(r["source"])
        r["stream_label"] = S.SHORT.get(r["stream"], r["stream"])
        r["article_date"] = r["article_date"].strftime("%d %b") if r["article_date"] else ""
        r["summary_main"], r["summary_why"] = _split_summary(r.get("summary"))
    notes = D.notes_for([r["url"] for r in rows])
    for r in rows:
        r["notes"] = notes.get(r["url"], [])

    # Grouped in the configured category order, so the post reads the same way
    # every week rather than in whatever order the articles arrived.
    groups = [(S.SHORT[s], [r for r in rows if r["stream"] == s]) for s in S.ORDER]
    groups = [(name, items) for name, items in groups if items]

    label = ("All time" if wk is None
             else next((w[2] for i, w in enumerate(weeks) if i == week_idx), ""))
    return templates.TemplateResponse(request, "digest.html", {
        "title": "This week", "build": BUILD, "total_articles": len(rows),
        "groups": groups, "rows": rows, "week_idx": week_idx,
        "week_label": label, "picked": sum(1 for r in rows if r["for_newsletter"]),
        "week_labels": ([(ALL_TIME, "All time")]
                        + [(i, w[2]) for i, w in enumerate(weeks)]),
    })


@app.get("/export.csv")
def export_csv(request: Request, stream: str = "all", week: int = 0,
               status: str = "kept"):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    weeks = D.week_options()
    _, wk = _week_range(weeks, week)
    # "all" is passed through rather than converted to None, so the export
    # holds exactly what the All tab holds — papers excluded.
    # status=newsletter exports just this week's picks; anything else keeps
    # the old behaviour of exporting everything kept.
    rows = D.kept_rows(wk, stream, status if status == "newsletter" else "kept")
    notes = D.notes_for([r["url"] for r in rows])

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "place", "published", "source", "title", "url",
                "summary", "why_it_matters", "my_notes"])
    for r in rows:
        summary, why = _split_summary(r.get("summary"))
        # Several notes on one article are joined rather than spread across
        # rows, so one article stays one line in the reading list.
        mine = " | ".join(n["note"] for n in notes.get(r["url"], []))
        w.writerow([r["stream"], r["place"], r["article_date"],
                    source_display(r["source"]), r["title"], r["url"],
                    summary, why, mine])
    buf.seek(0)
    # The papers pile is a separate reading list, so it gets a separate name
    # rather than a file that looks like the news export.
    stem = ("newsletter" if status == "newsletter"
            else "papers" if stream == "papers" else f"reading-list_{stream}")
    span = "all-time" if wk is None else f"{wk[0]:%Y-%m-%d}"
    name = f"{stem}_{span}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/healthz")
def healthz():
    return {"ok": True, "build": BUILD}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if auth.is_signed_in(request):
        return RedirectResponse("/", status_code=303)
    return auth.login_page()


@app.post("/login")
def login_submit(password: str = Form("")):
    if not auth.check(password):
        return auth.login_page("Wrong password." if password else "Enter the password.")
    resp = RedirectResponse("/", status_code=303)
    auth.issue_cookie(resp)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.post("/note")
def note(request: Request, url: str = Form(...), note: str = Form(""),
         back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    D.add_note(url, note)
    return _done(request, back)


@app.post("/note/delete")
def note_delete(request: Request, note_id: str = Form(...), back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    D.delete_note(note_id)
    return _done(request, back)
