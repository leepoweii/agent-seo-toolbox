import httpx
import pytest

from seo_toolbox.dataforseo import DataForSEOClient, build_serp_payload


def test_payload_shape():
    payload = build_serp_payload(
        keyword="SEO 工具",
        location_code=2158,
        language_code="zh-TW",
        depth=60,
        device="mobile",
        os="ios",
    )
    assert payload == [
        {
            "keyword": "SEO 工具",
            "location_code": 2158,
            "language_code": "zh-TW",
            "device": "mobile",
            "os": "ios",
            "depth": 60,
            "load_async_ai_overview": True,
            "people_also_ask_click_depth": 3,
        }
    ]


def test_payload_default_device_and_os():
    payload = build_serp_payload(
        keyword="test",
        location_code=2158,
        language_code="zh-TW",
        depth=20,
    )
    assert payload[0]["device"] == "mobile"
    assert payload[0]["os"] == "ios"


def test_payload_addons_can_be_disabled():
    payload = build_serp_payload(
        keyword="test",
        location_code=2158,
        language_code="zh-TW",
        depth=20,
        load_async_ai_overview=False,
        people_also_ask_click_depth=0,
    )
    assert payload[0]["load_async_ai_overview"] is False
    assert payload[0]["people_also_ask_click_depth"] == 0


@pytest.mark.asyncio
async def test_fetch_serp_raises_on_empty_tasks():
    """If DataForSEO returns no tasks, fetch_serp should raise RuntimeError."""

    def handler(request):
        return httpx.Response(200, json={"tasks": []})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    api = DataForSEOClient("user", "pass", sandbox=True)

    with pytest.raises(RuntimeError, match="no tasks"):
        await api.fetch_serp(
            keyword="x",
            location_code=2158,
            language_code="zh-TW",
            depth=20,
            client=client,
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_serp_raises_on_bad_status():
    """If task status_code != 20000, fetch_serp should raise RuntimeError with the code."""

    def handler(request):
        return httpx.Response(
            200,
            json={
                "tasks": [{"status_code": 40000, "status_message": "Bad Request", "result": None}]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    api = DataForSEOClient("user", "pass", sandbox=True)

    with pytest.raises(RuntimeError, match="40000"):
        await api.fetch_serp(
            keyword="x",
            location_code=2158,
            language_code="zh-TW",
            depth=20,
            client=client,
        )
    await client.aclose()
