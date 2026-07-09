# Seller Delivery Intelligence Agent

Point it at an Olist seller and it produces a personalized improvement brief — its
thesis is the causal link between **late delivery and low review scores**. Every
number comes from the seller's own data, pulled **entirely through the CRAFT
(em-runtime) MCP server** — there is no hand-written SQL anywhere in the codebase.

**The agent is LLM-orchestrated.** Claude is given the raw MCP tools and a goal; *it*
decides which questions to ask, when to run each query, when to chart, and when it has
enough to write the brief. There is no hard-coded question list or fixed pipeline — the
tool-call sequence is different every run because the model plans it.

Built for the Emergence hackathon, riffing on the reference
[Customer Experience Intelligence Agent](https://emergenceai.atlassian.net/wiki/spaces/deveng/pages/1736933401/Customer+Experience+Intelligence+Agent)
and the [Nebius DEV Environment MCP Setup Guide](https://emergenceai.atlassian.net/wiki/spaces/Product/pages/1717895195/Nebius+DEV+Environment+MCP+Setup+Guide).

---

## What it does

Given a seller_id, Claude runs an **agentic tool-use loop**. It has four tools, each
backed by our authenticated CRAFT MCP session:

- `generate_sql(question)` — describe an analytical question in words → schema-bound SQL
- `execute_query(sql)` → an artifact handle
- `get_result_page(artifact_fqn)` → the rows
- `generate_plotly_chart(chart_type, data, options)` → a saved PNG

Claude sequences the `generate_sql → execute_query → get_result_page` triplet itself for
each question it decides to investigate (profile, delivery timing, review distribution,
on-time-vs-late comparison, worst segments…), builds at least one chart of the
delivery↔review correlation, then stops calling tools and writes a five-section brief:
**Store Snapshot, Delivery Health, The Rating Impact, Top 3 Fixes, Watch-outs / Risk**.

The system prompt sets the goal and the required output shape (guided-agentic); everything
else — the questions, the order, the depth — is the model's call. The only step that isn't
a tool call is Claude writing the final brief.

---

## Prerequisites

- **Python 3.11+** (developed on 3.13).
- **A DEV Keycloak / SSO account** for `runtime.dev.emergence.ai` — internal `emergence.ai`
  developers use *Sign in with Google*. First run opens a browser for OAuth (once).
- **Claude access.** Two supported auth paths (the code prefers Vertex when its env vars are set):
  - **Vertex AI via Google Cloud ADC** (used in development): `gcloud auth application-default login`,
    then set `ANTHROPIC_VERTEX_PROJECT_ID` and `CLOUD_ML_REGION` (e.g. `global`). No API key needed.
  - **Direct Anthropic API**: set `ANTHROPIC_API_KEY`.

## Setup

```bash
# from the repository root
python3 -m venv .venv
.venv/bin/pip install -r seller_agent/requirements.txt
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
.venv/bin/streamlit run seller_agent/app.py
```

Then in the browser:

1. Click **Check connection** — completes the Keycloak OAuth login on first run and verifies the
   MCP server responds (`hello_world`).
2. Keep the default seller (or pick another / paste a custom `seller_id`).
3. Click **Run analysis** — watch the live progress, then the brief renders on the right, the two
   charts on the left, and the generated SQL in an expander.

### CLI (same pipeline, terminal only)

```bash
.venv/bin/python -m seller_agent.agent [--seller-id <id>]
```

Default seller: `6560211a19b47992c3666cc44a7e94c0` — a verified high-volume seller (1,854 orders)
whose data shows the thesis clearly: **on-time orders average ~4.0★ vs ~2.5★ for late orders.**

Both entrypoints share the exact same `agent.run()` pipeline; the UI is a thin wrapper.

---

## Outputs

Each run writes to `seller_agent/runs/seller_{id_short}_{timestamp}/`:

| File | Description |
| --- | --- |
| `engagement_brief.md` | The personalized seller improvement brief |
| `chart_1.png`, `chart_2.png`, … | The charts the model chose to build |
| `sql_queries.txt` | Every query the model generated (audit trail — none hand-written) |
| `raw_data.json` | The result rows the model collected, tagged by the question that produced them |

The number of charts and queries varies run-to-run — the model decides.

---

## How it connects (auth)

The agent is a standalone MCP client (`mcp` Python SDK) that talks to
`https://runtime.dev.emergence.ai/mcp` over streamable HTTP, authenticating via Keycloak OAuth
(`OAuthClientProvider`, static client `em-runtime-mcp`, callback port 9876). The token is cached to
`seller_agent/.token_cache.json` (gitignored) and reused on later runs; expiry re-opens the browser
automatically. Every request carries the required `X-Project-ID` header.

**The primary OAuth path works** — no bearer-token fallback was needed. (Had auto-discovery failed,
the fallback was to export `EM_RUNTIME_TOKEN` and send it as an `Authorization: Bearer` header.)

---

## Troubleshooting

- **Port 9876 already in use** (OAuth callback): `lsof -ti:9876 | xargs kill`, then retry. Or change
  `OAUTH_CALLBACK_PORT` in `config.py`.
- **`401 Unauthorized` / corrupted token**: `rm -f seller_agent/.token_cache.json` and re-run — the
  OAuth flow restarts.
- **Browser didn't open**: copy the URL printed in the terminal and open it manually.
- **`403 Forbidden` / empty results**: your account may not be provisioned for the shared DEV
  project — check with the platform team.
- **Talk2Data errors**: note that `sample_data`/query FQNs are 3-part (`DATABASE.SCHEMA.TABLE`),
  while `generate_sql`'s `schema_fqn` is the 3-part `connection-slug.database.schema` form — both are
  already handled in `config.py`.

---

## Project layout

```
seller_agent/
  app.py            # Streamlit UI (thin wrapper over agent.run)
  agent.py          # orchestration (drives the LLM loop) + CLI + progress callback
  llm.py            # client factory (Vertex/ADC or API key) + the agentic tool-use loop
  tools.py          # Anthropic tool defs + ToolExecutor (bridges tool calls -> MCP session)
  prompts.py        # system prompt (goal + schema hint + 5-section output spec)
  craft_client.py   # MCP session + response parsers (backs the tools)
  craft_auth.py     # OAuth (FileTokenStorage + OAuthClientProvider)
  charts.py         # render a Plotly figure spec -> PNG
  config.py         # connection slug, project id, OAuth settings, default seller
  tests/            # pytest suite (run: .venv/bin/python -m pytest seller_agent/tests/ -q)
  runs/             # per-run output (gitignored)
```
