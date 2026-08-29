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
    """Until approved_domains is populated in config/domain.yml, every article
    is rejected. This is the expected pre-sources state, not a bug — but it is
    the reason a fresh tracker ingests nothing."""
    assert is_approved_domain("https://openai.com/index/x") is False


def test_default_keywords_come_from_domain_config():
    assert "artificial intelligence" in DEFAULT_KEYWORDS
    assert "ai governance" in DEFAULT_KEYWORDS
    assert "education" not in DEFAULT_KEYWORDS


def test_keyword_matching_is_word_boundary_aware():
    patterns = compile_keyword_patterns(DEFAULT_KEYWORDS)
    assert matched_keywords("EU AI Act enters into force", patterns, DEFAULT_KEYWORDS)
    # "ai" must not match inside another word
    assert not matched_keywords("Repairs to the said building", patterns, DEFAULT_KEYWORDS)
