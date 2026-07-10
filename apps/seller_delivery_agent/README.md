# Seller Delivery Intelligence Agent (Marketplace Root-Cause Investigator)

Ask a free-text question about the marketplace's data and Claude investigates it like a
senior analyst: forms a hypothesis, tests it with real queries, follows the evidence, and
reports the root cause. The default example question chases a specific thesis — the
causal link between **late delivery and low review scores** — but the agent isn't
seller-ID-scoped or tied to that one question; you can ask about freight costs, payment
methods, regional trends, or anything else the marketplace data can answer. Every number
comes from the data itself, pulled **entirely through the CRAFT (em-runtime) MCP
server** — there is no hand-written SQL anywhere in the codebase.

**The agent is LLM-orchestrated.** Claude is given the raw MCP tools and a goal; *it*
decides which schema to explore, which questions to ask, when to run each query, when to
chart, and when it has enough to write the report. There is no hard-coded question list
or fixed pipeline — the tool-call sequence is different every run because the model plans
it.

Built for the Emergence hackathon, riffing on the reference
[Customer Experience Intelligence Agent](../customer-experience-agent/) in this same repo.

---

## What it does

Given a free-text question, Claude runs an **agentic tool-use loop**. It has eight tools,
each backed by our authenticated CRAFT MCP session:

- `note(thought)` — narrate its current hypothesis/reasoning live, before each step
- `search_schema(query)` — find tables/columns by keyword when it doesn't know where something lives
- `get_schema(fqn)` — read a table's columns, types, and business definitions
- `sample_data(table_fqn)` — peek at real rows to understand values and formats
- `generate_sql(question)` — describe an analytical question in words → schema-bound SQL
- `execute_query(sql)` → an artifact handle
- `get_result_page(artifact_fqn)` → the rows
- `generate_plotly_chart(chart_type, data, options)` → a saved PNG

The model discovers the schema itself with the first three tools (no schema is handed to
it up front), sequences the `generate_sql → execute_query → get_result_page` triplet for
each hypothesis it decides to test, narrates its reasoning with `note()` along the way,
builds at least one chart of the key finding, then stops calling tools and writes its
final report as markdown: **Answer, Evidence, Recommendation, Caveats**.

The system prompt sets the goal and the required output shape (guided-agentic); everything
else — the schema exploration, the questions, the order, the depth — is the model's call.
The only step that isn't a tool call is Claude writing the final report.

---

## Prerequisites

- **Python 3.11+** (developed on 3.13).
- **A Keycloak / SSO account** for `runtime.dev.emergence.ai` (Emergence's dev CRAFT
  environment). First run opens a browser for OAuth (once).
- **Claude access.** Two supported auth paths (the code prefers Vertex when its env vars are set):
  - **Vertex AI via Google Cloud ADC** (used in development): `gcloud auth application-default login`,
    then set `ANTHROPIC_VERTEX_PROJECT_ID` and `CLOUD_ML_REGION` (e.g. `global`). No API key needed.
  - **Direct Anthropic API**: set `ANTHROPIC_API_KEY`.

## Setup

```bash
# from the repository root
python3 -m venv .venv
.venv/bin/pip install -r apps/seller_delivery_agent/requirements.txt
```

> This machine has no bare `python` on PATH — use `.venv/bin/python` (shown below). If your
> `python` points at the venv, the plain command works too.

---

## Run

Set your Claude auth first (either path):

```bash
# Vertex AI via ADC (dev default)
export ANTHROPIC_VERTEX_PROJECT_ID=<gcp-project>
export CLOUD_ML_REGION=global
# — or — direct Anthropic API
export ANTHROPIC_API_KEY=sk-ant-...
```

### Web UI (primary — best for a demo)

```bash
.venv/bin/streamlit run apps/seller_delivery_agent/app.py
```

Then in the browser:

1. Click **Check connection** — completes the Keycloak OAuth login on first run and verifies the
   MCP server responds (`hello_world`).
2. Type your own question, or pick one of the example questions in the sidebar.
3. Click **🔎 Investigate** — watch the live reasoning trace, then the report renders on the left,
   any charts on the right, and the model's notes + generated SQL in expanders below.

### CLI (same pipeline, terminal only)

```bash
.venv/bin/python -m apps.seller_delivery_agent.agent ["<question>"]
```

Defaults to the same example question as the UI if you omit it: *"Late deliveries seem to
be hurting customer satisfaction. Is that true, how big is the impact, and which product
categories are worst affected?"* — a verified investigation prompt whose data shows the
thesis clearly: **on-time orders average ~4.0★ vs ~2.5★ for late orders.**

Both entrypoints share the exact same `agent.run()` pipeline; the UI is a thin wrapper.

---

## Outputs

Each run writes to `apps/seller_delivery_agent/runs/investigation_{timestamp}/`:

| File | Description |
| --- | --- |
| `report.md` | The final root-cause report (Answer, Evidence, Recommendation, Caveats) |
| `reasoning_trace.md` | The model's own `note()` narration, in order |
| `chart_1.png`, `chart_2.png`, … | The charts the model chose to build |
| `sql_queries.txt` | Every query the model generated (audit trail — none hand-written) |
| `raw_data.json` | The result rows the model collected, tagged by the question that produced them |

The number of charts and queries varies run-to-run — the model decides.

---

## How it connects (auth)

The agent is a standalone MCP client (`mcp` Python SDK) that talks to
`https://runtime.dev.emergence.ai/mcp` over streamable HTTP, authenticating via Keycloak OAuth
(`OAuthClientProvider`, static client `em-runtime-mcp`, callback port 9876). The token is cached to
`apps/seller_delivery_agent/.token_cache.json` (gitignored) and reused on later runs; expiry
re-opens the browser automatically. Every request carries the required `X-Project-ID` header.

**The primary OAuth path works** — no bearer-token fallback is implemented in this codebase.

---

## Troubleshooting

- **Port 9876 already in use** (OAuth callback): `lsof -ti:9876 | xargs kill`, then retry. Or change
  `OAUTH_CALLBACK_PORT` in `config.py`.
- **`401 Unauthorized` / corrupted token**: `rm -f apps/seller_delivery_agent/.token_cache.json` and
  re-run — the OAuth flow restarts.
- **Browser didn't open**: copy the URL printed in the terminal and open it manually.
- **`403 Forbidden` / empty results**: your account may not be provisioned for the shared DEV
  project — check with the platform team.
- **Talk2Data errors**: note that `sample_data`/query FQNs are 3-part (`DATABASE.SCHEMA.TABLE`),
  while `generate_sql`'s `schema_fqn` is the 3-part `connection-slug.database.schema` form — both are
  already handled in `config.py`.

---

## Project layout

```
apps/seller_delivery_agent/
  app.py            # Streamlit UI (thin wrapper over agent.run)
  agent.py          # orchestration (drives the LLM loop) + CLI + progress callback
  llm.py            # client factory (Vertex/ADC or API key) + the agentic tool-use loop
  tools.py          # Anthropic tool defs + ToolExecutor (bridges tool calls -> MCP session)
  prompts.py        # system prompt (goal + dataset hint + 4-section output spec)
  craft_client.py   # MCP session + response parsers (backs the tools)
  craft_auth.py     # OAuth (FileTokenStorage + OAuthClientProvider)
  charts.py         # render a Plotly figure spec -> PNG
  config.py         # connection slug, project id, OAuth settings
  tests/            # pytest suite (run: .venv/bin/python -m pytest apps/seller_delivery_agent/tests/ -q)
  runs/             # per-run output (gitignored)
```
