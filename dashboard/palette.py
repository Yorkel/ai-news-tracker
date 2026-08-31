"""
palette.py — the single source of truth for dashboard colour.

Sunset palette: warm cream paper, deep dusk-purple ink, and orange/coral
accents, moving through the colours of a sky between sunset and dusk.

Before this file existed the dashboard held ~70 hardcoded hex values spread
across styles.py, app.py and three page modules. Everything now resolves to a
name here, so changing the whole scheme is one edit in one place.

Naming is by ROLE, not by hue — SURFACE/INK/ACCENT rather than CREAM/PURPLE/
ORANGE — so a future palette can be swapped in without the names turning into
lies.

One deliberate exception to the sunset hues: KEEP stays a green (a deep
dusk-teal green, #2E8B6F). Triage is a fast accept/reject loop and green-means-
keep is a strong convention worth more than hue purity. REJECT is a sunset
crimson, so the pair is separated by both hue and lightness.
"""

# ── Surfaces ────────────────────────────────────────────────────────────────
SURFACE = "#FFF8F2"        # page background — warm cream
SURFACE_ALT = "#FDEFE4"    # raised panel — peach
SURFACE_SUNK = "#F6E3D4"   # recessed / hover — deeper peach
RULE = "#F0D9C7"           # hairline borders

# ── Text ────────────────────────────────────────────────────────────────────
INK = "#3B2154"            # headings and body — deep dusk purple
INK_SOFT = "#5C3D6E"       # subheadings
MUTED = "#8A6E8C"          # secondary text — dusty mauve
FAINT = "#C0A8BA"          # disabled / placeholder

# ── Dusk (sidebar and dark blocks) ──────────────────────────────────────────
DUSK = "#4A2A6A"           # sidebar background
DUSK_DEEP = "#2E1741"      # darkest band — header edge
DUSK_TEXT = "#F6DCC6"      # text on dusk
DUSK_MUTED = "#C9A9C4"     # secondary text on dusk

# ── Accents ─────────────────────────────────────────────────────────────────
ACCENT = "#F2683C"         # sunset orange — primary actions
ACCENT_HOVER = "#D9532B"
ACCENT_SOFT = "#FDE4D8"
CORAL = "#E8556E"
GOLD = "#E9A13B"
GOLD_SOFT = "#FDF0DC"

# ── Semantic states ─────────────────────────────────────────────────────────
KEEP = "#2E8B6F"           # accept — dusk green (see module docstring)
KEEP_HOVER = "#24705A"
KEEP_SOFT = "#E4F1EA"
REJECT = "#C2325C"         # reject — sunset crimson
REJECT_HOVER = "#A32549"
REJECT_SOFT = "#FBE2E8"
INFO = "#7B4FA8"           # violet
INFO_HOVER = "#633E8A"
INFO_SOFT = "#EFE6F7"
WARN = GOLD
WARN_SOFT = GOLD_SOFT
PENDING = "#9A8296"        # mauve grey

# ── Backwards-compatible aliases ────────────────────────────────────────────
# app.py and styles.py imported these names from config.py. Kept so nothing
# breaks, but they now point at sunset values.
NAVY = DUSK
TEAL = ACCENT
MID_BLUE = INK_SOFT
LIGHT_BLUE = INFO


def style(text: str) -> str:
    """Substitute {NAME} tokens in `text` with palette values.

    Used instead of f-strings because most of these strings are CSS blocks,
    where the literal braces of a rule body (`.foo { ... }`) would have to be
    doubled to survive f-string formatting — easy to get wrong and hard to
    read. This only touches {UPPER_CASE} tokens that name a palette constant,
    so CSS braces pass through untouched.

    Raises KeyError on an unknown token rather than leaving it in the page:
    a colour name that silently renders as the literal text "{ACCENT}" is
    exactly the bug this helper exists to prevent.
    """
    import re

    _values = {k: v for k, v in globals().items()
               if k.isupper() and isinstance(v, str) and v.startswith("#")}

    def _sub(m):
        name = m.group(1)
        if name not in _values:
            raise KeyError(f"unknown palette colour {{{name}}}")
        return _values[name]

    return re.sub(r"\{([A-Z][A-Z_]{2,})\}", _sub, text)
