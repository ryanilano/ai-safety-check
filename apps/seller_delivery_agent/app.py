"""Streamlit UI for the Marketplace Root-Cause Investigator.

Ask any question about the marketplace data. Claude orchestrates the investigation itself
— discovering the schema, forming and testing hypotheses, and following the evidence — and
you watch it reason live. Run with:  streamlit run apps/seller_delivery_agent/app.py
"""
import asyncio
import os
import sys

# `streamlit run apps/seller_delivery_agent/app.py` executes this file as a top-level script
# (module name "__main__"), so relative imports have no package. Put the repo root on
# sys.path and import the package absolutely — this works both under `streamlit run` and as
# a module. app.py lives two directories below repo root (apps/seller_delivery_agent/app.py),
# so dirname must be applied three times: once to get from the file to its directory, then
# once per directory level up to repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from apps.seller_delivery_agent import config
from apps.seller_delivery_agent.agent import DEFAULT_QUESTION, run
from apps.seller_delivery_agent.craft_auth import build_oauth_provider

EXAMPLE_QUESTIONS = [
    DEFAULT_QUESTION,
    "Which product category is quietly hurting us the most, and why?",
    "Are freight costs unusually high for any region, and what's driving it?",
    "Did anything change in the second half of the data that hurt on-time delivery?",
    "Which payment method correlates with the worst customer experience?",
]

st.set_page_config(page_title="Marketplace Investigator", page_icon="🔎", layout="wide")
st.title("🔎 Marketplace Root-Cause Investigator")
st.caption(
    "Ask a question about the marketplace data. **Claude orchestrates the whole "
    "investigation itself** — it discovers the schema, forms hypotheses, writes and runs "
    "the SQL, follows the evidence, and reports the root cause. Every query goes through "
    "the CRAFT MCP server; none are hand-written. Watch it reason live below."
)


async def _check_connection() -> str:
    auth = await build_oauth_provider()
    async with streamablehttp_client(config.MCP_URL, auth=auth, headers=config.HEADERS) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("hello_world", {})
            return result.content[0].text


with st.sidebar:
    st.header("Connection")
    st.write("Complete OAuth once before running (opens a browser tab).")
    if st.button("Check connection"):
        with st.spinner("Contacting em-runtime…"):
            try:
                st.success(f"Connected: {asyncio.run(_check_connection())}")
            except Exception as e:
                st.error(f"Connection failed: {e}")
    st.divider()
    st.caption("Example questions")
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, key=f"ex_{hash(q)}"):
            st.session_state["question"] = q

question = st.text_area(
    "What do you want to investigate?",
    value=st.session_state.get("question", DEFAULT_QUESTION),
    height=90,
)

if st.button("🔎 Investigate", type="primary"):
    trace_box = st.container()
    trace_box.subheader("Live reasoning trace")
    status = trace_box.status("Investigating…", expanded=True)

    def on_event(kind: str, detail: str) -> None:
        icon = {"note": "💭", "tool": "🔧", "status": "•"}.get(kind, "•")
        if kind == "note":
            status.markdown(f"💭 **{detail}**")  # the model's own reasoning — emphasized
        else:
            status.write(f"{icon} {detail}")

    try:
        result = asyncio.run(run(question, on_event=on_event))
        status.update(label="Investigation complete", state="complete")
        st.session_state["result"] = result
    except Exception as e:
        status.update(label="Investigation failed", state="error")
        st.exception(e)

result = st.session_state.get("result")
if result is not None:
    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Findings")
        st.markdown(result.report)
    with right:
        for path in result.chart_paths or []:
            st.image(path, use_container_width=True)
    with st.expander(f"💭 The model's reasoning ({len(result.notes)} notes)"):
        for i, note in enumerate(result.notes or [], 1):
            st.markdown(f"{i}. {note}")
    with st.expander(f"🔍 Generated SQL — the LLM wrote every one ({len(result.sql_log)} queries)"):
        for label, sql in result.sql_log or []:
            st.markdown(f"**{label}**")
            st.code(sql, language="sql")
    st.caption(f"Outputs saved to `{result.out_dir}`")
