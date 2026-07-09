# Customer Experience Intelligence Agent

A personalization engine for e-commerce that turns raw transactional data into actionable customer engagement briefs — without writing a single line of SQL.

The agent ingests a customer ID, autonomously discovers the TheLook E-Commerce schema via the CRAFT semantic platform, executes natural-language queries across purchase history, behavioral events, and product catalog, then feeds all evidence to Gemini to produce a personalized engagement report with targeted product recommendations and discount offers.

## Usage

```bash
python main.py 12345          # run for customer 12345
python main.py 99001          # any integer customer ID
python main.py                # defaults to customer 12345
```

Or via Makefile:
```bash
make run CUSTOMER_ID=12345
```

Each run writes all artifacts to `runs/customer_{id}_{timestamp}/`.

---

## Architecture

```
 User
  │
  │  python main.py 12345
  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          LangGraph Graph                               │
│                                                                        │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │  Node 1          │──►│  Node 2          │──►│  Node 3          │   │
│  │  DISCOVER        │   │  ANALYZE         │   │  RECOMMEND       │   │
│  │  PROFILE         │   │  BEHAVIOR        │   │  PRODUCTS        │   │
│  └──────────────────┘   └──────────────────┘   └────────┬─────────┘   │
│          ▲                     │ no data +               │             │
│          └─────────────────────┘ retries left            ▼             │
│                                                 ┌──────────────────┐   │
│                                                 │  Node 4          │   │
│                                                 │  VISUALIZE       │   │
│                                                 └────────┬─────────┘   │
│                                                          │             │
│                                                 ┌────────▼─────────┐   │
│                                                 │  Node 5          │   │
│                                                 │  COMPOSE         │   │
│                                                 │  ENGAGEMENT      │   │
│                                                 └────────┬─────────┘   │
└──────────────────────────────────────────────────────────┼─────────────┘
                                                           │
                                                          END
                                                   engagement_brief.md
```

---

## MCP Tool Calls per Node

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Node 1 · DISCOVER PROFILE                                              │
│                                                                         │
│  craft.fetch_schema()                                                   │
│  └─► MCP: get_schema ──► TheLook catalog                               │
│       Returns: 7 table names + schema description                       │
│                                                                         │
│  craft.generate_sql(customer profile question)                          │
│  └─► MCP: generate_sql ──► Talk2Data                                   │
│  craft.execute_query(sql)                                               │
│  └─► MCP: execute_query + get_result_page ──► BigQuery                 │
│       Returns: 1 customer row (demographics)                            │
└─────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Node 2 · ANALYZE BEHAVIOR  (3 queries)                                 │
│                                                                         │
│  Q1 — Purchase history (ORDERS + ORDER_ITEMS + PRODUCTS join)           │
│  Q2 — Category spend breakdown (GROUP BY category)                      │
│  Q3 — Behavioral events (EVENTS GROUP BY event_type)                   │
│                                                                         │
│  Each query: generate_sql + execute_query + get_result_page             │
│  → 6 MCP tool calls (9 raw calls including get_result_page)             │
└─────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Node 3 · GENERATE RECOMMENDATIONS  (2 queries)                         │
│                                                                         │
│  Q1 — Top products in preferred categories NOT yet purchased            │
│  Q2 — High-margin products in preferred categories (offer targeting)    │
│                                                                         │
│  Each query: generate_sql + execute_query + get_result_page             │
│  → 4 MCP tool calls (6 raw calls including get_result_page)             │
└─────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Node 4 · VISUALIZE                                                     │
│                                                                         │
│  generate_plotly_chart(category_preferences) ──► MCP: generate_plotly  │
│  generate_plotly_chart(recommended_products) ──► MCP: generate_plotly  │
│  → 2 MCP tool calls, returns Plotly figure JSON                         │
└─────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Node 5 · COMPOSE ENGAGEMENT                                            │
│                                                                         │
│  No MCP calls — pure LLM synthesis                                      │
│  Gemini (gemini-2.5-flash) reads all collected evidence and writes:     │
│    - Customer Snapshot                                                  │
│    - Top 3 Product Recommendations (with rationale)                     │
│    - Personalized Offer Strategy (targeted discounts)                   │
│    - Engagement Trigger (next 24h CRM action)                           │
│    - Conversion Risk + Mitigation                                       │
│    - Data Notes (caveats)                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Total MCP tool calls per run: ~15**
(1 schema + 2 profile + 6 behavior + 4 recommendations + 2 charts)

---

## Nodes

| # | Node | CRAFT Tools | Output |
|---|------|-------------|--------|
| 1 | Discover Profile | `get_schema`, `generate_sql`, `execute_query` | Schema + customer demographics |
| 2 | Analyze Behavior | `generate_sql`, `execute_query` ×3 | Purchase history, category prefs, events |
| 3 | Generate Recommendations | `generate_sql`, `execute_query` ×2 | Recommended products, offer candidates |
| 4 | Visualize | `generate_plotly_chart` ×2 | Category spend chart, recommendation chart |
| 5 | Compose Engagement | — (Gemini LLM) | `engagement_brief.md` |

---

## Database

**TheLook E-Commerce** (BigQuery via CRAFT)

| Table | Used In | Purpose |
|-------|---------|---------|
| USERS | Node 1 | Customer demographics, traffic source |
| ORDERS | Node 2 | Order status, timestamps |
| ORDER_ITEMS | Node 2, 3 | Products purchased, sale price |
| PRODUCTS | Node 2, 3 | Category, brand, retail price, cost |
| INVENTORY_ITEMS | Node 3 | Cost for margin calculation |
| EVENTS | Node 2 | Behavioral signals (page views, cart adds) |
| DISTRIBUTION_CENTERS | — | Not used in current version |

---

## State

All nodes read and write a shared `CustomerExperienceAgentState` TypedDict. LangGraph merges partial updates automatically — each node only returns the keys it produced.

---

## Retry Logic

- **Graph level**: if Node 2 returns no data and retries remain, the graph backtracks to Node 1 (up to `AGENT_MAX_RETRIES = 2`).
- **Client level**: `generate_sql` retries up to 2× with exponential backoff (2s, 4s) on `talk2data_unreachable`.
- **Transport level**: tenacity retries on `httpx.TimeoutException` / `ConnectError` (up to 4 attempts, max 8s wait).

---

## Run Artifacts

```
runs/customer_12345_20260625_110000/
  agent.log                  — full DEBUG trace of every MCP call
  sql_queries.txt            — all SQL generated by CRAFT (evidence trail)
  customer_profile.json      — demographics (name, age, gender, country, traffic_source)
  purchase_history.json      — last 15 orders × product details
  category_preferences.json  — top categories by total spend
  behavior_events.json       — event_type distribution
  recommended_products.json  — top 8 products in preferred category not yet bought
  offer_candidates.json      — 6 high-margin products for discount offers
  preference_chart.json      — Plotly bar chart: spend by category
  recommendation_chart.json  — Plotly bar chart: recommended products × price
  engagement_brief.md        — personalized engagement report (Gemini-generated)
```

---

## Setup

```bash
# 1. Copy env template and fill in values
cp .env.template .env

# 2. Install dependencies
uv sync

# 3. Obtain Keycloak refresh token (one-time, opens browser)
uv run python scripts/get_token.py
# → paste KEYCLOAK_REFRESH_TOKEN=... into .env

# 4. Run for a customer
python main.py 12345
```

---

## Decisions

See `docs/decisions/` for Architecture Decision Records covering:
- Why TheLook was chosen over Brazilian E-Commerce ([ADR-001](docs/decisions/001-database-selection.md))
- Why Gemini Flash was chosen for synthesis ([ADR-002](docs/decisions/002-llm-provider-selection.md))
- Why CRAFT `generate_sql` is used over raw SQL ([ADR-003](docs/decisions/003-generate-sql-over-raw-sql.md))
