import asyncio
import json
import os
from datetime import datetime, timezone

from . import config, report
from .graph import build_graph


async def run(*, craft=None, llm=None, tavily=None) -> dict:
    if craft is None:
        from .craft_client import CraftClient
        craft = CraftClient()
    if llm is None:
        from .nebius_llm import NebiusLLM
        llm = NebiusLLM()
    if tavily is None:
        from .tavily_client import TavilyClient
        tavily = TavilyClient()
    graph = build_graph(craft, llm, tavily)
    return await graph.ainvoke({"sql_log": [], "cases": list(config.PINNED_CASES)})


def _create_run_dir() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join("runs", f"safety_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


def save_artifacts(state: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(report.render_markdown(state))
    with open(os.path.join(out_dir, "state.json"), "w") as f:
        json.dump(state, f, indent=2, default=str)
    with open(os.path.join(out_dir, "sql_queries.txt"), "w") as f:
        for tool in state.get("tools", []):
            for label, sql in tool.get("sql_log", []):
                f.write(f"-- {label}\n{sql}\n\n")
    try:
        import plotly.io as pio
        fig = report.leaderboard_figure(state)
        pio.write_image(fig, os.path.join(out_dir, "leaderboard.png"),
                        width=1000, height=600)
    except Exception:
        pass  # kaleido optional; PNG is a nicety


def main() -> None:
    state = asyncio.run(run())
    out = _create_run_dir()
    save_artifacts(state, out)
    print(f"Wrote report to {out}/report.md")


if __name__ == "__main__":
    main()
