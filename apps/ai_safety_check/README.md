# 🔴🟡🟢 AI/LLM Safety Check

*Red light, green light for self-hosted AI — would you run this on your laptop?*

A LangGraph agent that grades popular self-hosted AI tools (agents, inference
servers, orchestration frameworks, vector DBs, gateways) on **supply-chain
risk**, using nothing but natural-language questions against the
[deps.dev](https://deps.dev) public dataset via the **CRAFT MCP** semantic
layer — no hand-written SQL. A reasoning LLM (Nemotron via **Nebius Token
Factory**) classifies the tools and synthesizes verdicts; Tavily web search
adds "what happened next" hindsight from after the dataset's snapshot.

**Live demo:** static results at
[ryanilano.github.io/ai-safety-check](https://ryanilano.github.io/ai-safety-check/) ·
Streamlit app renders the cached run with zero credentials.

## How it grades

Six signals per tool, each answered by CRAFT text-to-SQL over deps.dev:

| Signal | Question asked (in English) | RED example |
|---|---|---|
| CVE load | advisories joined to package versions | mlflow: 5 critical, worst CVSS 10.0 |
| Dangerous capability | from LLM classification (executes code, exposes server…) | agents that run their own plans |
| Staleness | most recent upstream release | abandoned 2+ years |
| Blast radius | distinct transitive dependents | — (sparse PyPI coverage is disclosed, not scored GREEN) |
| Upstream health | stars / forks / open issues | — |
| Identity trust | version counts across ecosystems | `anthropic` on PyPI: lone-version vendor-name squat |

Composite verdict: 🔴 don't run / 🟡 caution / 🟢 go. The hindsight column is
the punchline — the dataset snapshot ends ~mid-2023, so the pipeline's
predictions can be checked against what actually happened (mlflow graded RED
*before* its CVSS-10 CVEs were public knowledge).

## Pipeline

```
discover (deps.dev PROJECTS) → classify (Nemotron) → gate (6 SQL signals/tool)
    → hindsight (Tavily + Nemotron) → dangers (Nemotron) → report + leaderboard
```

Five LangGraph nodes over a typed state; every generated SQL statement is
written to the run's audit trail. Failures degrade per-tool (a broken tool
grades YELLOW with the error recorded) rather than killing the run.

## Run it

```bash
cd apps/ai_safety_check
uv sync                      # or: python3 -m venv .venv && .venv/bin/pip install -r ../../requirements.txt
cp .env.template .env        # fill in (see below)
uv run python scripts/get_token.py   # one-time browser SSO → KEYCLOAK_REFRESH_TOKEN

# full pipeline run (writes runs/safety_<ts>/: report.md, state.json, sql audit, chart)
PYTHONPATH=../.. .venv/bin/python -m apps.ai_safety_check.main

# UI (renders the newest cached run; Re-run live + ask-box need credentials)
.venv/bin/streamlit run app.py
```

`.env` keys: `MCP_URL`, `PROJECT_ID`, `KEYCLOAK_URL`, `KEYCLOAK_REFRESH_TOKEN`,
`DEPS_CONNECTION`, `GITHUB_CONNECTION`, `NEBIUS_API_KEY` (+ optional
`TAVILY_API_KEY` for hindsight). **Without any credentials the Streamlit app
still works** — it renders the committed cached run in read-only demo mode
(that's how the public deployment runs).

### Ask the supply chain

The app's chat box sends plain English straight to CRAFT `generate_sql`
against the deps.dev connection — "Looking for agents?", "What's popular that
has major issues?" — and shows the rows plus the generated SQL.

## Tests

```bash
# from the repo root
apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/ -q
```

49 tests, hand-rolled fakes + monkeypatch, no network. Notable regression
tests came from real live-run failures: CRAFT nests generated SQL under the
tool name in its response, Nemotron returning a JSON array of strings instead
of objects, and the empty-summary hallucination guard in the dangers node.

## Layout

```
apps/ai_safety_check/
├── app.py            # Streamlit UI (hero, bad-repos cards, leaderboard, ask box)
├── main.py           # CLI entry; writes the run-artifact trail
├── graph.py          # LangGraph wiring (5 nodes, discovery backtrack)
├── nodes.py          # node implementations; column-name-aware row parsing
├── queries.py        # every natural-language question sent to CRAFT
├── gating.py         # signal grading thresholds + composite verdict
├── classify.py       # candidate → tool classification parsing/filtering
├── craft_client.py   # CRAFT MCP JSON-RPC client (Keycloak refresh-token auth)
├── nebius_llm.py     # OpenAI-compatible client for Nebius Token Factory
├── tavily_client.py  # optional hindsight web search
├── report.py         # markdown report + plotly leaderboard (CVE-ID validation,
│                     # blast-radius coverage disclosure)
├── runs/             # committed cached demo runs (newest is what the app shows)
└── scripts/get_token.py  # headless-friendly Keycloak SSO helper
```

Built for the Nebius × Emergence hackathon on the CRAFT semantic data platform.
