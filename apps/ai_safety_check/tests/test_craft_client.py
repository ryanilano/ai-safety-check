import os

# config.py validates required env vars at import time — set fakes before
# importing craft_client (which imports config) if they aren't already present.
os.environ.setdefault("MCP_URL", "https://example.invalid/mcp")
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("KEYCLOAK_URL", "https://example.invalid")
os.environ.setdefault("KEYCLOAK_REFRESH_TOKEN", "fake-refresh-token")
os.environ.setdefault("DEPS_CONNECTION", "deps_conn")
os.environ.setdefault("GITHUB_CONNECTION", "github_conn")
os.environ.setdefault("NEBIUS_API_KEY", "fake-nebius-key")

from apps.ai_safety_check.craft_client import CraftClient


def test_auth_headers_include_project_and_bearer():
    c = CraftClient()
    c._bearer_token = "tok123"
    h = c._auth_headers()
    assert h["Authorization"] == "Bearer tok123"
    assert h["X-Project-ID"]  # project id injected


def test_extract_result_unwraps_content_text():
    # content items are shaped {"type": "text", "text": ...} per the real MCP
    # response format (the brief's sketch omitted "type"; _extract_result
    # requires it to route into the JSON-parsing branch).
    event = {"result": {"content": [{"type": "text", "text": '{"ok": true, "rows": []}'}]}}
    out = CraftClient._extract_result("execute_query", event)
    assert out["ok"] is True


def test_extract_result_raises_on_error_event():
    event = {"error": {"code": "boom", "message": "bad request"}}
    try:
        CraftClient._extract_result("generate_sql", event)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "boom" in str(exc)


def test_extract_result_wraps_non_dict_response():
    event = {"result": {"content": [{"type": "text", "text": "not json"}]}}
    out = CraftClient._extract_result("execute_query", event)
    assert out["ok"] is False
    assert out["error"]["code"] == "non_dict_response"
