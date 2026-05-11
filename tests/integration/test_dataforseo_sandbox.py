"""Integration test against DataForSEO sandbox (free, canned responses)."""

import os

import pytest

from seo_toolbox.dataforseo import DataForSEOClient, parse_serp_items


@pytest.mark.asyncio
async def test_sandbox_fetches_canned_response():
    login = os.environ.get("DATAFORSEO_LOGIN")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    if not (login and password):
        pytest.skip("DataForSEO creds not in env")

    client = DataForSEOClient(login=login, password=password, sandbox=True)
    result = await client.fetch_serp(
        keyword="test",
        location_code=2158,
        language_code="zh-TW",
        depth=20,
    )
    assert "items" in result
    assert "cost" in result
    parsed = parse_serp_items(result["items"])
    assert "organic_results" in parsed
    assert "ai_overview" in parsed
    assert "featured_snippet" in parsed
    assert "people_also_ask" in parsed
