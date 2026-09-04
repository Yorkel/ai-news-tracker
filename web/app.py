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
import subprocess
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
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


def _build() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=str(BASE.parent), capture_output=True,
                              text=True, timeout=4).stdout.strip() or "?"
    except Exception:
        return "?"


BUILD = _build()


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
          status: str = "all", week: int = 0, q: str = "", page: int = 1):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    weeks = D.week_options()
    week_idx = max(0, min(week, len(weeks) - 1))
    wk = (weeks[week_idx][0], weeks[week_idx][1])

    counts = D.stream_counts(wk)
    offset = (max(page, 1) - 1) * PER_PAGE
    rows, total = D.fetch_articles(stream, place, wk, status, q, offset, PER_PAGE)

    for r in rows:
        r["source_label"] = source_display(r["source"])
        r["stream_label"] = S.SHORT.get(r["stream"], r["stream"])
        r["article_date"] = r["article_date"].strftime("%d %b") if r["article_date"] else ""
        main, why = _split_summary(r.get("summary"))
        r["summary_main"], r["summary_why"] = main, why

    notes = D.notes_for([r["url"] for r in rows])
    for r in rows:
        r["notes"] = notes.get(r["url"], [])
    to_sort = D.pending_count(stream, place, wk)

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
        "week_labels": [(i, w[2]) for i, w in enumerate(weeks)],
        "move_targets": [(s, S.SHORT[s]) for s in S.ORDER],
        "back": back,
    })


@app.post("/act")
def act(request: Request, url: str = Form(...), action: str = Form(...),
        back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    if action == "clear":
        D.clear_decision(url)
    else:
        D.set_decision(url, action)
    return RedirectResponse(back, status_code=303)


@app.post("/move")
def move(request: Request, url: str = Form(...), stream: str = Form(""),
         back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    if stream:
        D.set_stream(url, stream)
    return RedirectResponse(back, status_code=303)


@app.get("/export.csv")
def export_csv(request: Request, stream: str = "all", week: int = 0):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    weeks = D.week_options()
    week_idx = max(0, min(week, len(weeks) - 1))
    wk = (weeks[week_idx][0], weeks[week_idx][1])
    rows = D.kept_rows(wk, None if stream == "all" else stream)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "place", "date", "source", "title", "url", "summary"])
    for r in rows:
        w.writerow([r["stream"], r["place"], r["article_date"], r["source"],
                    r["title"], r["url"], (r.get("summary") or "")])
    buf.seek(0)
    name = f"reading-list_{stream}_{date.today():%Y-%m-%d}.csv"  # noqa: E501
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
    return RedirectResponse(back, status_code=303)


@app.post("/note/delete")
def note_delete(request: Request, note_id: str = Form(...), back: str = Form("/")):
    blocked = auth.require(request)
    if blocked is not None:
        return blocked
    D.delete_note(note_id)
    return RedirectResponse(back, status_code=303)
