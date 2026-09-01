"""
News Tracker Curator Dashboard
"""

# Streamlit Cloud runs `streamlit run dashboard/app.py` which sets sys.path[0]
# to dashboard/, not the repo root. Without the next 3 lines, every
# `from dashboard.<…> import` raises ModuleNotFoundError.
import sys
import base64
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd

from dashboard.config import NAVY
from dashboard.styles import get_css
from dashboard.data import (
    load_classified_articles,
    init_session_state, record_feedback,
)
from dashboard.pages import triage, select_categories, draft, sources, thoughts_page
from dashboard.palette import DUSK_DEEP, DUSK_MUTED, DUSK_TEXT, MUTED, style
from dashboard.gate import require_password
from dashboard import streams as S
from dashboard import thoughts as TH
from dashboard.data import record_source_suggestion, load_stream_overrides, load_decisions
from dashboard import export as X


def main():
    st.set_page_config(
        page_title="News Tracker",
        page_icon="\U0001f4f0",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(get_css(), unsafe_allow_html=True)

    # Hide the sidebar entirely (the toggle chevron + the panel itself).
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    div[data-testid="collapsedControl"] { display: none !important; }
    /* Pull main content flush with the viewport top so the grey header bar
       hugs the top of the window with no Streamlit whitespace above it. */
    .block-container { padding-top: 1rem !important; }
    /* Hide Streamlit's "Press ↵ to submit" helper text under text inputs. */
    [data-testid="InputInstructions"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    # Header bar. Previously this rendered ONLY when dashboard/logo.png existed,
    # and it does not, so the site had no title at all. The title is now always
    # shown; the logo is used alongside it if the file is ever added.
    _logo_path = Path(__file__).parent / "logo.png"
    _logo_html = ""
    if _logo_path.exists():
        _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
        _logo_html = (
            f"<img src='data:image/png;base64,{_logo_b64}' "
            f"style='height:52px;margin-right:18px;'/>"
        )
    _header_html = (
        f"<div style=\"background:{NAVY};padding:16px 28px;"
        f"margin:-1rem -2rem 18px -2rem;display:flex;align-items:center;"
        f"border-bottom:1px solid {DUSK_DEEP};\">"
        f"{_logo_html}"
        f"<div>"
        f"<div style=\"color:{DUSK_TEXT};font-size:22px;font-weight:700;"
        f"letter-spacing:-0.2px;line-height:1.1;\">Louise&#39;s AI News Tracker</div>"
        f"<div style=\"color:{DUSK_MUTED};font-size:13px;margin-top:3px;\">"
        f"Governance, geopolitics, safety, research, deployment</div>"
        f"</div></div>"
    )
    st.markdown(_header_html, unsafe_allow_html=True)

    # Two DIFFERENT kinds of destination, so two separate controls:
    #   STREAM_NAV — content lanes. "Which articles am I looking at?"
    #   TOOL_NAV   — workflow steps acting across the whole week, whatever lane
    #                you came from. "What am I doing with them?"
    # One flat row implied Sources was a sixth lane of articles, which it is not.
    # "all" is a pseudo-stream: it is not in config/domain.yml, it just skips
    # the per-stream filter so every lane is shown together.
    STREAM_NAV = ["stream:all"] + [f"stream:{s}" for s in S.ORDER]
    TOOL_NAV = ["Select Categories", "Newsletter Draft", "Thoughts", "Sources"]
    NAV = STREAM_NAV + TOOL_NAV
    NAV_LABELS = {f"stream:{s}": S.SHORT[s] for s in S.ORDER}
    NAV_LABELS["stream:all"] = "All"
    NAV_LABELS.update({
        "Select Categories": "Categorise",
        "Newsletter Draft": "Draft newsletter",
        "Thoughts": "Thoughts",
        "Sources": "Manage sources",
    })

    # Full-page gate. Restored 2026-08-31 when the app went onto a public
    # Streamlit Cloud URL: without it, anyone with the link could read the
    # articles and notes AND use every action button. require_password() calls
    # st.stop() until the password is entered, so nothing below runs and the
    # database is never queried.
    require_password()

    if "current_page" not in st.session_state:
        st.session_state.current_page = f"stream:{S.ORDER[0]}"
    cur = st.session_state.current_page

    # Make the step buttons larger + bolder so the workflow order reads clearly.
    st.markdown("""
    <style>
    [data-testid="stSegmentedControl"] button {
        font-size: 15px !important;
        font-weight: 600 !important;
        padding: 8px 22px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Top row: page nav on the left, login popover on the right ────────────
    col_nav, col_add, col_think = st.columns([5, 1.2, 1.2])
    with col_nav:
        # Button-like segmented control reading "Step 1 / 2 / 3" so the curator
        # sees the workflow order at a glance.
        choice = st.segmented_control(
            "Streams", STREAM_NAV,
            format_func=lambda x: NAV_LABELS.get(x, x),
            default=cur if cur in STREAM_NAV else None,
            label_visibility="collapsed",
            key="_nav_streams",
        )
        if choice and choice != cur:
            st.session_state.current_page = choice
            st.rerun()
    with col_add:
        # Available on every page and without logging in: capturing a source the
        # moment the curator thinks of it matters more than gating the form.
        with st.popover("➕ Add source", use_container_width=True):
            st.caption(
                "Goes to config/pending_sources.yml for review. "
                "Nothing starts scraping until it is promoted by hand."
            )
            with st.form("_suggest_source", clear_on_submit=True):
                s_name = st.text_input("Source name *", placeholder="e.g. Lawfare")
                s_url = st.text_input("URL", placeholder="https://…")
                s_stream = st.selectbox(
                    "Stream", [""] + list(S.ORDER),
                    format_func=lambda x: "— not sure —" if x == "" else S.SHORT[x],
                )
                s_cov = st.text_input("What does it cover?", placeholder="e.g. national security law")
                s_notes = st.text_area("Notes", placeholder="Why it is worth tracking", height=70)
                sent = st.form_submit_button("Save to holding file", type="primary",
                                             use_container_width=True)
            if sent:
                if not s_name.strip():
                    st.error("A source name is required.")
                else:
                    r = record_source_suggestion(s_name, s_url, s_stream, s_cov, s_notes)
                    if r["file"]:
                        st.success(f"Saved “{s_name.strip()}” to config/pending_sources.yml")
                    elif r["db"]:
                        st.warning("Saved to the database, but the holding file could not be written.")
                    else:
                        st.error("Could not save the suggestion.")


    with col_think:
        # Always available, on every page: the point is to catch a thought the
        # moment it occurs, not to navigate somewhere first. The stream you are
        # on is recorded automatically as context.
        _n = TH.count()
        with st.popover(f"💭 Thought{f' ({_n})' if _n else ''}", use_container_width=True):
            st.caption("Saved to data/thoughts.json under today's date.")
            with st.form("_thought_form", clear_on_submit=True):
                _txt = st.text_area(
                    "Thought", height=110, label_visibility="collapsed",
                    placeholder="What just occurred to you…",
                )
                _sent = st.form_submit_button(
                    "Save", type="primary", use_container_width=True,
                )
            if _sent:
                _cur = st.session_state.get("current_page", "")
                _stream = _cur.split(":", 1)[1] if _cur.startswith("stream:") else ""
                if TH.add(_txt, stream=_stream):
                    st.success("Saved.")
                    st.rerun()
                elif not _txt.strip():
                    st.error("Nothing to save.")
                else:
                    st.error("Could not write data/thoughts.json.")

    # Secondary: workflow tools. Visually subordinate to the stream row above,
    # so it reads as "these act on what you triaged" rather than "another lane
    # of articles".
    st.markdown(style("""
    <style>
    .tool-nav [data-testid="stSegmentedControl"] button {
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 3px 13px !important;
        color: {MUTED} !important;
    }
    </style>
    """), unsafe_allow_html=True)
    st.markdown('<div class="tool-nav"></div>', unsafe_allow_html=True)
    col_tools, _tool_spacer = st.columns([4, 3])
    with col_tools:
        st.caption("Then, across all streams:")
        tool_choice = st.segmented_control(
            "Tools", TOOL_NAV,
            format_func=lambda x: NAV_LABELS.get(x, x),
            default=cur if cur in TOOL_NAV else None,
            label_visibility="collapsed",
            key="_nav_tools",
        )
        if tool_choice and tool_choice != cur:
            st.session_state.current_page = tool_choice
            st.rerun()

    st.markdown("---")

    # The pipeline status banner was removed on 2026-09-01. It reported how
    # many of the week's articles had no summary, which is not a problem worth
    # a banner: those articles are listed and fully triageable, and a summary
    # is optional. Summaries are generated per-article from the Triage cards.
    # week_processing_status() is kept in data.py for anything that wants it.

    page = st.session_state.current_page

    df = load_classified_articles()

    if df.empty:
        st.error("No classified articles found in Supabase. Run the inference pipeline (s07 → classify_via_api → s10) to populate `classify_newsletter`.")
        st.stop()

    if "article_date" in df.columns:
        # article_date from Supabase is ISO (YYYY-MM-DD). Parsing ISO with
        # dayfirst=True mangles it (2026-06-11 -> 6 Nov) on recent pandas, which
        # broke the week filters. Parse ISO directly, then format for display.
        df["article_date"] = pd.to_datetime(df["article_date"], errors="coerce").dt.strftime("%d-%m-%Y")

    init_session_state()

    # Curator moves (curator_decisions.stream_override) beat the derived stream.
    df = S.add_stream_column(df, load_stream_overrides())
    df = S.add_place_column(df)

    if page.startswith("stream:"):
        stream_id = page.split(":", 1)[1]
        is_all = stream_id == "all"
        _title = "All streams" if is_all else S.DISPLAY.get(stream_id, stream_id)
        _desc = ("Every lane together, newest first."
                 if is_all else S.DESCRIPTION.get(stream_id, ""))
        st.markdown(
            f"### {_title}\n"
            f"<span style='color:{MUTED};font-size:13px;'>{_desc}</span>",
            unsafe_allow_html=True,
        )
        lane = df if is_all else df[df["stream"] == stream_id]

        # Geography filter — composes with the stream rather than replacing it.
        # Only places actually present in this lane are offered, so the control
        # never shows an option that returns nothing.
        present = [p for p in S.PLACE_ORDER if p in set(lane.get("place", []))]
        if present:
            pick = st.segmented_control(
                "Place", ["All"] + present, default="All",
                label_visibility="collapsed", key=f"_place_{stream_id}",
            )
            if pick and pick != "All":
                lane = lane[lane["place"] == pick]

        # Purpose 1: the reading list. One row per kept article, this lane only.
        kept = X.kept_frame(lane, load_decisions(),
                            stream=None if is_all else stream_id)
        c_dl, c_note = st.columns([1.4, 4])
        with c_dl:
            st.download_button(
                f"⬇ CSV ({len(kept)} kept)",
                X.to_csv_bytes(kept),
                file_name=X.filename(None if is_all else stream_id),
                mime="text/csv",
                use_container_width=True,
                disabled=kept.empty,
                help="Articles you kept. Keep some first if this is empty.",
            )
        with c_note:
            st.caption(
                "Kept articles only — the week's reading list."
                if is_all else
                "Kept articles only — the week's reading list for this stream. "
                "Every stream in one file is on **Draft newsletter**."
            )

        if lane.empty:
            st.info(
                "Nothing here yet."
                if is_all else
                "No articles in this stream yet. "
                "Sources are assigned to streams in config/domain.yml."
            )
        else:
            triage.render(lane)
    elif page == "Select Categories":
        select_categories.render(df)
    elif page == "Newsletter Draft":
        draft.render(df)
    elif page == "Thoughts":
        thoughts_page.render(df)
    elif page == "Sources":
        sources.render(df)

    # ── Feedback on dashboard (every page) ──────────────────────────────────
    auth = bool(st.session_state.get("authenticated"))
    st.markdown("---")
    if page == "Sources":
        st.markdown("### 💬 Feedback on sources")
        _feedback_placeholder = ("e.g. \"We're missing source X\" / \"Source Y has "
                                 "stopped appearing\" / \"Can we add Z?\"")
    else:
        st.markdown("### 💬 Feedback on dashboard design & functionality")
        _feedback_placeholder = ("e.g. \"The Triage page is too slow\" / \"I can't "
                                 "find X\" / \"Why does the source filter not include Y?\"")
    feedback_text = st.text_area(
        "Feedback",
        key="_feedback_box",
        height=110,
        placeholder=_feedback_placeholder,
        label_visibility="collapsed",
        disabled=not auth,
    )
    if st.button("Send feedback", key="_feedback_submit", disabled=not auth, type="primary"):
        if feedback_text and feedback_text.strip():
            record_feedback(feedback_text.strip())
            st.session_state["_feedback_box"] = ""
            st.success("Feedback sent. Thank you.")
            st.rerun()
        else:
            st.warning("Feedback is empty.")


main()
