import os
import sys
import glob
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from apps.ai_safety_check import report, main
from apps.ai_safety_check import config

st.set_page_config(page_title="AI Safety Check", page_icon="🚦", layout="wide")

VERDICT_DOT = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}


def _latest_state():
    runs = sorted(glob.glob("runs/safety_*/state.json"))
    if not runs:
        return None
    with open(runs[-1]) as f:
        return json.load(f)


def _sections(md: str) -> dict:
    """Split the rendered report into its '## ' sections (title -> body)."""
    out, title, buf = {}, None, []
    for line in md.splitlines():
        if line.startswith("## "):
            if title:
                out[title] = "\n".join(buf).strip()
            title, buf = line[3:].strip(), []
        elif title:
            buf.append(line)
    if title:
        out[title] = "\n".join(buf).strip()
    return out


state = st.session_state.get("state") or _latest_state()

# ── Index (left) ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Index")
    st.markdown(
        "- [Use natural language](#ask)\n"
        "- [Bad repos](#bad-repos)\n"
        "- [Leaderboard](#leaderboard)\n"
        "- [Case studies](#case-studies)\n"
        "- [Common dangers](#common-dangers)"
    )
    st.markdown("### Controls")
    if st.button("Re-run live", icon=":material/refresh:"):
        with st.status("Running safety check…", expanded=True) as status:
            state = asyncio.run(main.run())
            out_dir = main._create_run_dir()
            main.save_artifacts(state, out_dir)
            st.session_state["state"] = state
            status.update(label=f"Done — saved to {out_dir}", state="complete")
    st.caption("Signals: CVE load · dangerous capability · staleness · "
               "blast radius · upstream health · identity trust — graded "
               "live from deps.dev via CRAFT text-to-SQL.")

# ── Giant copy (top) ──────────────────────────────────────────────────────────
st.html(
    '<div style="font-size:72px;font-weight:800;line-height:1.05;'
    'letter-spacing:-0.02em;margin-bottom:0.15em">🔴🟡🟢 AI/LLM Safety Tests</div>'
    '<div style="font-size:22px;color:#8a919e;margin-bottom:0.6em">'
    'Red light, green light for self-hosted AI — would you run this on your laptop?</div>'
)

# ── Natural-language ask box (llama-server-style chat box) ───────────────────
st.header("Use natural language", anchor="ask")
st.markdown("""
<style>
[data-testid="stChatInput"] {
  background-color: #242424;
  border: 1px solid #3a3a3a;
  border-radius: 24px;
  padding: 14px 18px;
  min-height: 96px;
  align-items: flex-start;
  width: 100% !important;
  max-width: 100% !important;
}
[data-testid="stChatInput"] > div {
  width: 100% !important;
  max-width: 100% !important;
}
[data-testid="stChatInput"] textarea {
  font-size: 17px;
}
</style>
""", unsafe_allow_html=True)
with st.container():
    submitted = st.chat_input(
        "Lookin' for agents?  ·  What's the best MCP right now?")
if submitted:
    from apps.ai_safety_check.craft_client import CraftClient
    craft = CraftClient()
    with st.spinner("Translating to SQL and querying deps.dev…"):
        result, sql = asyncio.run(craft.nl_query(
            submitted, config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN))
    st.session_state["ask"] = {
        "q": submitted, "sql": sql,
        "table": {c: [r[i] for r in result.get("rows", [])]
                  for i, c in enumerate(result.get("columns", []))}}
if st.session_state.get("ask"):
    ask = st.session_state["ask"]
    st.caption(f"“{ask['q']}”")
    st.dataframe(ask["table"])
    with st.expander("Generated SQL", icon=":material/code:"):
        st.code(ask["sql"], language="sql")

if not state:
    st.info("No cached run yet. Click **Re-run live** to generate one.",
            icon=":material/play_circle:")
    st.stop()

tools = state.get("tools", [])
verdicts = [t.get("verdict") for t in tools]
m_tools, m_red, m_yellow, m_green, m_cves = st.columns(5)
m_tools.metric("Tools graded", len(tools), border=True)
m_red.metric("🔴 Red — don't run", verdicts.count("RED"), border=True)
m_yellow.metric("🟡 Yellow — caution", verdicts.count("YELLOW"), border=True)
m_green.metric("🟢 Green — go", verdicts.count("GREEN"), border=True)
critical = sum(
    (t.get("signals", {}).get("cve", {}).get("counts") or {}).get("CRITICAL", 0)
    for t in tools)
m_cves.metric("Critical advisories", critical, border=True)

# ── Bad repos ─────────────────────────────────────────────────────────────────
st.header("🚨 Bad repos", anchor="bad-repos")
bad = [t for t in tools if t.get("verdict") == "RED"]
if not bad:
    st.caption("No RED verdicts in this run.")
for row in range(0, len(bad), 3):
    cols = st.columns(3)
    for col, t in zip(cols, bad[row:row + 3]):
        with col, st.container(border=True):
            st.subheader(f"🔴 {t['name']}")
            st.caption(f"{t.get('category', '?')} — {t.get('significance', '')}")
            sig = t.get("signals", {})
            cve = sig.get("cve", {})
            if cve.get("detail"):
                st.markdown(f":red-badge[{cve['detail']}]")
            ident = sig.get("identity", {})
            if ident.get("verdict") == "RED":
                st.markdown(f":orange-badge[{ident.get('detail', 'identity risk')}]")
            hind = t.get("hindsight") or {}
            if hind.get("tag"):
                link = f" ([source]({hind['source_url']}))" if hind.get("source_url") else ""
                st.markdown(f"**What happened next:** {hind['tag']}{link}")

# ── Leaderboard ───────────────────────────────────────────────────────────────
sections = _sections(report.render_markdown(state))
st.header("Leaderboard", anchor="leaderboard")
lb_left, lb_right = st.columns([3, 2])
with lb_left:
    st.markdown(sections.get("Leaderboard", ""))
with lb_right:
    with st.container(border=True):
        st.plotly_chart(report.leaderboard_figure(state), width="stretch")

# ── Case studies / dangers ────────────────────────────────────────────────────
st.header("Case studies", anchor="case-studies")
st.markdown(sections.get("Case Studies", ""))

st.header("Common dangers", anchor="common-dangers")
st.markdown(sections.get("Common Dangers", ""))

if state.get("errors"):
    with st.expander("Run warnings", icon=":material/warning:"):
        for e in state["errors"]:
            st.caption(e)
