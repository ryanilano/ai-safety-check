import asyncio
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


def test_nl_query_reads_sql_nested_under_tool_name(monkeypatch):
    # Live CRAFT returns {"ok": true, "generate_sql": {"sql": ...}} — the SQL
    # is nested under the tool name, not top-level. Reading only the flat
    # "sql" key made nl_query silently return no SQL (empty leaderboard).
    async def fake_call(self, tool: str, arguments: dict):
        if tool == "generate_sql":
            return {"ok": True, "generate_sql": {"sql": "SELECT 1"}}
        if tool == "execute_query":
            return {"ok": True,
                    "execute_query": {"artifact_fqn": "a", "row_count": 1}}
        if tool == "get_result_page":
            return {"preview": {"columns": ["N"], "rows": [[1]]}}
        raise AssertionError(f"unexpected tool call: {tool}")

    monkeypatch.setattr(CraftClient, "call", fake_call)
    c = CraftClient()
    result, sql = asyncio.run(c.nl_query("q", "deps_conn", "S", "S.D.S"))
    assert sql == "SELECT 1"
    assert result["rows"] == [[1]]


def test_execute_query_returns_positional_list_of_lists(monkeypatch):
    # execute_query() calls self.call(...) twice — once for "execute_query"
    # (to get artifact_fqn/row_count) and once for "get_result_page" (to get
    # the actual rows). Patch that seam so no HTTP happens.
    canned_columns = ["Title", "CVSS3Score", "GitHubSeverity"]
    canned_rows = [["path traversal", 10.0, "CRITICAL"]]

    async def fake_call(self, tool: str, arguments: dict):
        if tool == "execute_query":
            return {
                "ok": True,
                "execute_query": {"artifact_fqn": "fake_artifact", "row_count": 1},
            }
        if tool == "get_result_page":
            return {"preview": {"columns": canned_columns, "rows": canned_rows}}
        raise AssertionError(f"unexpected tool call: {tool}")

    monkeypatch.setattr(CraftClient, "call", fake_call)

    c = CraftClient()
    result = asyncio.run(c.execute_query("SELECT * FROM whatever", "deps_conn"))

    assert result["columns"] == canned_columns
    assert isinstance(result["rows"][0], list)
    assert result["rows"][0][0] == "path traversal"
