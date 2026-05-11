"""Async client for DataForSEO Google Organic SERP advanced live endpoint.

Endpoint: /v3/serp/google/organic/live/advanced
Add-ons enabled: AI Overview content, PAA click depth=3.
Cost: see docs/methodology.md "DataForSEO cost model".
"""
from __future__ import annotations

from typing import Any

import httpx

PROD_URL = "https://api.dataforseo.com/v3"
SANDBOX_URL = "https://sandbox.dataforseo.com/v3"


def build_serp_payload(
    *,
    keyword: str,
    location_code: int,
    language_code: str,
    depth: int,
    device: str = "mobile",
    os: str = "ios",
    load_async_ai_overview: bool = True,
    people_also_ask_click_depth: int = 3,
) -> list[dict[str, Any]]:
    return [{
        "keyword": keyword,
        "location_code": location_code,
        "language_code": language_code,
        "device": device,
        "os": os,
        "depth": depth,
        "load_async_ai_overview": load_async_ai_overview,
        "people_also_ask_click_depth": people_also_ask_click_depth,
    }]


class DataForSEOClient:
    def __init__(self, login: str, password: str, sandbox: bool = False):
        self._auth = (login, password)
        self._base = SANDBOX_URL if sandbox else PROD_URL

    async def fetch_serp(
        self,
        *,
        keyword: str,
        location_code: int,
        language_code: str,
        depth: int,
        device: str = "mobile",
        os: str = "ios",
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base}/serp/google/organic/live/advanced"
        payload = build_serp_payload(
            keyword=keyword, location_code=location_code,
            language_code=language_code, depth=depth, device=device, os=os,
        )
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=90.0)
        try:
            r = await client.post(url, json=payload, auth=self._auth)
            r.raise_for_status()
            data = r.json()
        finally:
            if owns_client:
                await client.aclose()

        tasks = data.get("tasks") or []
        if not tasks:
            raise RuntimeError("DataForSEO returned no tasks")
        task = tasks[0]
        if task.get("status_code") != 20000:
            raise RuntimeError(
                f"DataForSEO error {task.get('status_code')}: {task.get('status_message')}"
            )
        result = (task.get("result") or [{}])[0]
        return {
            "keyword": result.get("keyword"),
            "items": result.get("items", []),
            "item_types": result.get("item_types", []),
            "total_results": result.get("se_results_count"),
            "cost": task.get("cost", 0.0),
        }


def parse_serp_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract organic results, AI Overview, and featured snippet from items.

    Returns a dict ready to store in SerpCache.serp_data.
    """
    organic_results: list[dict[str, Any]] = []
    ai_overview = None
    featured_snippet = None
    paa_questions: list[dict[str, Any]] = []

    for item in items:
        t = item.get("type")
        if t == "organic":
            organic_results.append({
                "url": item.get("url"),
                "domain": item.get("domain"),
                "title": item.get("title"),
                "description": item.get("description"),
                "rank_group": item.get("rank_group"),
                "rank_absolute": item.get("rank_absolute"),
            })
        elif t == "ai_overview":
            ai_overview = {
                "markdown": item.get("markdown"),
                "items": item.get("items", []),
                "references": item.get("references", []),
                "rank_absolute": item.get("rank_absolute"),
            }
        elif t == "featured_snippet":
            featured_snippet = {
                "url": item.get("url"),
                "title": item.get("title"),
                "description": item.get("description"),
                "rank_absolute": item.get("rank_absolute"),
            }
        elif t == "people_also_ask":
            paa_questions.extend(item.get("items", []))

    return {
        "organic_results": organic_results,
        "ai_overview": ai_overview,
        "featured_snippet": featured_snippet,
        "people_also_ask": paa_questions,
    }
