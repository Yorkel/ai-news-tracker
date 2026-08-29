"""Shared dashboard constants loaded from config/domain.yml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DOMAIN_CONFIG = _PROJECT_ROOT / "config" / "domain.yml"


def _load_domain_config() -> dict[str, Any]:
    if not _DOMAIN_CONFIG.exists():
        return {}
    return yaml.safe_load(_DOMAIN_CONFIG.read_text(encoding="utf-8")) or {}


_CONFIG = _load_domain_config()
_LABELS = _CONFIG.get("labels", {})

CATEGORY_ORDER = list(_LABELS.get("order", [])) or [
    "policy",
    "research",
    "practice",
    "technology",
    "workforce",
    "other",
]
CATEGORY_LABELS = dict(_LABELS.get("display", {})) or {key: key.replace("_", " ").title() for key in CATEGORY_ORDER}
CATEGORY_SHORT_LABELS = dict(_LABELS.get("short", {})) or CATEGORY_LABELS.copy()
CATEGORY_COLORS = dict(_LABELS.get("colors", {})) or {
    "policy": "#3B6EA8",
    "research": "#4F8A5B",
    "practice": "#8A6FB0",
    "technology": "#2E8C9E",
    "workforce": "#C9793A",
    "other": "#667085",
}

SOURCE_LABELS = {
    "example_feed": "Example Feed",
}

_TLDS = (".co.uk", ".org.uk", ".gov.uk", ".ac.uk", ".com", ".org", ".uk", ".net")


def source_label(src) -> str:
    """Friendly organisation name for a source value."""
    if src is None:
        return ""
    s = str(src).strip()
    if not s or s.lower() in {"nan", "none", "nat"}:
        return ""
    if s in SOURCE_LABELS:
        return SOURCE_LABELS[s]
    base = s
    for tld in _TLDS:
        if base.lower().endswith(tld):
            base = base[: -len(tld)]
            break
    base = base.replace("_", " ").replace(".", " ").strip()
    return base.title() if base else s


NAVY = "#1F2937"
TEAL = "#2E8C9E"
LIGHT_BLUE = "#3B82F6"
MID_BLUE = "#374151"

MS_FORM_URL = os.environ.get("MS_FORM_URL", "")
