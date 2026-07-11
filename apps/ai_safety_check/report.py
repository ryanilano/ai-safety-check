"""Pure rendering of the final state into markdown + a plotly figure dict."""

BADGE = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}


def render_markdown(state: dict) -> str:
    tools = state.get("tools", [])
    lines = ["# 🔴🟡🟢 LLM / AI Safety Check", "",
             "*Red light, green light for self-hosted AI — would you run this on your laptop?*", "",
             "## Leaderboard", "",
             "| Verdict | Tool | Category | Significance | What happened next |",
             "|---|---|---|---|---|"]
    for t in tools:
        hs = (t.get("hindsight") or {}).get("tag", "")
        lines.append(f"| {BADGE.get(t['verdict'], '')} {t['verdict']} | {t['name']} | "
                     f"{t['category']} | {t.get('significance', '')} | {hs} |")
    # Case studies
    lines += ["", "## Case Studies", ""]
    by_name = {t["name"]: t for t in tools}
    for name in state.get("cases", []):
        t = by_name.get(name)
        if not t:
            continue
        lines.append(f"### {BADGE.get(t['verdict'], '')} {name}")
        lines.append(f"*{t.get('significance', '')}*")
        for key, sig in t.get("signals", {}).items():
            lines.append(f"- **{key}:** {sig.get('detail', '')}")
        hs = t.get("hindsight") or {}
        if hs.get("source_url"):
            lines.append(f"- **What actually happened:** {hs.get('tag')} "
                         f"([source]({hs['source_url']}))")
        lines.append("")
    # Common dangers
    lines += ["## Common Dangers", ""]
    for d in state.get("dangers", []):
        seen = ", ".join(d.get("seen_in", []))
        lines.append(f"- **{d.get('pattern')}** — seen in {seen}. "
                     f"*Unscrew:* {d.get('remediation')}")
    return "\n".join(lines)


def leaderboard_figure(state: dict) -> dict:
    tools = state.get("tools", [])
    colors = {"RED": "#e5484d", "YELLOW": "#f5a623", "GREEN": "#30a46c"}
    names = [t["name"] for t in tools]
    stars = [t.get("stars") or 0 for t in tools]
    bar_colors = [colors.get(t["verdict"], "#888") for t in tools]
    return {
        "data": [{"type": "bar", "x": stars, "y": names, "orientation": "h",
                  "marker": {"color": bar_colors}}],
        "layout": {"title": "AI tools by popularity, colored by safety verdict",
                   "xaxis": {"title": "GitHub stars"}, "height": 500},
    }
