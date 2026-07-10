import asyncio
import json
import os

import apps.seller_delivery_agent.agent as agent


class FakeExecutor:
    def __init__(self):
        self.notes = ["hypothesis A", "A confirmed; drilling into category"]
        self.sql_log = [("orders by category?", "SELECT category, COUNT(*) ...")]
        self.chart_paths = ["chart_1.png"]
        self.collected = [{"question": "orders by category?", "columns": ["c"], "rows": [["x"]]}]


def test_write_outputs_creates_all_files(tmp_path):
    out = str(tmp_path / "run")
    os.makedirs(out)
    agent.write_outputs(out, "## Answer\nRoot cause X.", "why did orders drop?", FakeExecutor())

    report = open(os.path.join(out, "report.md")).read()
    assert "why did orders drop?" in report and "Root cause X." in report
    assert "hypothesis A" in open(os.path.join(out, "reasoning_trace.md")).read()
    assert "SELECT category" in open(os.path.join(out, "sql_queries.txt")).read()
    assert json.load(open(os.path.join(out, "raw_data.json")))[0]["question"] == "orders by category?"


def test_run_orchestrates_via_investigation_and_returns_result(tmp_path, monkeypatch):
    """run() wires a live MCP session + ToolExecutor into the investigation loop, captures
    the executor's side effects into the RunResult, forwards events, and writes outputs."""

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    async def fake_run_investigation(executor, question, **kwargs):
        executor.notes.append("late orders average 2.6 stars vs 4.0 on-time")
        executor.sql_log.append(("late vs on-time review?", "SELECT ..."))
        executor.collected.append({"question": "late vs on-time review?", "columns": ["s"], "rows": [["2.6"]]})
        executor.chart_paths.append("chart_1.png")
        on_event = kwargs.get("on_event")
        if on_event:
            on_event("note", "late orders average 2.6 stars vs 4.0 on-time")
        return "## Answer\nLate delivery is the root cause."

    monkeypatch.setattr(agent, "CraftClient", lambda: FakeClient())
    monkeypatch.setattr(agent, "run_investigation", fake_run_investigation)
    monkeypatch.setattr(agent, "run_dir", lambda ts, base="runs": str(tmp_path / "r"))

    events = []
    result = asyncio.run(agent.run("why are reviews low?", on_event=lambda k, d: events.append((k, d))))

    assert result.report.startswith("## Answer")
    assert result.question == "why are reviews low?"
    assert result.sql_log == [("late vs on-time review?", "SELECT ...")]
    assert result.chart_paths == ["chart_1.png"]
    assert "late orders average 2.6 stars vs 4.0 on-time" in result.notes
    assert ("status", "Done") == events[-1]
    # outputs written
    assert os.path.exists(os.path.join(result.out_dir, "report.md"))
    assert "SELECT ..." in open(os.path.join(result.out_dir, "sql_queries.txt")).read()
