"""Hindsight web lookups. Enrichment only — degrades to no-op without a key."""
import httpx

_ENDPOINT = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self, api_key: str | None = None, http_post=None):
        from . import config
        self._key = api_key if api_key is not None else config.TAVILY_API_KEY
        self._post = http_post or httpx.post

    def search(self, query: str) -> list[dict]:
        if not self._key:
            return []
        try:
            r = self._post(_ENDPOINT,
                           json={"api_key": self._key, "query": query, "max_results": 5},
                           timeout=15.0)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        return [{"title": x.get("title", ""), "url": x.get("url", ""),
                 "content": x.get("content", "")} for x in data.get("results", [])]
