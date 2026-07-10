import pytest

from apps.seller_delivery_agent.craft_client import (
    MCPResponseError,
    parse_execute_query,
    parse_generate_sql,
    parse_plotly,
    parse_result_page,
)


def test_parse_generate_sql_extracts_sql():
    resp = {"ok": True, "generate_sql": {"session_id": "x", "sql": "SELECT 1", "explanation": "e", "assumptions": []}}
    assert parse_generate_sql(resp) == "SELECT 1"


def test_parse_execute_query_unwraps_result_key():
    resp = {"result": {"ok": True, "execute_query": {"artifact_fqn": "artifact:abc", "row_count": 2, "truncated": False, "sql": "..."}}}
    assert parse_execute_query(resp) == "artifact:abc"


def test_parse_execute_query_without_result_wrapper():
    resp = {"ok": True, "execute_query": {"artifact_fqn": "artifact:def"}}
    assert parse_execute_query(resp) == "artifact:def"


def test_parse_result_page_returns_columns_and_rows():
    resp = {"ok": True, "preview": {"columns": ["DELIVERY_STATUS", "AVG_REVIEW_SCORE"], "rows": [["late", "2.54"], ["on_time", "4.0"]], "total_rows": 2}}
    cols, rows = parse_result_page(resp)
    assert cols == ["DELIVERY_STATUS", "AVG_REVIEW_SCORE"]
    assert rows == [["late", "2.54"], ["on_time", "4.0"]]


def test_parse_plotly_unwraps_triple_nesting():
    resp = {"generate_plotly_chart": {"success": True, "plotly_json": {"success": True, "plotly_json": {"data": [{"type": "bar"}], "layout": {"title": "t"}}}}}
    fig = parse_plotly(resp)
    assert fig["data"] == [{"type": "bar"}]
    assert fig["layout"] == {"title": "t"}


# --- malformed / transient-outage handling: a clear error, not an opaque KeyError ---
def test_result_page_missing_preview_raises_clear_error():
    # This is the exact shape seen during a live em-runtime outage.
    with pytest.raises(MCPResponseError) as exc:
        parse_result_page({"ok": True})  # no 'preview' key
    msg = str(exc.value)
    assert "get_result_page" in msg and "retry" in msg.lower()


def test_explicit_error_payload_is_surfaced():
    resp = {"ok": False, "error": {"code": "talk2data_error", "message": "boom"}}
    with pytest.raises(MCPResponseError) as exc:
        parse_execute_query(resp)
    assert "boom" in str(exc.value)


def test_generate_sql_missing_key_raises_clear_error():
    with pytest.raises(MCPResponseError):
        parse_generate_sql({"ok": True})  # no 'generate_sql' key
