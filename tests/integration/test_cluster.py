"""Integration test: cluster pipeline (without HTTP server) using mocked DataForSEO."""

import csv
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from seo_toolbox.commands.cluster import run_cluster_pipeline
from seo_toolbox.db import SerpCache


@pytest.fixture
def keywords_csv(tmp_path):
    path = tmp_path / "keywords.csv"
    with open(path, "w") as f:
        w = csv.writer(f)
        w.writerow(["keyword", "volume"])
        w.writerow(["SEO 工具", "1000"])
        w.writerow(["SEO 關鍵字工具", "500"])
    return path


def _expires() -> datetime:
    return datetime.now() + timedelta(days=7)


def _fake_serp(kw, urls):
    return {
        "keyword": kw,
        "items": [
            {
                "type": "organic",
                "url": u,
                "domain": u.split("/")[2] if "://" in u else "x",
                "title": "T",
                "rank_group": i + 1,
                "rank_absolute": i + 1,
            }
            for i, u in enumerate(urls)
        ],
        "item_types": ["organic"],
        "total_results": 1000,
        "cost": 0.005,
    }


async def test_cluster_pipeline_fetches_and_clusters(db_session, keywords_csv):
    mock_client = AsyncMock()
    mock_client.fetch_serp.side_effect = [
        _fake_serp("SEO 工具", ["https://target.com/a", "https://b.com", "https://c.com"]),
        _fake_serp("SEO 關鍵字工具", ["https://target.com/a", "https://b.com", "https://d.com"]),
    ]

    result = await run_cluster_pipeline(
        keywords=["SEO 工具", "SEO 關鍵字工具"],
        volumes={"SEO 工具": 1000, "SEO 關鍵字工具": 500},
        session=db_session,
        client=mock_client,
        threshold=0.3,
        method="jaccard",
    )

    assert "clusters" in result
    assert "matrix" in result
    assert "ungrouped" in result
    # Two URLs shared / 4 unique → jaccard 0.5 ≥ 0.3 → one cluster
    assert len(result["clusters"]) == 1
    assert "SEO 工具" in result["clusters"][0]["members"]
    assert "SEO 關鍵字工具" in result["clusters"][0]["members"]
    assert mock_client.fetch_serp.call_count == 2


async def test_cluster_uses_cache_when_present(db_session):
    keyword = "cached_kw_" + uuid.uuid4().hex[:8]
    db_session.add(
        SerpCache(
            keyword=keyword,
            location_code=2158,
            language_code="zh-TW",
            serp_data={
                "organic_results": [{"url": f"https://example.com/{i}"} for i in range(10)],
                "metadata": {"depth_fetched": 20},
            },
            fetched_at=datetime.now(),
            expires_at=_expires(),
        )
    )
    await db_session.flush()

    mock_client = AsyncMock()

    result = await run_cluster_pipeline(
        keywords=[keyword],
        volumes={keyword: 100},
        session=db_session,
        client=mock_client,
        threshold=0.3,
        method="jaccard",
    )
    assert mock_client.fetch_serp.call_count == 0  # cache hit
    assert len(result["clusters"]) == 1


async def test_csv_loader_parses_keyword_and_volume(keywords_csv):
    """Read CSV produces keywords list + volumes dict."""
    from seo_toolbox.commands.cluster import _read_keywords

    keywords, volumes = _read_keywords(str(keywords_csv))
    assert keywords == ["SEO 工具", "SEO 關鍵字工具"]
    assert volumes == {"SEO 工具": 1000, "SEO 關鍵字工具": 500}


def test_csv_loader_handles_missing_volume(tmp_path):
    """CSV with only keyword column should default volumes to 0."""
    from seo_toolbox.commands.cluster import _read_keywords

    p = tmp_path / "k.csv"
    with open(p, "w") as f:
        f.write("keyword\nSEO 工具\nSEO 關鍵字工具\n")
    keywords, volumes = _read_keywords(str(p))
    assert keywords == ["SEO 工具", "SEO 關鍵字工具"]
    assert volumes == {"SEO 工具": 0, "SEO 關鍵字工具": 0}


# ------------------------------------------------------------------
# serp_features payload — drives the sidebar UI (AI Overview / FS / PAA)
# ------------------------------------------------------------------


async def test_pipeline_returns_serp_features_from_cache(db_session):
    """When cache row contains AI Overview / Featured Snippet / PAA,
    the pipeline must surface them under result['serp_features'][kw]."""
    keyword = "feat_cached_" + uuid.uuid4().hex[:8]
    db_session.add(
        SerpCache(
            keyword=keyword,
            location_code=2158,
            language_code="zh-TW",
            serp_data={
                "organic_results": [{"url": f"https://example.com/{i}"} for i in range(10)],
                "ai_overview": {
                    "markdown": "AI summary text",
                    "references": [{"url": "https://example.com/0", "title": "ref"}],
                    "rank_absolute": 1,
                },
                "featured_snippet": {
                    "url": "https://example.com/0",
                    "title": "FS title",
                    "description": "FS desc",
                    "rank_absolute": 2,
                },
                "people_also_ask": [
                    {"title": "What is X?", "type": "people_also_ask_element"},
                    {"title": "How does Y work?"},
                ],
                "metadata": {"depth_fetched": 20},
            },
            fetched_at=datetime.now(),
            expires_at=_expires(),
        )
    )
    await db_session.flush()

    mock_client = AsyncMock()
    result = await run_cluster_pipeline(
        keywords=[keyword],
        volumes={keyword: 100},
        session=db_session,
        client=mock_client,
        threshold=0.3,
        method="percentage",
    )

    assert "serp_features" in result
    feats = result["serp_features"][keyword]
    assert feats["ai_overview"] is not None
    assert feats["ai_overview"]["markdown"] == "AI summary text"
    assert feats["featured_snippet"]["title"] == "FS title"
    assert len(feats["paa"]) == 2
    assert feats["paa"][0]["title"] == "What is X?"


async def test_pipeline_returns_serp_features_on_cache_miss(db_session):
    """Cache miss → fetch via DataForSEO → features must round-trip into
    result['serp_features'][kw] after parse_serp_items."""
    keyword = "feat_fetch_" + uuid.uuid4().hex[:8]
    mock_client = AsyncMock()
    mock_client.fetch_serp.return_value = {
        "keyword": keyword,
        "items": [
            {"type": "organic", "url": "https://x.com/a", "domain": "x.com",
             "rank_group": 1, "rank_absolute": 3, "title": "T", "description": "D"},
            {"type": "ai_overview", "markdown": "AI from API",
             "references": [{"url": "https://x.com/a"}], "rank_absolute": 1},
            {"type": "featured_snippet", "url": "https://x.com/a",
             "title": "FS API", "description": "snippet", "rank_absolute": 2},
            {"type": "people_also_ask",
             "items": [{"title": "Q1?"}, {"title": "Q2?"}]},
        ],
        "item_types": ["organic", "ai_overview", "featured_snippet", "people_also_ask"],
        "total_results": 100,
        "cost": 0.01,
    }

    result = await run_cluster_pipeline(
        keywords=[keyword],
        volumes={keyword: 100},
        session=db_session,
        client=mock_client,
        threshold=0.3,
        method="percentage",
    )

    assert mock_client.fetch_serp.call_count == 1
    feats = result["serp_features"][keyword]
    assert feats["ai_overview"]["markdown"] == "AI from API"
    assert feats["featured_snippet"]["title"] == "FS API"
    assert [q["title"] for q in feats["paa"]] == ["Q1?", "Q2?"]


async def test_pipeline_serp_features_includes_organic_with_titles(db_session):
    """serp_features[kw].organic must include title/description/domain so the
    sidebar can render Google-SERP style rows (not just URLs)."""
    keyword = "feat_organic_" + uuid.uuid4().hex[:8]
    db_session.add(
        SerpCache(
            keyword=keyword,
            location_code=2158,
            language_code="zh-TW",
            serp_data={
                "organic_results": [
                    {
                        "url": "https://x.com/a",
                        "domain": "x.com",
                        "title": "How to do X",
                        "description": "Learn how to X in three steps",
                        "rank_group": 1,
                        "rank_absolute": 3,
                    },
                    {
                        "url": "https://y.com/b",
                        "domain": "y.com",
                        "title": "Why X matters",
                        "description": "An overview of X.",
                        "rank_group": 2,
                        "rank_absolute": 4,
                    },
                ],
            },
            fetched_at=datetime.now(),
            expires_at=_expires(),
        )
    )
    await db_session.flush()

    mock_client = AsyncMock()
    result = await run_cluster_pipeline(
        keywords=[keyword],
        volumes={keyword: 1},
        session=db_session,
        client=mock_client,
        threshold=0.3,
        method="percentage",
    )
    organic = result["serp_features"][keyword]["organic"]
    assert len(organic) == 2
    assert organic[0]["title"] == "How to do X"
    assert organic[0]["description"] == "Learn how to X in three steps"
    assert organic[0]["domain"] == "x.com"
    assert organic[0]["rank_absolute"] == 3


async def test_pipeline_serp_features_handles_missing_addons(db_session):
    """Cache row with only organic_results (no AI Overview / FS / PAA) must
    still produce a valid serp_features entry — None / empty list defaults."""
    keyword = "feat_bare_" + uuid.uuid4().hex[:8]
    db_session.add(
        SerpCache(
            keyword=keyword,
            location_code=2158,
            language_code="zh-TW",
            serp_data={
                "organic_results": [{"url": "https://x.com/a"}],
            },
            fetched_at=datetime.now(),
            expires_at=_expires(),
        )
    )
    await db_session.flush()

    mock_client = AsyncMock()
    result = await run_cluster_pipeline(
        keywords=[keyword],
        volumes={keyword: 1},
        session=db_session,
        client=mock_client,
        threshold=0.3,
        method="percentage",
    )
    feats = result["serp_features"][keyword]
    assert feats["ai_overview"] is None
    assert feats["featured_snippet"] is None
    assert feats["paa"] == []
    assert feats["organic"] == [{"url": "https://x.com/a"}]
