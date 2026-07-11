import os

# config.py validates required env vars at import time — set fakes before
# importing tavily_client (which imports config) if they aren't already present.
os.environ.setdefault("MCP_URL", "https://example.invalid/mcp")
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("KEYCLOAK_URL", "https://example.invalid")
os.environ.setdefault("KEYCLOAK_REFRESH_TOKEN", "fake-refresh-token")
os.environ.setdefault("DEPS_CONNECTION", "deps_conn")
os.environ.setdefault("GITHUB_CONNECTION", "github_conn")
os.environ.setdefault("NEBIUS_API_KEY", "fake-nebius-key")

from apps.ai_safety_check.tavily_client import TavilyClient


def test_no_key_returns_empty():
    assert TavilyClient(api_key="").search("anything") == []


def test_parses_results():
    def fake_post(url, json=None, timeout=None):
        class R:
            def raise_for_status(self): pass
            def json(self): return {"results": [
                {"title": "T", "url": "http://x", "content": "snippet"}]}
        return R()
    c = TavilyClient(api_key="k", http_post=fake_post)
    out = c.search("mlflow cve 2024")
    assert out[0]["url"] == "http://x"
