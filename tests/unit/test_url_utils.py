from seo_toolbox.url_utils import normalize_url


def test_strips_protocol_and_www():
    assert normalize_url("https://www.example.com/path") == "example.com/path"


def test_strips_trailing_slash():
    assert normalize_url("https://example.com/path/") == "example.com/path"


def test_lowercases_host():
    assert normalize_url("https://EXAMPLE.COM/Path") == "example.com/Path"


def test_strips_tracking_params():
    url = "https://example.com/page?utm_source=x&utm_medium=y&fbclid=z&keep=this"
    assert normalize_url(url) == "example.com/page?keep=this"


def test_sorts_query_params():
    assert normalize_url("https://example.com/?b=2&a=1") == "example.com/?a=1&b=2"


def test_handles_malformed_url_gracefully():
    assert normalize_url("not a url") == "not a url"


def test_handles_none():
    assert normalize_url(None) == ""


def test_handles_empty_string():
    assert normalize_url("") == ""


def test_drops_url_fragment():
    """Fragments are client-side only, irrelevant for SERP identity."""
    assert normalize_url("https://example.com/page#section") == "example.com/page"
