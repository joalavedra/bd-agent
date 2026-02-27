import asyncio

import httpx
import structlog
import trafilatura

from src.config import Settings

log = structlog.get_logger()


class NonHTMLContentError(Exception):
    """Raised when the response content-type is not HTML."""
    pass


async def search_web(query: str, settings: Settings, count: int = 5, freshness: str | None = None) -> list[dict]:
    """Search the web using Brave Search API."""
    async with httpx.AsyncClient() as client:
        try:
            params = {"q": query, "count": count}
            if freshness:
                params["freshness"] = freshness
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params=params,
                headers={"X-Subscription-Token": settings.brave_api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("web", {}).get("results", [])
            return [
                {
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                }
                for r in results
            ]
        except httpx.HTTPError as e:
            return [{"error": str(e)}]


async def _httpx_fetch(url: str, settings: Settings) -> str:
    """Fetch URL, return raw HTML. Raises on HTTP errors or non-HTML content."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=settings.scrape_timeout,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise NonHTMLContentError(f"Non-HTML content-type: {content_type}")
        return resp.text


async def _try_jina_fallback(url: str, settings: Settings, reason: str) -> dict | None:
    """Try Jina Reader API as fallback. Returns result dict or None on failure."""
    try:
        log.info("jina_fallback_triggered", url=url, reason=reason)
        headers = {"Accept": "text/markdown"}
        if settings.jina_api_key:
            headers["Authorization"] = f"Bearer {settings.jina_api_key}"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                f"https://r.jina.ai/{url}",  # Jina expects raw URL, no encoding
                headers=headers,
                timeout=settings.jina_timeout,
            )
            resp.raise_for_status()
        text = resp.text.strip()
        if not text or text[:50].lower().lstrip().startswith(("<html", "<!doctype")):
            log.warning("jina_fallback_unusable", url=url, reason="empty_or_html")
            return None
        return {"markdown": text, "url": url, "source": "jina"}
    except Exception as e:
        log.warning("jina_fallback_failed", url=url, error=str(e))
        return None


async def scrape_url(url: str, settings: Settings) -> dict:
    """Fetch a URL and extract content using trafilatura, with Jina Reader fallback."""
    try:
        html = await _httpx_fetch(url, settings)
        text = await asyncio.to_thread(
            trafilatura.extract,
            html,
            include_links=True,
            include_tables=True,
            include_comments=False,
            output_format="markdown",
            favor_recall=True,
        )
        text = (text or "").strip()

        if len(text) >= settings.scrape_thin_threshold:
            return {
                "markdown": text[: settings.scrape_max_chars],
                "url": url,
                "source": "trafilatura",
            }

        # Thin content — try Jina if enabled, return whichever raw text is longer
        if settings.jina_fallback_enabled:
            jina_result = await _try_jina_fallback(url, settings, reason="thin_content")
            if jina_result and len(jina_result["markdown"]) > len(text):
                return {
                    **jina_result,
                    "markdown": jina_result["markdown"][: settings.scrape_max_chars],
                }

        return {
            "markdown": text[: settings.scrape_max_chars],
            "url": url,
            "source": "trafilatura",
        }

    except NonHTMLContentError as e:
        return {"markdown": "", "error": str(e), "url": url, "source": "error"}

    except httpx.HTTPError as e:
        if settings.jina_fallback_enabled:
            jina_result = await _try_jina_fallback(url, settings, reason="fetch_error")
            if jina_result:
                return {
                    **jina_result,
                    "markdown": jina_result["markdown"][: settings.scrape_max_chars],
                }
        return {"markdown": "", "error": str(e), "url": url, "source": "error"}

    except Exception as e:
        log.warning("scrape_unexpected_error", url=url, error=str(e))
        if settings.jina_fallback_enabled:
            jina_result = await _try_jina_fallback(url, settings, reason="extract_error")
            if jina_result:
                return {
                    **jina_result,
                    "markdown": jina_result["markdown"][: settings.scrape_max_chars],
                }
        return {"markdown": "", "error": str(e), "url": url, "source": "error"}
