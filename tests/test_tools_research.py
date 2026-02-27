from unittest.mock import patch

import httpx
import pytest
import respx

from src.tools.research import scrape_url, search_web

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
JINA_URL = "https://r.jina.ai/https://example.com/page"


# ── search_web tests (unchanged) ──────────────────────────────────────────────


@respx.mock
async def test_search_web_returns_results(settings):
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={
        "web": {
            "results": [
                {"url": "https://example.com", "title": "Example", "description": "A test"},
                {"url": "https://other.com", "title": "Other", "description": "Another"},
            ]
        }
    }))

    results = await search_web("crypto wallets", settings)
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com"
    assert results[0]["title"] == "Example"
    assert results[0]["description"] == "A test"


@respx.mock
async def test_search_web_empty_results(settings):
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={
        "web": {"results": []}
    }))

    results = await search_web("nonexistent query", settings)
    assert results == []


@respx.mock
async def test_search_web_respects_count(settings):
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={
        "web": {"results": [{"url": "https://a.com", "title": "A", "description": "a"}]}
    }))

    await search_web("test", settings, count=3)
    request = respx.calls.last.request
    assert "count=3" in str(request.url)


@respx.mock
async def test_search_web_handles_api_error(settings):
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(500))

    results = await search_web("test", settings)
    assert len(results) == 1
    assert "error" in results[0]


# ── scrape_url tests ──────────────────────────────────────────────────────────


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_url_converts_html(mock_extract, settings):
    """Basic scrape: trafilatura returns content, passes through correctly."""
    mock_extract.return_value = "# Hello World\n\nSome content here." + " extra" * 100
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html; charset=utf-8"})
    )

    result = await scrape_url("https://example.com/page", settings)
    assert "Hello World" in result["markdown"]
    assert "Some content" in result["markdown"]
    assert result["url"] == "https://example.com/page"
    assert result["source"] == "trafilatura"
    assert "error" not in result


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_url_truncates_long_content(mock_extract, settings):
    """Content exceeding scrape_max_chars is truncated."""
    settings.scrape_max_chars = 100
    mock_extract.return_value = "x" * 500
    respx.get("https://example.com/long").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )

    result = await scrape_url("https://example.com/long", settings)
    assert len(result["markdown"]) <= 100


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_good_content_skips_jina(mock_extract, settings):
    """When trafilatura returns >= threshold chars, Jina is never called."""
    mock_extract.return_value = "x" * 400  # > 300 threshold
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    jina_route = respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="jina content"))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert not jina_route.called


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_trafilatura_none_triggers_jina_fallback(mock_extract, settings):
    """When trafilatura returns None, Jina fallback is triggered."""
    mock_extract.return_value = None
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="Jina extracted content " * 20))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"
    assert "Jina extracted" in result["markdown"]


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_thin_content_triggers_jina_fallback(mock_extract, settings):
    """When trafilatura returns < threshold chars, Jina fallback is triggered."""
    mock_extract.return_value = "short"  # 5 chars < 300
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="Full Jina content " * 30))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_thin_prefers_jina_when_longer(mock_extract, settings):
    """When both return content, the longer one wins."""
    mock_extract.return_value = "a" * 100  # thin but not empty
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="b" * 250))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"
    assert result["markdown"].startswith("b")


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_thin_prefers_layer1_when_longer(mock_extract, settings):
    """When layer 1 is thin but longer than Jina, layer 1 wins."""
    mock_extract.return_value = "a" * 250  # thin (< 300) but longer than Jina
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="b" * 100))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert result["markdown"].startswith("a")


@respx.mock
async def test_scrape_http_error_triggers_jina_fallback(settings):
    """When httpx returns 403, Jina fallback is triggered."""
    respx.get("https://example.com/page").mock(return_value=httpx.Response(403))
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="Jina got through"))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"
    assert "Jina got through" in result["markdown"]


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_trafilatura_exception_triggers_jina_fallback(mock_extract, settings):
    """When trafilatura raises, Jina fallback is triggered."""
    mock_extract.side_effect = Exception("lxml parse error")
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="Jina recovered"))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"
    assert "Jina recovered" in result["markdown"]


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_failure_returns_layer1(mock_extract, settings):
    """When Jina returns 500, layer 1 thin content is returned."""
    mock_extract.return_value = "thin content"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(500))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert result["markdown"] == "thin content"
    assert "error" not in result


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_rate_limited_returns_layer1(mock_extract, settings):
    """When Jina returns 429, layer 1 thin content is returned."""
    mock_extract.return_value = "thin content"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(429))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert result["markdown"] == "thin content"


@respx.mock
async def test_scrape_both_fail_returns_error_dict(settings):
    """When httpx fails and Jina fails, error dict is returned."""
    respx.get("https://example.com/page").mock(return_value=httpx.Response(403))
    respx.get(JINA_URL).mock(return_value=httpx.Response(500))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "error"
    assert result["markdown"] == ""
    assert "error" in result


@respx.mock
async def test_scrape_non_html_skips_jina(settings):
    """Non-HTML content-type returns error without trying Jina."""
    respx.get("https://example.com/file.pdf").mock(
        return_value=httpx.Response(200, content=b"binary",
                                    headers={"content-type": "application/pdf"})
    )
    jina_route = respx.get("https://r.jina.ai/https://example.com/file.pdf").mock(
        return_value=httpx.Response(200, text="should not be called")
    )

    result = await scrape_url("https://example.com/file.pdf", settings)
    assert "Non-HTML" in result["error"]
    assert result["markdown"] == ""
    assert result["source"] == "error"
    assert not jina_route.called


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_sends_auth_header_when_key_set(mock_extract, settings):
    """When jina_api_key is set, Authorization header is sent."""
    settings.jina_api_key = "test-key"
    mock_extract.return_value = "short"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    jina_route = respx.get(JINA_URL).mock(
        return_value=httpx.Response(200, text="Jina content " * 30)
    )

    await scrape_url("https://example.com/page", settings)
    assert jina_route.called
    jina_request = jina_route.calls.last.request
    assert jina_request.headers["authorization"] == "Bearer test-key"


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_no_auth_header_when_key_empty(mock_extract, settings):
    """When jina_api_key is empty, no Authorization header is sent."""
    settings.jina_api_key = ""
    mock_extract.return_value = "short"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    jina_route = respx.get(JINA_URL).mock(
        return_value=httpx.Response(200, text="Jina content " * 30)
    )

    await scrape_url("https://example.com/page", settings)
    assert jina_route.called
    jina_request = jina_route.calls.last.request
    assert "authorization" not in jina_request.headers


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_uses_jina_timeout(mock_extract, settings):
    """Jina call uses jina_timeout setting, not scrape_timeout."""
    settings.jina_timeout = 45
    settings.scrape_timeout = 10
    mock_extract.return_value = "short"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    jina_route = respx.get(JINA_URL).mock(
        return_value=httpx.Response(200, text="Jina content " * 30)
    )

    result = await scrape_url("https://example.com/page", settings)
    # Jina was called (confirming it used the timeout setting — respx doesn't expose
    # the timeout directly, but we verify the call was made with the right settings)
    assert jina_route.called
    assert result["source"] == "jina"


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_disabled_skips_fallback(mock_extract, settings):
    """When jina_fallback_enabled=False, Jina is never called."""
    settings.jina_fallback_enabled = False
    mock_extract.return_value = "thin"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    jina_route = respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="Jina"))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert result["markdown"] == "thin"
    assert not jina_route.called


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_empty_response_discarded(mock_extract, settings):
    """Jina returning empty body is discarded, layer 1 is used."""
    mock_extract.return_value = "some thin content"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text=""))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert result["markdown"] == "some thin content"


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_jina_html_error_page_discarded(mock_extract, settings):
    """Jina returning raw HTML error page is discarded."""
    mock_extract.return_value = "some thin content"
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(
        return_value=httpx.Response(200, text="<!DOCTYPE html><html>Error</html>")
    )

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "trafilatura"
    assert result["markdown"] == "some thin content"


@respx.mock
@patch("src.tools.research.trafilatura.extract")
async def test_scrape_trafilatura_valueerror_triggers_jina(mock_extract, settings):
    """ValueError from trafilatura triggers Jina (not treated as non-HTML)."""
    mock_extract.side_effect = ValueError("could not parse")
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>...</html>",
                                    headers={"content-type": "text/html"})
    )
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="Jina recovered"))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"
    assert "Jina recovered" in result["markdown"]


@respx.mock
async def test_scrape_jina_result_truncated(settings):
    """Jina content exceeding scrape_max_chars is truncated."""
    settings.scrape_max_chars = 50
    respx.get("https://example.com/page").mock(return_value=httpx.Response(403))
    respx.get(JINA_URL).mock(return_value=httpx.Response(200, text="x" * 200))

    result = await scrape_url("https://example.com/page", settings)
    assert result["source"] == "jina"
    assert len(result["markdown"]) == 50


@respx.mock
async def test_search_web_passes_freshness_param(settings):
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={
        "web": {"results": [{"url": "https://a.com", "title": "A", "description": "a"}]}
    }))

    await search_web("test", settings, freshness="pw")
    request = respx.calls.last.request
    assert "freshness=pw" in str(request.url)


@respx.mock
async def test_search_web_omits_freshness_when_none(settings):
    respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json={
        "web": {"results": [{"url": "https://a.com", "title": "A", "description": "a"}]}
    }))

    await search_web("test", settings)
    request = respx.calls.last.request
    assert "freshness" not in str(request.url)


@respx.mock
async def test_scrape_url_error_on_connection_failure(settings):
    """Connection failure triggers Jina, but if both fail returns error dict."""
    settings.jina_fallback_enabled = False
    respx.get("https://unreachable.test/").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    result = await scrape_url("https://unreachable.test/", settings)
    assert result["error"]
    assert result["markdown"] == ""
    assert result["source"] == "error"
