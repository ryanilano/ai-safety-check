"""LangGraph nodes — Customer Experience Intelligence Agent.

Each node receives the full CustomerExperienceAgentState and returns a PARTIAL dict
(LangGraph merges updates into the shared state automatically).

Node 1  discover_profile        — get_schema + generate_sql + execute_query
Node 2  analyze_behavior        — generate_sql + execute_query  (×3 queries)
Node 3  generate_recommendations— generate_sql + execute_query  (×2 queries)
Node 4  visualize               — generate_plotly_chart          (×2 charts)
Node 5  compose_engagement      — Gemini LLM synthesis           (no CRAFT tools)

Database: TheLook E-Commerce (STG BigQuery — eval-thelook-ecommerce)
Tables:   USERS · EVENTS · ORDERS · ORDER_ITEMS · PRODUCTS · INVENTORY_ITEMS
          · DISTRIBUTION_CENTERS
"""
import json
import logging

from google import genai
from rich.console import Console

from config import GEMINI_API_KEY, GEMINI_SYNTHESIS_MODEL, SCHEMA_FQN
from craft_client import CraftClient
from state import CustomerExperienceAgentState

log = logging.getLogger(__name__)
console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper
# ─────────────────────────────────────────────────────────────────────────────

async def _run_nl_query(
    craft: CraftClient,
    question: str,
    label: str,
    node_errors: list[str],
    sql_evidence: list[str],
) -> list[dict]:
    """Translate a natural-language question to SQL via CRAFT, then execute it.

    Appends generated SQL to sql_evidence (audit trail) and any failures
    to node_errors (non-fatal). Returns an empty list on failure.
    """
    console.print(f"  [dim]→ {label}[/dim]")

    sql_response = await craft.generate_sql(question=question)

    if not sql_response or not sql_response.get("ok"):
        node_errors.append(f"generate_sql failed [{label}]: {str(sql_response)[:80]}")
        return []

    generated_sql = sql_response.get("generate_sql", {}).get("sql", "").strip()
    if not generated_sql:
        node_errors.append(f"Empty SQL returned [{label}]")
        return []

    sql_evidence.append(generated_sql)
    log.info(f"[{label}] generated SQL:\n{generated_sql}")
    console.print(
        f"     [dim]SQL: {generated_sql[:110]}{'…' if len(generated_sql) > 110 else ''}[/dim]"
    )

    exec_response = await craft.execute_query(sql=generated_sql)
    if not exec_response or not exec_response.get("ok"):
        log.error(f"[{label}] execute_query failed. Response: {exec_response}")
        node_errors.append(f"execute_query failed [{label}]")
        return []

    rows = exec_response.get("rows", [])
    log.info(f"[{label}] {len(rows)} rows returned")
    console.print(f"     [green]✓[/green] {len(rows)} rows returned")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — DISCOVER PROFILE
# Goal: Understand the schema + fetch customer demographics from USERS.
# CRAFT tools: get_schema, generate_sql, execute_query
# ─────────────────────────────────────────────────────────────────────────────

async def discover_profile_node(
    state: CustomerExperienceAgentState,
    craft: CraftClient,
) -> dict:
    customer_id = state["customer_id"]
    console.print(
        f"\n[bold cyan]● Node 1/5 — Discover Profile[/bold cyan]  "
        f"[dim](CRAFT: get_schema + generate_sql + execute_query)[/dim]"
    )

    node_errors: list[str] = list(state.get("errors", []))
    sql_evidence: list[str] = list(state.get("sql_queries", []))
    schema_description = ""
    table_names: list[str] = []
    customer_profile: dict = {}

    # Step 1a — discover the schema tables
    schema_result = await craft.fetch_schema(fqn=SCHEMA_FQN)

    if schema_result and schema_result.get("ok"):
        meta = schema_result.get("metadata", {})
        schema_description = meta.get("description") or meta.get("summary_text", "TheLook e-commerce database")
        children = meta.get("children") or []
        table_names = [child["name"] for child in children if child.get("type") == "table"]
        log.info(f"Schema discovered: {len(table_names)} tables — {table_names}")
        console.print(
            f"  [green]✓[/green] {len(table_names)} tables: "
            f"{', '.join(table_names[:8])}{'…' if len(table_names) > 8 else ''}"
        )
    else:
        error_msg = f"fetch_schema unexpected response: {str(schema_result)[:120]}"
        node_errors.append(error_msg)
        log.error(error_msg)
        console.print(f"  [red]✗[/red] {error_msg}")

    # Step 1b — fetch customer demographics
    profile_rows = await _run_nl_query(
        craft=craft,
        question=(
            f"Get the full profile for user with id {customer_id}. "
            "Return columns: id, first_name, last_name, age, gender, "
            "country, city, traffic_source, created_at."
        ),
        label=f"Customer profile (id={customer_id})",
        node_errors=node_errors,
        sql_evidence=sql_evidence,
    )

    if profile_rows:
        customer_profile = profile_rows[0]
        first = customer_profile.get("first_name", "")
        last  = customer_profile.get("last_name", "")
        console.print(
            f"  [green]✓[/green] Customer: [bold]{first} {last}[/bold] | "
            f"Age {customer_profile.get('age', '?')} | "
            f"{customer_profile.get('gender', '?')} | "
            f"{customer_profile.get('city', '?')}, {customer_profile.get('country', '?')}"
        )
    else:
        node_errors.append(f"No customer found with id={customer_id}")
        console.print(f"  [red]✗[/red] No customer found with id={customer_id}")

    return {
        "schema_summary":   schema_description,
        "tables_available": table_names,
        "customer_profile": customer_profile,
        "sql_queries":      sql_evidence,
        "iteration":        state.get("iteration", 0) + 1,
        "errors":           node_errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 — ANALYZE BEHAVIOR
# Goal: Collect purchase history, category preferences, and event behavior.
# CRAFT tools: generate_sql + execute_query (×3 queries)
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_behavior_node(
    state: CustomerExperienceAgentState,
    craft: CraftClient,
) -> dict:
    customer_id = state["customer_id"]
    console.print(
        f"\n[bold cyan]● Node 2/5 — Analyze Behavior[/bold cyan]  "
        f"[dim](CRAFT: generate_sql + execute_query ×3)[/dim]"
    )

    node_errors: list[str] = list(state.get("errors", []))
    sql_evidence: list[str] = list(state.get("sql_queries", []))

    # Q1 — Recent purchase history (orders + products)
    purchase_history = await _run_nl_query(
        craft=craft,
        question=(
            f"What are the last 15 orders placed by user {customer_id}? "
            "For each order item include: order_id, product name, brand, category, "
            "department, sale_price, status, and the order creation date. "
            "Order by order creation date descending."
        ),
        label="Recent purchase history (orders × products)",
        node_errors=node_errors,
        sql_evidence=sql_evidence,
    )

    # Q2 — Category spend breakdown (preference signal)
    category_preferences = await _run_nl_query(
        craft=craft,
        question=(
            f"For user {customer_id}, what are their top product categories by total spend? "
            "Return columns: category, total_spend, num_items_purchased. "
            "Order by total_spend descending. Limit to top 6."
        ),
        label="Category preferences (spend by category, top 6)",
        node_errors=node_errors,
        sql_evidence=sql_evidence,
    )

    # Q3 — Browsing and interaction events
    behavior_events = await _run_nl_query(
        craft=craft,
        question=(
            f"For user {customer_id}, how many events of each type have they performed? "
            "Return columns: event_type, event_count. "
            "Order by event_count descending."
        ),
        label="Behavioral events (event_type distribution)",
        node_errors=node_errors,
        sql_evidence=sql_evidence,
    )

    return {
        "purchase_history":     purchase_history,
        "category_preferences": category_preferences,
        "behavior_events":      behavior_events,
        "sql_queries":          sql_evidence,
        "errors":               node_errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 3 — GENERATE RECOMMENDATIONS
# Goal: Find products to recommend + high-margin items for targeted offers.
# CRAFT tools: generate_sql + execute_query (×2 queries)
# ─────────────────────────────────────────────────────────────────────────────

async def generate_recommendations_node(
    state: CustomerExperienceAgentState,
    craft: CraftClient,
) -> dict:
    customer_id = state["customer_id"]
    console.print(
        f"\n[bold cyan]● Node 3/5 — Generate Recommendations[/bold cyan]  "
        f"[dim](CRAFT: generate_sql + execute_query ×2)[/dim]"
    )

    node_errors: list[str] = list(state.get("errors", []))
    sql_evidence: list[str] = list(state.get("sql_queries", []))

    # Derive preferred categories from Node 2 results
    category_preferences = state.get("category_preferences", [])
    top_categories = [
        row.get("category") or row.get("CATEGORY", "")
        for row in category_preferences[:3]
        if row.get("category") or row.get("CATEGORY")
    ]
    top_category = top_categories[0] if top_categories else "Outerwear & Coats"
    preferred_categories_sql_list = (
        ", ".join(f"'{c}'" for c in top_categories)
        if top_categories else "'Outerwear & Coats'"
    )

    console.print(
        f"  [dim]Top preferred categories: "
        f"{', '.join(top_categories) if top_categories else 'none detected (using default)'}[/dim]"
    )

    # Q1 — Top products in preferred categories not yet purchased by this customer
    recommended_products = await _run_nl_query(
        craft=craft,
        question=(
            f"What are the top 8 best-selling products in the '{top_category}' category "
            f"that user {customer_id} has never purchased? "
            "Rank by total number of times the product appears in orders across all users. "
            "Return columns: product_name, brand, retail_price, category. "
            "Order by popularity descending."
        ),
        label=f"Recommended products (top '{top_category}' not yet bought)",
        node_errors=node_errors,
        sql_evidence=sql_evidence,
    )

    # Q2 — High-margin products in preferred categories for targeted discount offers
    offer_candidates = await _run_nl_query(
        craft=craft,
        question=(
            f"For product categories {preferred_categories_sql_list}, find the 6 products "
            "with the highest profit margin (retail_price minus cost) "
            "where retail_price is between 20 and 200. "
            "Return columns: product_name, brand, retail_price, cost, category. "
            "Order by margin descending."
        ),
        label="Offer candidates (high-margin products for discount offers)",
        node_errors=node_errors,
        sql_evidence=sql_evidence,
    )

    return {
        "recommended_products": recommended_products,
        "offer_candidates":     offer_candidates,
        "sql_queries":          sql_evidence,
        "errors":               node_errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 4 — VISUALIZE
# Goal: Turn raw data into Plotly chart JSON for rendering or saving.
# CRAFT tools: generate_plotly_chart (×2 charts)
# ─────────────────────────────────────────────────────────────────────────────

async def visualize_node(
    state: CustomerExperienceAgentState,
    craft: CraftClient,
) -> dict:
    customer_profile = state.get("customer_profile", {})
    first_name = customer_profile.get("first_name", f"Customer {state['customer_id']}")
    console.print(
        f"\n[bold cyan]● Node 4/5 — Visualize[/bold cyan]  "
        f"[dim](CRAFT: generate_plotly_chart ×2)[/dim]"
    )

    node_errors: list[str] = list(state.get("errors", []))
    preference_chart: dict = {}
    recommendation_chart: dict = {}

    # Chart 1 — Category spend breakdown (preference profile)
    category_preferences = state.get("category_preferences", [])
    if category_preferences:
        chart_data = [
            {
                "category":    row.get("category") or row.get("CATEGORY", "Unknown"),
                "total_spend": float(row.get("total_spend") or row.get("TOTAL_SPEND") or 0),
            }
            for row in category_preferences
        ]
        result = await craft.generate_plotly_chart(
            data=chart_data,
            chart_type="bar",
            options={
                "title":        f"{first_name}'s Category Spend Profile",
                "x_label":      "Product Category",
                "y_label":      "Total Spend ($)",
                "color_scheme": "viridis",
            },
        )
        if result and result.get("ok"):
            preference_chart = (
                result.get("generate_plotly_chart", {})
                      .get("plotly_json", {})
                      .get("plotly_json", {})
            )
            console.print("  [green]✓[/green] Category preference bar chart generated")
        else:
            error_msg = f"Preference chart generation failed: {str(result)[:80]}"
            node_errors.append(error_msg)
            log.warning(error_msg)
    else:
        console.print("  [yellow]⚠[/yellow]  No category data — skipping preference chart")

    # Chart 2 — Recommended products by price
    recommended_products = state.get("recommended_products", [])
    if recommended_products:
        chart_data = [
            {
                "product": (
                    (row.get("product_name") or row.get("PRODUCT_NAME") or "Unknown")[:30]
                ),
                "retail_price": float(
                    row.get("retail_price") or row.get("RETAIL_PRICE") or 0
                ),
            }
            for row in recommended_products[:8]
        ]
        result = await craft.generate_plotly_chart(
            data=chart_data,
            chart_type="bar",
            options={
                "title":        f"Recommended Products for {first_name}",
                "x_label":      "Product",
                "y_label":      "Retail Price ($)",
                "color_scheme": "plasma",
            },
        )
        if result and result.get("ok"):
            recommendation_chart = (
                result.get("generate_plotly_chart", {})
                      .get("plotly_json", {})
                      .get("plotly_json", {})
            )
            console.print("  [green]✓[/green] Recommendation bar chart generated")
        else:
            error_msg = f"Recommendation chart generation failed: {str(result)[:80]}"
            node_errors.append(error_msg)
            log.warning(error_msg)
    else:
        console.print("  [yellow]⚠[/yellow]  No recommendation data — skipping recommendation chart")

    return {
        "preference_chart":     preference_chart,
        "recommendation_chart": recommendation_chart,
        "errors":               node_errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 5 — COMPOSE ENGAGEMENT
# Goal: Gemini synthesizes all evidence into a personalized engagement brief.
# No CRAFT tools — pure LLM synthesis on top of structured evidence.
# ─────────────────────────────────────────────────────────────────────────────

async def compose_engagement_node(
    state: CustomerExperienceAgentState,
    craft: CraftClient,
) -> dict:
    console.print(
        f"\n[bold cyan]● Node 5/5 — Compose Engagement[/bold cyan]  "
        f"[dim](Gemini synthesis — {GEMINI_SYNTHESIS_MODEL})[/dim]"
    )

    customer_profile     = state.get("customer_profile", {})
    purchase_history     = state.get("purchase_history", [])
    category_preferences = state.get("category_preferences", [])
    behavior_events      = state.get("behavior_events", [])
    recommended_products = state.get("recommended_products", [])
    offer_candidates     = state.get("offer_candidates", [])
    sql_evidence         = state.get("sql_queries", [])

    first_name     = customer_profile.get("first_name", "Valued Customer")
    age            = customer_profile.get("age", "?")
    gender         = customer_profile.get("gender", "?")
    country        = customer_profile.get("country", "?")
    traffic_source = customer_profile.get("traffic_source", "?")

    prompt = f"""You are a personalization engine for a premium e-commerce platform.
Your job is to produce a crisp, actionable customer engagement brief for a store associate or CRM system.

CUSTOMER PROFILE:
- Name: {first_name}
- Age: {age} | Gender: {gender} | Country: {country}
- Acquisition channel: {traffic_source}

PURCHASE HISTORY (last 15 items):
{json.dumps(purchase_history[:15], indent=2)}

CATEGORY PREFERENCES (by spend):
{json.dumps(category_preferences, indent=2)}

BEHAVIORAL EVENTS (event type counts):
{json.dumps(behavior_events, indent=2)}

RECOMMENDED PRODUCTS (top picks not yet purchased):
{json.dumps(recommended_products, indent=2)}

OFFER CANDIDATES (high-margin items for targeted discounts):
{json.dumps(offer_candidates, indent=2)}

SQL EVIDENCE ({len(sql_evidence)} queries executed against TheLook E-Commerce database):
{chr(10).join(f"  Q{i + 1}: {q[:120]}..." for i, q in enumerate(sql_evidence))}

---

Write a personalized customer engagement brief with exactly these sections:

## Customer Snapshot
2–3 sentences. Who is {first_name}? What kind of shopper are they based on spend patterns and behavior?

## Top 3 Product Recommendations
For each: product name, brand, price, and ONE sentence on why it fits this customer.
Format as a numbered list.

## Personalized Offer Strategy
Recommend 2 targeted discount offers from the offer candidates. For each: product, suggested discount %, and the rationale. Keep margin impact in mind.

## Engagement Trigger
Identify the most valuable behavioral signal from the events data (e.g. high cart-add rate, repeat views in a category) and recommend one specific action the store associate or CRM should take in the next 24 hours.

## Conversion Risk
One sentence on the biggest risk that this customer doesn't convert, and one mitigation.

## Data Notes
2 brief caveats about what this analysis can and cannot tell us.

Write for a store associate who will read this in 90 seconds. Be specific — avoid vague language like "high engagement" without numbers."""

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = await gemini_client.aio.models.generate_content(
            model=GEMINI_SYNTHESIS_MODEL,
            contents=prompt,
        )
        engagement_brief = response.text
    except Exception as exc:
        log.error(f"Gemini synthesis failed: {exc}")
        return {"engagement_brief": f"[LLM error — {exc}]", "status": "failed"}

    console.print("  [green]✓[/green] Personalized engagement brief generated")

    return {
        "engagement_brief": engagement_brief,
        "status":           "done",
    }
