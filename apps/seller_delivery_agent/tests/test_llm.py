"""Unit tests for the investigation loop's control flow, with a fake Anthropic client and
a fake tool executor — no network. Verifies tool orchestration, note/tool event emission,
the max_tokens-truncation safety, and turn-budget compose."""
import asyncio

from apps.seller_delivery_agent import llm


class Block:
    def __init__(self, type, text=None, name=None, input=None, id=None):
        self.type = type
        self.text = text
        self.name = name
        self.input = input or {}
        self.id = id


class Resp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def create(self, **kwargs):
        snapshot = dict(kwargs)
        if "messages" in snapshot:
            snapshot["messages"] = list(snapshot["messages"])
        self.calls.append(snapshot)
        return self._script.pop(0)


class FakeAnthropic:
    def __init__(self, script):
        self.messages = FakeMessages(script)


class FakeExecutor:
    def __init__(self):
        self.ran = []
        self.notes = []

    async def run(self, name, tool_input):
        self.ran.append((name, tool_input))
        if name == "note":
            self.notes.append(tool_input.get("thought"))
            return "noted"
        return "OK"


REPORT = "## Answer\nRoot cause is X.\n## Evidence\n..."


def _run(script, monkeypatch, executor=None, **kw):
    fake = FakeAnthropic(script)
    monkeypatch.setattr(llm, "make_client", lambda: fake)
    ex = executor or FakeExecutor()
    events = []
    result = asyncio.run(
        llm.run_investigation(ex, "why?", on_event=lambda k, d: events.append((k, d)), **kw)
    )
    return result, fake, ex, events


def test_note_then_query_then_report(monkeypatch):
    script = [
        Resp([Block("tool_use", name="note", input={"thought": "checking home_garden"}, id="n1")], "tool_use"),
        Resp([Block("tool_use", name="generate_sql", input={"question": "q"}, id="t1")], "tool_use"),
        Resp([Block("text", text=REPORT)], "end_turn"),
    ]
    result, fake, ex, events = _run(script, monkeypatch)

    assert result == REPORT
    assert ("note", {"thought": "checking home_garden"}) in ex.ran
    assert ("generate_sql", {"question": "q"}) in ex.ran
    # events surfaced the reasoning and the tool call
    assert ("note", "checking home_garden") in events
    assert any(k == "tool" and "generate_sql" in d for k, d in events)


def test_returns_report_when_tools_stop_regardless_of_content_shape(monkeypatch):
    # No 5-section template anymore — any non-empty final text is the report.
    script = [Resp([Block("text", text="## Answer\nShort but valid.")], "end_turn")]
    result, *_ = _run(script, monkeypatch)
    assert result == "## Answer\nShort but valid."


def test_empty_final_turn_triggers_compose(monkeypatch):
    script = [
        Resp([Block("text", text="   ")], "end_turn"),   # empty
        Resp([Block("text", text=REPORT)], "end_turn"),  # composed
    ]
    result, fake, _, _ = _run(script, monkeypatch)
    assert result == REPORT
    assert "tools" not in fake.messages.calls[1]  # compose withholds tools


def test_tool_use_truncated_by_max_tokens_still_matched(monkeypatch):
    script = [
        Resp([Block("tool_use", name="generate_sql", input={}, id="tt")], "max_tokens"),
        Resp([Block("text", text=REPORT)], "end_turn"),
    ]
    result, fake, ex, _ = _run(script, monkeypatch)
    assert result == REPORT
    assert ex.ran == []  # truncated call NOT executed
    user_turn = fake.messages.calls[1]["messages"][-1]
    tr = user_turn["content"][0]
    assert tr["type"] == "tool_result" and tr["tool_use_id"] == "tt"
    assert "truncated" in tr["content"].lower()


def test_turn_budget_forces_compose(monkeypatch):
    tool_turn = Resp([Block("tool_use", name="note", input={"thought": "x"}, id="t")], "tool_use")
    script = [tool_turn, tool_turn, Resp([Block("text", text=REPORT)], "end_turn")]
    result, fake, _, _ = _run(script, monkeypatch, max_turns=2)
    assert result == REPORT
    assert "tools" not in fake.messages.calls[-1]
