"""CLI entrypoint and orchestration for the root-cause investigator.

The investigation is LLM-orchestrated: Claude discovers the schema, forms and tests
hypotheses, and writes the root-cause report via the loop in llm.run_investigation,
backed by a ToolExecutor over the live CRAFT MCP session. All logic lives in run(); the
CLI and the Streamlit UI both call it.
"""
import argparse
import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from .craft_client import CraftClient
from .llm import run_investigation
from .tools import ToolExecutor

# A verified investigation prompt that exercises the delivery↔review thesis end-to-end —
# used as the CLI default and as an example in the UI.
DEFAULT_QUESTION = (
    "Late deliveries seem to be hurting customer satisfaction. Is that true, how big is "
    "the impact, and which product categories are worst affected?"
)


@dataclass
class RunResult:
    out_dir: str
    question: str
    report: str
    notes: list[str] = field(default_factory=list)
    chart_paths: list[str] = field(default_factory=list)
    sql_log: list[tuple[str, str]] = field(default_factory=list)
    collected: list[dict] = field(default_factory=list)


def run_dir(ts: str, base: str = "runs") -> str:
    return os.path.join(os.path.dirname(__file__), base, f"investigation_{ts}")


def write_outputs(out_dir: str, result_report: str, question: str, executor) -> None:
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(f"# Investigation\n\n**Question:** {question}\n\n---\n\n{result_report}\n")
    with open(os.path.join(out_dir, "reasoning_trace.md"), "w") as f:
        f.write("# Reasoning trace (the model's own notes, in order)\n\n")
        for i, note in enumerate(executor.notes, 1):
            f.write(f"{i}. {note}\n")
    with open(os.path.join(out_dir, "sql_queries.txt"), "w") as f:
        for label, sql in executor.sql_log:
            f.write(f"-- {label}\n{sql}\n\n")
    with open(os.path.join(out_dir, "raw_data.json"), "w") as f:
        json.dump(executor.collected, f, indent=2)


async def run(
    question: str,
    on_event: Callable[[str, str], None] | None = None,
) -> RunResult:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = run_dir(ts)
    os.makedirs(out_dir, exist_ok=True)

    if on_event:
        on_event("status", "Starting investigation…")
    async with CraftClient() as client:
        executor = ToolExecutor(client, out_dir)
        report = await run_investigation(executor, question, on_event=on_event)

    write_outputs(out_dir, report, question, executor)
    if on_event:
        on_event("status", "Done")
    return RunResult(
        out_dir=out_dir,
        question=question,
        report=report,
        notes=executor.notes,
        chart_paths=executor.chart_paths,
        sql_log=executor.sql_log,
        collected=executor.collected,
    )


def _cli_event(kind: str, detail: str) -> None:
    prefix = {"note": "💭", "tool": "→", "status": "•"}.get(kind, "•")
    print(f"{prefix} {detail}")


def main():
    parser = argparse.ArgumentParser(description="Marketplace Root-Cause Investigator")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION,
                        help="The question / symptom to investigate.")
    args = parser.parse_args()
    result = asyncio.run(run(args.question, on_event=_cli_event))
    print("\n" + "=" * 70 + "\n")
    print(result.report)
    print(f"\nOutputs in: {result.out_dir}")


if __name__ == "__main__":
    main()
