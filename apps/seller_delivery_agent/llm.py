"""LLM client factory + the agentic investigation loop.

Claude orchestrates: given the tools (backed by ToolExecutor) it discovers the schema,
forms and tests hypotheses, follows the evidence, and writes the final root-cause report.
Auth prefers Vertex AI (Google Cloud ADC) when its env vars are present, else the direct
Anthropic API.
"""
import os
from typing import Callable

from . import prompts
from .tools import TOOL_DEFINITIONS


def make_client():
    """Vertex AI (ADC) when its env vars are set, else the direct Anthropic API.
    Vertex uses bare model IDs, so the same model string works on both paths."""
    project = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if project:
        from anthropic import AnthropicVertex

        region = os.environ.get("CLOUD_ML_REGION", "global")
        return AnthropicVertex(project_id=project, region=region)

    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def _text_of(message) -> str:
    return "".join(b.text for b in message.content if b.type == "text")


async def run_investigation(
    executor,
    question: str,
    *,
    model: str = "claude-sonnet-5",
    max_turns: int = 60,
    on_event: Callable[[str, str], None] | None = None,
) -> str:
    """Drive the investigation loop until Claude stops calling tools.

    Returns the final report text. `executor` is a ToolExecutor whose side effects
    (sql_log, collected, chart_paths, notes) accumulate as Claude works.

    on_event(kind, detail) is called for each step: kind is one of
    "note" | "tool" | "status"; detail is the human-readable text.
    """
    def emit(kind: str, detail: str) -> None:
        if on_event:
            on_event(kind, detail)

    client = make_client()
    messages = [{"role": "user", "content": prompts.user_message(question)}]
    system = prompts.system_prompt()

    for _ in range(max_turns):
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            system=system,
            thinking={"type": "disabled"},
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        tool_uses = [b for b in resp.content if b.type == "tool_use"]

        # No tool calls → the model is done; its text is the report. (Key off tool_use
        # presence, not stop_reason: a turn can carry a tool_use block AND hit max_tokens.)
        if not tool_uses:
            report = _text_of(resp)
            if report.strip():
                return report
            # Empty final turn (rare) — ask once more for the report, tools withheld.
            emit("status", "Composing final report…")
            return _compose_report(client, model, system, messages)

        truncated = resp.stop_reason == "max_tokens"
        tool_results = []
        for block in tool_uses:
            if truncated:
                result = "ERROR: response truncated before the tool call completed; retry."
            elif block.name == "note":
                # Narration: surface it, record it, no data-plane call.
                thought = block.input.get("thought", "")
                emit("note", thought)
                result = await executor.run("note", block.input)
            else:
                emit("tool", f"{block.name}: {_summarize_input(block.name, block.input)}")
                result = await executor.run(block.name, block.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )
        messages.append({"role": "user", "content": tool_results})

    # Turn budget exhausted — compose the report with tools withheld.
    emit("status", "Composing report (turn budget reached)…")
    return _compose_report(client, model, system, messages)


def _compose_report(client, model, system, messages) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=system,
        thinking={"type": "disabled"},
        messages=messages
        + [
            {
                "role": "user",
                "content": (
                    "Stop investigating and write your final report now, using the evidence "
                    "you gathered. Do not call any tools. Lead with the Answer (root cause), "
                    "then Evidence, Recommendation, and Caveats."
                ),
            }
        ],
    )
    return _text_of(resp)


def _summarize_input(name: str, tool_input: dict) -> str:
    """Short preview of a tool call for the live trace."""
    if name == "search_schema":
        return tool_input.get("query", "")
    if name == "get_schema":
        return tool_input.get("fqn", "").split(".")[-1]
    if name == "sample_data":
        return tool_input.get("table_fqn", "").split(".")[-1]
    if name == "generate_sql":
        q = tool_input.get("question", "")
        return q if len(q) <= 90 else q[:87] + "..."
    if name == "execute_query":
        return "running query"
    if name == "get_result_page":
        return "reading results"
    if name == "generate_plotly_chart":
        opts = tool_input.get("options") or {}
        return opts.get("title", tool_input.get("chart_type", "chart"))
    return ""
