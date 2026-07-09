"""
LangGraph state machine — Customer Experience Intelligence Agent.

                    ┌───────────────────┐
              ┌────►│ DISCOVER PROFILE  │  Node 1: get_schema + generate_sql + execute_query
              │     └────────┬──────────┘
              │              │ always
              │              ▼
              │     ┌────────────────────┐
              │     │ ANALYZE BEHAVIOR   │  Node 2: generate_sql + execute_query (×3)
              │     └────────┬───────────┘
              │              │
              │    ┌─────────▼──────────────────────────┐
              │    │  has_behavioral_data?              │
              └────│  no + retries left ────────────────┘  backtrack to profile
                   │  no + retries exhausted ──────────────► END (partial state)
                   │  yes ──────────────────────────────────────────────────────►
                   └──────────────────────────────────────────────────────────────
                                                                                 │
                                                               ┌─────────────────▼──────────────┐
                                                               │ GENERATE RECOMMENDATIONS       │ Node 3
                                                               └─────────────────┬──────────────┘
                                                                                 │ always
                                                               ┌─────────────────▼──────────────┐
                                                               │ VISUALIZE                      │ Node 4
                                                               └─────────────────┬──────────────┘
                                                                                 │ always
                                                               ┌─────────────────▼──────────────┐
                                                               │ COMPOSE ENGAGEMENT             │ Node 5
                                                               └─────────────────┬──────────────┘
                                                                                 │
                                                                                END
"""
from functools import partial

from langgraph.graph import END, StateGraph

from config import AGENT_MAX_RETRIES
from craft_client import CraftClient
from nodes import (
    analyze_behavior_node,
    compose_engagement_node,
    discover_profile_node,
    generate_recommendations_node,
    visualize_node,
)
from state import CustomerExperienceAgentState


def _route_after_analyze(state: CustomerExperienceAgentState) -> str:
    """Conditional edge: decide what comes after analyze_behavior.

    Routes to recommendations if any behavioral data was collected.
    Backtracks to profile discovery if no data and retries remain.
    Terminates gracefully if retries are exhausted.
    """
    has_behavioral_data = bool(
        state.get("purchase_history")
        or state.get("category_preferences")
        or state.get("behavior_events")
    )
    if has_behavioral_data:
        return "generate_recommendations"
    if state.get("iteration", 0) < AGENT_MAX_RETRIES:
        return "discover_profile"  # backtrack — retry schema + profile discovery
    return END


def _route_after_profile(state: CustomerExperienceAgentState) -> str:
    """Conditional edge: proceed only if customer was found."""
    if state.get("customer_profile"):
        return "analyze_behavior"
    return END


def build_graph(craft: CraftClient):
    """Compile the LangGraph StateGraph.

    The CraftClient is bound into each node via functools.partial so nodes
    remain pure functions (state in → partial state out).
    """
    _discover_profile = partial(discover_profile_node, craft=craft)
    _analyze_behavior = partial(analyze_behavior_node, craft=craft)
    _generate_recommendations = partial(generate_recommendations_node, craft=craft)
    _visualize = partial(visualize_node, craft=craft)
    _compose_engagement = partial(compose_engagement_node, craft=craft)

    graph = StateGraph(CustomerExperienceAgentState)

    graph.add_node("discover_profile", _discover_profile)
    graph.add_node("analyze_behavior", _analyze_behavior)
    graph.add_node("generate_recommendations", _generate_recommendations)
    graph.add_node("visualize", _visualize)
    graph.add_node("compose_engagement", _compose_engagement)

    graph.set_entry_point("discover_profile")

    graph.add_conditional_edges(
        "discover_profile",
        _route_after_profile,
        {
            "analyze_behavior": "analyze_behavior",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "analyze_behavior",
        _route_after_analyze,
        {
            "generate_recommendations": "generate_recommendations",
            "discover_profile": "discover_profile",
            END: END,
        },
    )

    graph.add_edge("generate_recommendations", "visualize")
    graph.add_edge("visualize", "compose_engagement")
    graph.add_edge("compose_engagement", END)

    return graph.compile()
