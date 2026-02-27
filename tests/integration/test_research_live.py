import pytest

from src.tools.research import search_web, scrape_url


async def test_brave_search_returns_real_results(live_settings):
    results = await search_web("crypto wallet security", live_settings)
    assert len(results) >= 1
    assert "url" in results[0]
    assert "title" in results[0]
    print(f"Got {len(results)} results, first: {results[0]['title']}")


async def test_scrape_real_website(live_settings):
    result = await scrape_url("https://www.keypo.io", live_settings)
    assert result["url"] == "https://www.keypo.io"
    assert len(result["markdown"]) > 0
    assert "source" in result
    print(f"Scraped {len(result['markdown'])} chars from keypo.io (source: {result['source']})")


async def test_scrape_unreachable_url(live_settings):
    result = await scrape_url("https://this-domain-does-not-exist-9999.com", live_settings)
    assert result["markdown"] == "" or result.get("source") == "jina"
    assert "source" in result
    print(f"Result source: {result['source']}, error: {result.get('error', 'none')}")


async def test_search_then_scrape_top_result(live_settings):
    results = await search_web("Keypo crypto security", live_settings, count=3)
    assert len(results) >= 1

    top_url = results[0]["url"]
    print(f"Scraping top result: {top_url}")

    scraped = await scrape_url(top_url, live_settings)
    assert "source" in scraped
    print(f"Scraped {len(scraped['markdown'])} chars (source: {scraped['source']}), error: {scraped.get('error', 'none')}")
    assert "url" in scraped
