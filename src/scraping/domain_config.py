"""
domain_config.py
Loads config/domain.yml for the scraping/relevance layer.

The dashboard has its own loader (dashboard/config.py) for label display.
This one exposes the `relevance` and `geography` sections, which relevance.py
reads so that retargeting the tracker to a new domain is a YAML edit rather
than a code edit.

Every getter takes a fallback so the module degrades to the hard-coded
defaults in relevance.py if config/domain.yml is missing or partial.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOMAIN_CONFIG = _PROJECT_ROOT / "config" / "domain.yml"


def _load() -> dict[str, Any]:
    if not _DOMAIN_CONFIG.exists():
        return {}
    return yaml.safe_load(_DOMAIN_CONFIG.read_text(encoding="utf-8")) or {}


_CONFIG = _load()
_RELEVANCE = _CONFIG.get("relevance", {}) or {}
_GEOGRAPHY = _CONFIG.get("geography", {}) or {}


def tuple_from(section: str, key: str, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Read a list of strings out of domain.yml, lowercased and de-duplicated.

    Returns `fallback` only when the key is absent. An explicitly empty list in
    the YAML is honoured as empty — that is how a filter gets switched off.
    """
    source = {"relevance": _RELEVANCE, "geography": _GEOGRAPHY}.get(section, {})
    if key not in source:
        return fallback
    values = source.get(key) or []
    seen: dict[str, None] = {}
    for v in values:
        s = str(v).strip().lower()
        if s:
            seen[s] = None
    return tuple(seen)


def flag(section: str, key: str, fallback: bool = False) -> bool:
    source = {"relevance": _RELEVANCE, "geography": _GEOGRAPHY}.get(section, {})
    return bool(source.get(key, fallback))
