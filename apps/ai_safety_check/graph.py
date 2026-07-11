"""Wires the pipeline nodes into a compiled LangGraph."""
import functools

from langgraph.graph import StateGraph, END

from . import nodes
from .state import SafetyCheckState


def build_graph(craft, llm, tavily):
    g = StateGraph(SafetyCheckState)
    g.add_node("discover", functools.partial(nodes.discover_candidates_node, craft=craft))
    g.add_node("classify", functools.partial(nodes.classify_node, llm=llm))
    g.add_node("gate", functools.partial(nodes.gate_node, craft=craft))
    g.add_node("hindsight", functools.partial(nodes.hindsight_node, tavily=tavily, llm=llm))
    g.add_node("dangers", functools.partial(nodes.dangers_node, llm=llm))
    g.set_entry_point("discover")
    g.add_edge("discover", "classify")
    g.add_edge("classify", "gate")
    g.add_edge("gate", "hindsight")
    g.add_edge("hindsight", "dangers")
    g.add_edge("dangers", END)
    return g.compile()
