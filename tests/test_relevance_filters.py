"""Tests for the relevance filter: the layer that decides what enters the tracker.

Covers the config-driven filter lists (config/domain.yml), the universal
hard-blocks, the fail-closed approved-domain gate, and the fact that the
inherited UK country veto is OFF for this tracker — overseas AI coverage is
core scope, not noise."""

from src.scraping.relevance import (
    DEFAULT_KEYWORDS,
    compile_keyword_patterns,
    is_approved_domain,
    is_blocked_domain,
    is_blocked_url_pattern,
    is_non_uk_content,
    matched_keywords,
)


def test_social_and_aggregator_domains_are_blocked():
    for url in (
        "https://twitter.com/someone/status/1",
        "https://www.facebook.com/post/1",
        "https://www.msn.com/en-gb/news/ai-story",
    ):
        assert is_blocked_domain(url) is True, url


def test_primary_sources_are_not_blocked():
    for url in (
        "https://www.gov.uk/government/news/ai-white-paper",
        "https://openai.com/index/some-release",
        "https://arxiv.org/abs/2401.00001",
    ):
        assert is_blocked_domain(url) is False, url


def test_lifestyle_sections_are_blocked_by_path():
    assert is_blocked_url_pattern("https://example.com/sport/football/story") is True
    assert is_blocked_url_pattern("https://example.com/celebrity/gossip") is True


def test_us_and_world_paths_are_not_blocked():
    """Regression guard: the education tracker this template came from blocked
    /us-news/ and /world/. For AI those paths carry the most important stories."""
    assert is_blocked_url_pattern("https://example.com/us-news/ai-executive-order") is False
    assert is_blocked_url_pattern("https://example.com/world/china/ai-rules") is False


def test_country_veto_is_disabled_for_this_tracker():
    """veto_non_uk is false in config/domain.yml, so nothing is dropped for
    mentioning a non-UK place."""
    cases = [
        ("White House issues AI executive order", "Washington DC announcement."),
        ("China publishes generative AI measures", "Beijing regulator sets rules."),
        ("Stanford releases AI Index", "Researchers in California report trends."),
    ]
    for title, body in cases:
        assert is_non_uk_content(title, body) is None, title


def test_approved_domain_gate_fails_closed():
    """The gate rejects anything not explicitly listed in approved_domains.
    Was written against the empty pre-sources roster; now that the roster is
    populated it asserts the property that mattered all along — unlisted
    domains are dropped, so a new source needs a deliberate config change."""
    assert is_approved_domain("https://example-not-a-source.com/x") is False
    # NOTE: bbc.co.uk used to stand in for "an obvious news site we do not
    # follow". It became an approved source on 2026-08-29 when mainstream tech
    # coverage was added, so the example had to change to something that will
    # never be a source.
    assert is_approved_domain("https://some-random-blog.example/x") is False
    # Exact netloc match: a subdomain does NOT inherit its parent's approval.
    assert is_approved_domain("https://openai.com/index/x") is True
    assert is_approved_domain("https://careers.openai.com/x") is False


def test_approved_domains_match_the_source_roster():
    """Every source in sources.yml must have its article domain approved, or it
    silently scrapes and then drops everything. aisnakeoil.com is the live
    example: the feed lives there but items resolve to normaltech.ai."""
    import yaml
    from pathlib import Path
    approved = set(
        yaml.safe_load(Path("config/domain.yml").read_text())["relevance"]["approved_domains"]
    )
    for host in ("normaltech.ai", "gds.blog.gov.uk", "gov.uk", "arxiv.org"):
        assert host in approved, host
    assert "aisnakeoil.com" not in approved


def test_default_keywords_come_from_domain_config():
    assert "artificial intelligence" in DEFAULT_KEYWORDS
    assert "ai governance" in DEFAULT_KEYWORDS
    assert "education" not in DEFAULT_KEYWORDS


def test_keyword_matching_is_word_boundary_aware():
    patterns = compile_keyword_patterns(DEFAULT_KEYWORDS)
    assert matched_keywords("EU AI Act enters into force", patterns, DEFAULT_KEYWORDS)
    # "ai" must not match inside another word
    assert not matched_keywords("Repairs to the said building", patterns, DEFAULT_KEYWORDS)
