"""Pure rendering of the final state into markdown + a plotly figure dict."""
import re

BADGE = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}

# Strict CVE-ID format (spec §7): CVE-YYYY-NNNN (4+ digit sequence number).
_CVE_STRICT = re.compile(r"^CVE-\d{4}-\d{4,}$")
# Loose scan so we catch malformed look-alikes (e.g. "CVE-23-1", "CVE-2023-1")
# that an LLM/hindsight source might surface — these get flagged, not trusted.
_CVE_LOOSE = re.compile(r"\bCVE-[A-Za-z0-9-]+\b")


def _sanitize_advisory_ids(text: str) -> str:
    """Drop the authoritative-looking CVE-ID token from LLM/hindsight text
    unless it matches the real CVE-ID format. Un-cited/malformed IDs must
    never render as if verified (spec §7 integrity guard)."""
    if not text:
        return text
    return _CVE_LOOSE.sub(
        lambda m: m.group(0) if _CVE_STRICT.match(m.group(0)) else "[unverified advisory ID]",
        text)


def _lacks_dependents_coverage(tool: dict) -> bool:
    """DEPENDENTS (PyPI) coverage is sparse — a 0-row result reads as a clean
    'GREEN' blast-radius verdict but actually means "not measured", not "low
    risk" (spec §6 honesty rule). Flag it so the report doesn't overstate it."""
    blast = (tool.get("signals") or {}).get("blast") or {}
    return blast.get("dependent_count") is None


def render_markdown(state: dict) -> str:
    tools = state.get("tools", [])
    lines = ["# 🔴🟡🟢 LLM / AI Safety Check", "",
             "*Red light, green light for self-hosted AI — would you run this on your laptop?*", "",
             "## Leaderboard", "",
             "| Verdict | Tool | Category | Significance | What happened next |",
             "|---|---|---|---|---|"]
    any_uncovered = False
    for t in tools:
        hs = _sanitize_advisory_ids((t.get("hindsight") or {}).get("tag", ""))
        marker = ""
        if _lacks_dependents_coverage(t):
            marker, any_uncovered = " ⚠️¹", True
        lines.append(f"| {BADGE.get(t['verdict'], '')} {t['verdict']}{marker} | {t['name']} | "
                     f"{t['category']} | {t.get('significance', '')} | {hs} |")
    if any_uncovered:
        lines.append("")
        lines.append("⚠️¹ *no PyPI dependents data in the snapshot for this tool — the "
                     "blast-radius signal was not measured, not verified low-risk.*")
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
            detail = sig.get("detail", "")
            if key == "blast" and sig.get("dependent_count") is None:
                detail += " — ⚠️ no coverage in snapshot, not a verified measurement"
            lines.append(f"- **{key}:** {detail}")
        hs = t.get("hindsight") or {}
        if hs.get("source_url"):
            lines.append(f"- **What actually happened:** {_sanitize_advisory_ids(hs.get('tag'))} "
                         f"([source]({hs['source_url']}))")
        lines.append("")
    # Common dangers
    lines += ["## Common Dangers", ""]
    for d in state.get("dangers", []):
        seen = ", ".join(d.get("seen_in", []))
        pattern = _sanitize_advisory_ids(d.get("pattern", ""))
        remediation = _sanitize_advisory_ids(d.get("remediation", ""))
        lines.append(f"- **{pattern}** — seen in {seen}. "
                     f"*Unscrew:* {remediation}")
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
