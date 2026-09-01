"""Legacy source-to-country mapping retained for stored article records."""

from __future__ import annotations

UK_NATIONS = ("eng", "sco", "wal", "nir", "uk")

SOURCE_NATION: dict[str, str] = {
    "welsh_government": "wal",
    "wales_education": "wal",
    "gov.wales": "wal",
    "senedd.wales": "wal",
    "wlga.wales": "wal",
    "hwb.gov.wales": "wal",
    "scotland_news": "sco",
    "education_scotland_alert": "sco",
    "parliament.scot": "sco",
    "education.gov.scot": "sco",
    "cosla.gov.uk": "sco",
    "gov.scot": "sco",
    "nilga.org": "nir",
    "northernireland.gov.uk": "nir",
    "education-ni.gov.uk": "nir",
    "dfe": "eng",
    "schoolsweek": "eng",
    "gov.uk": "uk",
    "bbc.co.uk": "uk",
    "example_feed": "uk",
}


def nation_for_source(source: str | None) -> str:
    """Return the nation/geography code for a source slug or domain. Unknown -> uk."""
    if not source:
        return "uk"
    return SOURCE_NATION.get(source, "uk")
