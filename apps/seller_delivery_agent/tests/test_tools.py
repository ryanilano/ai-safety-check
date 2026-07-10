import asyncio
import json

from apps.seller_delivery_agent import config
from apps.seller_delivery_agent.tools import TOOL_DEFINITIONS, ToolExecutor


class FakeMCP:
    """Stands in for an entered CraftClient: records _call args and returns canned
    MCP response shapes (the same shapes the real parsers/compactors were built against)."""

    def __init__(self):
        self.calls = []

    async def _call(self, tool, args):
        self.calls.append((tool, args))
        if tool == "search_schema":
            return {"list_metadata": {"results": [
                {"name": "OLIST_ORDERS", "type": "table",
                 "fully_qualified_name": "eval-x.DB.SC.OLIST_ORDERS",
                 "description": "orders " * 60},
            ]}}
        if tool == "get_schema":
            return {"metadata": {"name": "OLIST_ORDERS",
                                 "fully_qualified_name": "eval-x.DB.SC.OLIST_ORDERS",
                                 "children": [
                                     {"type": "column", "name": "order_id", "data_type": "VARCHAR",
                                      "description": "id " * 100},
                                     {"type": "column", "name": "order_status", "data_type": "VARCHAR"},
                                 ]}}
        if tool == "sample_data":
            return {"sample": {"columns": ["order_id"], "rows": [["abc"]]}}
        if tool == "generate_sql":
            return {"generate_sql": {"sql": "SELECT 42"}}
        if tool == "execute_query":
            return {"result": {"execute_query": {"artifact_fqn": "artifact:xyz"}}}
        if tool == "get_result_page":
            return {"preview": {"columns": ["AVG"], "rows": [["4.0"]]}}
        if tool == "generate_plotly_chart":
            return {"generate_plotly_chart": {"plotly_json": {"plotly_json": {
                "data": [{"type": "bar"}], "layout": {"title": "t"}}}}}
        raise AssertionError(f"unexpected tool {tool}")


def test_tool_surface_includes_discovery_query_and_note():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {
        "note", "search_schema", "get_schema", "sample_data",
        "generate_sql", "execute_query", "get_result_page", "generate_plotly_chart",
    }


def test_note_is_recorded_and_makes_no_mcp_call(tmp_path):
    mcp = FakeMCP()
    ex = ToolExecutor(mcp, str(tmp_path))
    out = asyncio.run(ex.run("note", {"thought": "orders down 30% in home_garden — why?"}))
    assert out == "noted"
    assert ex.notes == ["orders down 30% in home_garden — why?"]
    assert mcp.calls == []  # narration must not hit the data plane


def test_search_schema_compacts_and_injects_connection(tmp_path):
    mcp = FakeMCP()
    ex = ToolExecutor(mcp, str(tmp_path))
    out = asyncio.run(ex.run("search_schema", {"query": "orders"}))
    tool, args = mcp.calls[0]
    assert tool == "search_schema" and args["connection"] == config.CONNECTION_SLUG
    hits = json.loads(out)
    assert hits[0]["fqn"] == "eval-x.DB.SC.OLIST_ORDERS"
    assert len(hits[0]["description"]) <= 200  # compacted, not the giant catalog blob


def test_get_schema_returns_columns(tmp_path):
    ex = ToolExecutor(FakeMCP(), str(tmp_path))
    out = json.loads(asyncio.run(ex.run("get_schema", {"fqn": "eval-x.DB.SC.OLIST_ORDERS"})))
    assert out["table"] == "OLIST_ORDERS"
    assert {c["name"] for c in out["columns"]} == {"order_id", "order_status"}


def test_sample_data_unwraps_sample(tmp_path):
    ex = ToolExecutor(FakeMCP(), str(tmp_path))
    out = json.loads(asyncio.run(ex.run("sample_data", {"table_fqn": "DB.SC.OLIST_ORDERS"})))
    assert out == {"columns": ["order_id"], "rows": [["abc"]]}


def test_query_triplet_logs_sql_and_collects_rows(tmp_path):
    ex = ToolExecutor(FakeMCP(), str(tmp_path))
    asyncio.run(ex.run("generate_sql", {"question": "avg score late vs on-time?"}))
    artifact = asyncio.run(ex.run("execute_query", {"sql": "SELECT 42"}))
    assert artifact == "artifact:xyz"
    asyncio.run(ex.run("get_result_page", {"artifact_fqn": artifact}))
    assert ex.sql_log == [("avg score late vs on-time?", "SELECT 42")]
    assert ex.collected == [
        {"question": "avg score late vs on-time?", "columns": ["AVG"], "rows": [["4.0"]]}
    ]


def test_chart_renders_png(tmp_path):
    import os
    ex = ToolExecutor(FakeMCP(), str(tmp_path))
    msg = asyncio.run(ex.run(
        "generate_plotly_chart",
        {"chart_type": "bar", "data": [{"x": "a", "y": 1}], "options": {"title": "t"}},
    ))
    assert "chart_1.png" in msg
    assert os.path.getsize(ex.chart_paths[0]) > 0


def test_tool_error_is_returned_as_string(tmp_path):
    class BoomMCP:
        async def _call(self, tool, args):
            raise RuntimeError("mcp exploded")
    ex = ToolExecutor(BoomMCP(), str(tmp_path))
    out = asyncio.run(ex.run("generate_sql", {"question": "q"}))
    assert out.startswith("ERROR:") and "mcp exploded" in out


def test_unknown_tool_reported(tmp_path):
    ex = ToolExecutor(FakeMCP(), str(tmp_path))
    assert "unknown tool" in asyncio.run(ex.run("nope", {}))


def test_get_result_page_retries_transient_outage(tmp_path, monkeypatch):
    """em-runtime's result endpoints intermittently return a malformed shape. The bridge
    should retry and succeed, not surface the error to the model on the first blip."""
    import apps.seller_delivery_agent.tools as tools_mod
    monkeypatch.setattr(tools_mod.asyncio, "sleep", lambda *_a, **_k: _noop())  # no real delay

    class FlakyMCP:
        def __init__(self):
            self.attempts = 0

        async def _call(self, tool, args):
            self.attempts += 1
            if self.attempts < 3:  # fail twice, then succeed
                return {"ok": True}  # missing 'preview' -> MCPResponseError
            return {"preview": {"columns": ["N"], "rows": [["99224"]]}}

    ex = ToolExecutor(FlakyMCP(), str(tmp_path))
    out = asyncio.run(ex.run("get_result_page", {"artifact_fqn": "artifact:x"}))
    assert json.loads(out) == {"columns": ["N"], "rows": [["99224"]]}
    assert ex.collected[0]["rows"] == [["99224"]]


def test_get_result_page_gives_clear_error_after_exhausting_retries(tmp_path, monkeypatch):
    import apps.seller_delivery_agent.tools as tools_mod
    monkeypatch.setattr(tools_mod.asyncio, "sleep", lambda *_a, **_k: _noop())

    class DeadMCP:
        async def _call(self, tool, args):
            return {"ok": True}  # always malformed

    ex = ToolExecutor(DeadMCP(), str(tmp_path))
    out = asyncio.run(ex.run("get_result_page", {"artifact_fqn": "artifact:x"}))
    assert out.startswith("ERROR:") and "retry" in out.lower()


async def _noop():
    return None
