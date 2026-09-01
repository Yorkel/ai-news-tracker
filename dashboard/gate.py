"""
gate.py — the password gate.

A full-page block, not a permissions flag. Nothing else on the dashboard is
rendered or queried until the password is entered: `require_password()` calls
st.stop() on failure, so the article data is never fetched and never reaches
the browser.

This replaces an earlier design where the whole dashboard was browsable and
only the action buttons were disabled. That was fine on localhost. On a public
Streamlit Cloud URL it is not: the articles, the curator's notes and the
stream assignments were all visible to anyone with the link.

The password is read from, in order:
  1. st.secrets["CURATOR_PASSWORD"]   — Streamlit Cloud, and .streamlit/secrets.toml
  2. os.environ["CURATOR_PASSWORD"]   — .env for local runs

If NEITHER is set the gate FAILS CLOSED and the app refuses to open, rather
than defaulting to open. A missing password is a misconfiguration, and on a
public URL guessing wrong in the permissive direction is unrecoverable.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import streamlit as st

from dashboard.palette import style


def _expected() -> str | None:
    try:
        v = st.secrets["CURATOR_PASSWORD"]
        if v:
            return str(v)
    except Exception:
        pass
    v = os.environ.get("CURATOR_PASSWORD")
    return str(v) if v else None


# Query-param key used to stay signed in across reloads. It holds a hash of
# the password, never the password itself, so the URL cannot be read back into
# a credential. Anyone holding the full URL is nonetheless as good as holding
# the password — which is the same trade-off as any "remember me" cookie, and
# acceptable for a single-curator dashboard.
_REMEMBER_PARAM = "k"


def _token(password: str) -> str:
    return hashlib.sha256(f"news-tracker:{password}".encode()).hexdigest()[:32]


def require_password() -> None:
    """Render the login page and stop, unless already authenticated."""
    if st.session_state.get("authenticated"):
        return

    expected = _expected()

    # Already signed in on this browser? Streamlit clears session_state on every
    # reload, so without this the password would be re-typed on each refresh.
    if expected is not None:
        try:
            if hmac.compare_digest(str(st.query_params.get(_REMEMBER_PARAM, "")),
                                   _token(expected)):
                st.session_state.authenticated = True
                return
        except Exception:
            pass

    st.markdown(style("""
    <style>
    /* The gate owns the whole viewport: no nav, no sidebar, no content. */
    section[data-testid="stSidebar"], div[data-testid="collapsedControl"] { display: none !important; }
    .block-container { max-width: 420px !important; padding-top: 12vh !important; }
    </style>
    """), unsafe_allow_html=True)

    st.markdown(
        style("<div style='border-left:4px solid {ACCENT};padding:2px 0 2px 14px;margin-bottom:22px;'>")
        + style("<div style='color:{INK};font-size:26px;font-weight:700;'>News Tracker</div>")
        + style("<div style='color:{MUTED};font-size:14px;'>AI governance, safety, geopolitics and research</div>")
        + "</div>",
        unsafe_allow_html=True,
    )

    if expected is None:
        st.error(
            "No CURATOR_PASSWORD is configured, so the dashboard cannot be "
            "unlocked. Set it in the app's secrets (Streamlit Cloud) or in .env."
        )
        st.stop()

    with st.form("_gate", clear_on_submit=False):
        pwd = st.text_input(
            "Password", type="password", label_visibility="collapsed",
            placeholder="Password",
        )
        remember = st.checkbox("Stay signed in on this browser", value=True)
        ok = st.form_submit_button("Enter", type="primary", use_container_width=True)

    if ok:
        # compare_digest rather than == so the check does not leak the password
        # length or prefix through timing.
        if hmac.compare_digest(str(pwd), expected):
            st.session_state.authenticated = True
            if remember:
                # Survives reload and can be bookmarked.
                st.query_params[_REMEMBER_PARAM] = _token(expected)
            st.rerun()
        else:
            st.error("Wrong password." if pwd else "Enter the password.")

    st.stop()
