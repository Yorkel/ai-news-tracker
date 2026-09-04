"""
web/auth.py — password gate for the FastAPI dashboard.

The Render URL is public, and every action (keep, reject, move) writes to the
database, so the app cannot be left open. This is a signed-cookie session:
one password, set as LOGIN_PASSWORD in the environment.

Fails CLOSED. With no LOGIN_PASSWORD set the app refuses every request
rather than defaulting to open, because a public URL is the wrong place to
guess in the permissive direction.

Local runs can skip it with TRACKER_NO_AUTH=1 in .env; Render does not read
.env, so the deployed app is always gated.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

COOKIE = "tracker_session"
_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _password() -> str | None:
    # CURATOR_PASSWORD is the old name, still read so an already-deployed
    # service keeps working if it was set before the rename.
    v = os.environ.get("LOGIN_PASSWORD") or os.environ.get("CURATOR_PASSWORD")
    return v if v else None


def _serializer() -> URLSafeSerializer:
    # The password doubles as the signing key: changing it invalidates every
    # existing session, which is the behaviour you want from a password change.
    secret = os.environ.get("SESSION_SECRET") or _password() or "unset"
    return URLSafeSerializer(secret, salt="tracker-auth")


def _no_auth() -> bool:
    return str(os.environ.get("TRACKER_NO_AUTH", "")).strip().lower() in {"1", "true", "yes"}


def is_signed_in(request: Request) -> bool:
    if _no_auth():
        return True
    raw = request.cookies.get(COOKIE)
    if not raw:
        return False
    try:
        return _serializer().loads(raw) == "ok"
    except BadSignature:
        return False


def issue_cookie(response, ) -> None:
    response.set_cookie(
        COOKIE, _serializer().dumps("ok"),
        max_age=_MAX_AGE, httponly=True, samesite="lax",
        secure=bool(os.environ.get("RENDER")),   # HTTPS-only once deployed
    )


def check(password: str) -> bool:
    expected = _password()
    if not expected:
        return False
    return hmac.compare_digest(str(password), expected)


LOGIN_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>News Tracker</title>
<style>
body{margin:0;background:#FFF8F2;color:#3B2154;display:flex;align-items:center;
 justify-content:center;height:100vh;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.box{width:340px;border-left:4px solid #F2683C;padding:4px 0 4px 16px}
h1{margin:0;font-size:24px;font-weight:700}
p{margin:3px 0 20px;color:#8A6E8C;font-size:13.5px}
input{width:100%;padding:9px 11px;border:1px solid #F0D9C7;border-radius:6px;font-size:14px}
button{width:100%;margin-top:9px;padding:9px;border:0;border-radius:6px;background:#F2683C;
 color:#fff;font-size:14px;font-weight:600;cursor:pointer}
.err{color:#C2325C;font-size:13px;margin-top:9px}
</style></head><body><div class="box">
<h1>Louise&#39;s AI News Tracker</h1>
<p>Governance, geopolitics, safety, research, deployment</p>
<form method="post" action="/login">
<input type="password" name="password" placeholder="Password" autofocus>
<button type="submit">Enter</button>
</form>
__ERROR__
</div></body></html>"""


def login_page(error: str = "") -> HTMLResponse:
    html = LOGIN_HTML.replace(
        "__ERROR__", f'<div class="err">{error}</div>' if error else "")
    return HTMLResponse(html, status_code=401 if error else 200)


def require(request: Request):
    """Return None if signed in, else a response to send instead."""
    if is_signed_in(request):
        return None
    if _password() is None:
        return HTMLResponse(
            "<p style='font:15px sans-serif;padding:40px'>No login details are "
            "set up yet, so this dashboard cannot be unlocked.</p>", status_code=503)
    return RedirectResponse("/login", status_code=303)
