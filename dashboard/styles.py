"""
Custom CSS for dashboard styling.
"""

from .palette import (
    ACCENT, ACCENT_HOVER, ACCENT_SOFT, DUSK, DUSK_MUTED, DUSK_TEXT,
    GOLD, GOLD_SOFT, INFO, INFO_SOFT, INK, INK_SOFT, KEEP_SOFT,
    REJECT, REJECT_HOVER, REJECT_SOFT, RULE, SURFACE_ALT, SURFACE_SUNK,
)

NAVY, TEAL, MID_BLUE = DUSK, ACCENT, INK_SOFT


def get_css():
    return f"""
<style>
    /* Hide Streamlit's auto-generated multipage nav (we use a custom radio
       in app.py - the dashboard/pages/ folder is just a Python module). */
    [data-testid="stSidebarNav"] {{
        display: none;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {NAVY};
    }}
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    /* Sidebar buttons need their own text colour so they're not white-on-pale */
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"],
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] * {{
        color: {REJECT} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"],
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] * {{
        color: white !important;
    }}
    [data-testid="stSidebar"] .stRadio label {{
        color: {DUSK_MUTED} !important;
    }}
    [data-testid="stSidebar"] .stRadio label:hover {{
        color: {TEAL} !important;
    }}

    /* Headers */
    h1 {{
        color: {NAVY} !important;
    }}
    h2, h3 {{
        color: {MID_BLUE} !important;
    }}

    /* Primary buttons */
    .stButton > button[kind="primary"] {{
        background-color: {TEAL};
        border-color: {TEAL};
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}

    /* Info boxes */
    .stAlert {{
        background-color: {INFO_SOFT};
        border-left-color: {TEAL};
    }}

    /* Progress bar */
    .stProgress > div > div > div {{
        background-color: {TEAL};
    }}

    /* Dividers */
    hr {{
        border-color: {RULE};
    }}

    /* Hide anchor link icons on headers */
    h1 a, h2 a, h3 a {{
        display: none !important;
    }}

    /* Card containers - light background */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {SURFACE_ALT} !important;
        border-radius: 8px !important;
    }}

    /* Download button - light orange */
    [data-testid="stDownloadButton"] button {{
        background-color: {GOLD_SOFT} !important;
        color: {INK} !important;
        border: 1px solid {GOLD} !important;
    }}
    [data-testid="stDownloadButton"] button:hover {{
        background-color: {SURFACE_SUNK} !important;
    }}

    /* All buttons - same height, larger text */
    [data-testid="stButton"] button {{
        min-height: 50px !important;
        font-size: 16px !important;
    }}

    /* Primary buttons - light blue (Category 1 + Manual) */
    [data-testid="stButton"] button[kind="primary"] {{
        background-color: {INFO_SOFT} !important;
        border: 1px solid {INFO} !important;
        color: {INFO} !important;
    }}
    [data-testid="stButton"] button[kind="primary"]:hover {{
        background-color: {SURFACE_SUNK} !important;
    }}

    /* Tertiary buttons - light orange (Category 2) */
    [data-testid="stButton"] button[kind="tertiary"] {{
        background-color: {ACCENT_SOFT} !important;
        border: 1px solid {ACCENT} !important;
        color: {ACCENT_HOVER} !important;
    }}
    [data-testid="stButton"] button[kind="tertiary"]:hover {{
        background-color: {SURFACE_SUNK} !important;
    }}

    /* Secondary buttons - light red (Reject) */
    [data-testid="stButton"] button[kind="secondary"] {{
        background-color: {REJECT_SOFT} !important;
        border: 1px solid {REJECT} !important;
        color: {REJECT} !important;
    }}
    [data-testid="stButton"] button[kind="secondary"]:hover {{
        background-color: {REJECT_HOVER} !important;
        color: white !important;
    }}
</style>
"""
