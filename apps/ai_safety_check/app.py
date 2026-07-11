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
st.title("🔴🟡🟢 LLM / AI safety check")
st.caption("Red light, green light for self-hosted AI — would you run this on your laptop?")


def _latest_state():
    runs = sorted(glob.glob("runs/safety_*/state.json"))
    if not runs:
        return None
    with open(runs[-1]) as f:
        return json.load(f)


state = st.session_state.get("state") or _latest_state()

col_run, col_ask = st.columns([1, 2])
with col_run:
    if st.button("Re-run live", icon=":material/refresh:"):
        with st.status("Running safety check…", expanded=True) as status:
            state = asyncio.run(main.run())
            out_dir = main._create_run_dir()
            main.save_artifacts(state, out_dir)
            st.session_state["state"] = state
            status.update(label=f"Done — saved to {out_dir}", state="complete")
with col_ask:
    q = st.text_input("Ask the supply chain (plain English):",
                      placeholder="Which AI agents execute code but have unpatched critical CVEs?")
    if q:
        from apps.ai_safety_check.craft_client import CraftClient
        craft = CraftClient()
        result, sql = asyncio.run(craft.nl_query(
            q, config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN))
        st.dataframe({c: [r[i] for r in result.get("rows", [])]
                      for i, c in enumerate(result.get("columns", []))})
        with st.expander("Generated SQL", icon=":material/code:"):
            st.code(sql, language="sql")

if state:
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

    left, right = st.columns([3, 2])
    with left:
        st.markdown(report.render_markdown(state))
    with right:
        with st.container(border=True):
            st.plotly_chart(report.leaderboard_figure(state), width="stretch")
        if state.get("errors"):
            with st.expander("Run warnings", icon=":material/warning:"):
                for e in state["errors"]:
                    st.caption(e)
        st.caption("Signals: CVE load · dangerous capability · staleness · "
                   "blast radius · upstream health · identity trust — "
                   "graded live from deps.dev via CRAFT text-to-SQL.")
else:
    st.info("No cached run yet. Click **Re-run live** to generate one.",
            icon=":material/play_circle:")
