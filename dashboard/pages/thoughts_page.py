"""Thoughts — browse, export and prune the scratchpad."""

from __future__ import annotations

import json
from datetime import date, timedelta

import streamlit as st

from dashboard import thoughts as T
from dashboard.palette import ACCENT, INK, MUTED, RULE, SURFACE_ALT, style


def render(df=None):
    st.title("Thoughts")

    data = T.load()
    total = sum(len(v) for v in data.values())
    if not total:
        st.info(
            "Nothing yet. Use **💭 Thought** in the top bar to jot something down "
            "as it occurs to you — it saves to `data/thoughts.json`, grouped by date."
        )
        return

    # ── Scope ───────────────────────────────────────────────────────────────
    from src.scraping.common import last_anchor

    wk = last_anchor().isoformat()
    col_a, col_b = st.columns([2, 4])
    with col_a:
        scope = st.radio(
            "Show", ["This week", "Everything"],
            horizontal=True, label_visibility="collapsed", key="_th_scope",
        )
    shown = T.since(wk) if scope == "This week" else data
    n_shown = sum(len(v) for v in shown.values())
    with col_b:
        st.caption(
            f"{n_shown} of {total} thoughts · week starts {wk} · "
            f"stored in data/thoughts.json (gitignored, not backed up by git)"
        )

    # ── Export ──────────────────────────────────────────────────────────────
    c1, c2, _ = st.columns([1.3, 1.3, 3])
    with c1:
        st.download_button(
            "⬇ JSON", json.dumps(shown, indent=2, ensure_ascii=False).encode("utf-8"),
            file_name=f"thoughts_{date.today():%Y-%m-%d}.json",
            mime="application/json", use_container_width=True, disabled=not n_shown,
        )
    with c2:
        st.download_button(
            "⬇ Markdown", T.as_markdown(shown).encode("utf-8"),
            file_name=f"thoughts_{date.today():%Y-%m-%d}.md",
            mime="text/markdown", use_container_width=True, disabled=not n_shown,
            help="Paste straight into a draft.",
        )

    st.markdown("---")

    if not n_shown:
        st.info("Nothing this week yet. Switch to **Everything** to see older thoughts.")
        return

    # ── The thoughts, newest day first ──────────────────────────────────────
    for day in sorted(shown.keys(), reverse=True):
        items = shown[day]
        pretty = date.fromisoformat(day).strftime("%A %-d %B %Y") if _isodate(day) else day
        st.markdown(
            style(f"<div style='color:{{INK}};font-weight:700;font-size:16px;"
                  f"margin:14px 0 6px;'>{pretty}  "
                  f"<span style='color:{{MUTED}};font-weight:400;font-size:13px;'>"
                  f"({len(items)})</span></div>"),
            unsafe_allow_html=True,
        )
        for i, t in enumerate(items):
            col_txt, col_del = st.columns([9, 1])
            with col_txt:
                meta = []
                if t.get("time"):
                    meta.append(t["time"])
                if t.get("stream"):
                    meta.append(t["stream"])
                st.markdown(
                    style(
                        f"<div style='background:{{SURFACE_ALT}};border-left:3px solid {{ACCENT}};"
                        f"padding:8px 12px;margin:4px 0;border-radius:0 4px 4px 0;'>"
                        f"<div style='color:{{MUTED}};font-size:11px;'>{' · '.join(meta)}</div>"
                        f"<div style='color:{{INK}};font-size:14px;white-space:pre-wrap;'>"
                        f"{_esc(t.get('text',''))}</div>"
                        + (
                            f"<div style='color:{{MUTED}};font-size:11px;margin-top:4px;'>"
                            f"↳ {_esc(t.get('article_title',''))}</div>"
                            if t.get("article_title") else ""
                        )
                        + "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                if t.get("article_url"):
                    st.caption(t["article_url"])
            with col_del:
                if st.button("✕", key=f"delth_{day}_{i}", help="Delete this thought"):
                    # Index is against the FULL day list, which `shown` shares by
                    # reference for a whole-day slice — safe because filtering is
                    # by date, never within a day.
                    T.delete(day, i)
                    st.rerun()


def _isodate(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except Exception:
        return False


def _esc(v: str) -> str:
    import html
    return html.escape(str(v or ""))
