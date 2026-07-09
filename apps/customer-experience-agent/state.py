from typing import TypedDict


class CustomerExperienceAgentState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    customer_id: int                       # e.g. 12345

    # ── Node 1 · Discover Profile ─────────────────────────────────────────────
    schema_summary: str                    # DB description from CRAFT catalog
    tables_available: list[str]            # All table names in THELOOK_ECOMMERCE schema
    customer_profile: dict                 # name, age, gender, country, city, traffic_source

    # ── Node 2 · Analyze Behavior ─────────────────────────────────────────────
    purchase_history: list[dict]           # recent orders × product details
    category_preferences: list[dict]      # top categories by total spend
    behavior_events: list[dict]           # event_type counts from EVENTS table
    sql_queries: list[str]                # audit trail of every SQL generated

    # ── Node 3 · Generate Recommendations ────────────────────────────────────
    recommended_products: list[dict]       # top products in preferred categories not yet bought
    offer_candidates: list[dict]           # high-margin products for targeted discount offers

    # ── Node 4 · Visualize ────────────────────────────────────────────────────
    preference_chart: dict                 # Plotly bar chart: spend by category
    recommendation_chart: dict             # Plotly bar chart: recommended products × price

    # ── Node 5 · Compose Engagement ───────────────────────────────────────────
    engagement_brief: str                  # Gemini-generated personalized engagement report

    # ── Control ───────────────────────────────────────────────────────────────
    iteration: int                         # retry counter (guarded by AGENT_MAX_RETRIES)
    errors: list[str]                      # non-fatal warnings logged throughout
    status: str                            # "running" | "done" | "failed"
