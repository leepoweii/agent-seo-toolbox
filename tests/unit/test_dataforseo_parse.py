"""Unit tests for parse_serp_items (pure parsing, no network)."""

from seo_toolbox.dataforseo import parse_serp_items


def test_parse_empty_items():
    parsed = parse_serp_items([])
    assert parsed["organic_results"] == []
    assert parsed["ai_overview"] is None
    assert parsed["featured_snippet"] is None
    assert parsed["people_also_ask"] == []


def test_parse_organic_only():
    items = [
        {
            "type": "organic",
            "url": "https://a.com",
            "domain": "a.com",
            "title": "A",
            "rank_group": 1,
            "rank_absolute": 1,
        },
    ]
    parsed = parse_serp_items(items)
    assert len(parsed["organic_results"]) == 1
    assert parsed["organic_results"][0]["url"] == "https://a.com"


def test_parse_with_ai_overview():
    items = [
        {
            "type": "ai_overview",
            "markdown": "AI says...",
            "references": [{"url": "https://x.com", "title": "X"}],
        },
        {"type": "organic", "url": "https://a.com", "domain": "a.com"},
    ]
    parsed = parse_serp_items(items)
    assert parsed["ai_overview"]["markdown"] == "AI says..."
    assert len(parsed["ai_overview"]["references"]) == 1
    assert len(parsed["organic_results"]) == 1
