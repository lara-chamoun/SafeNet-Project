from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents import (
    advice_agent,
    recovery_agent,
    report_agent,
    risk_assessor,
    situation_analyzer,
    threat_investigator,
    scope_response
)
from .models import CyberSafetyState


# Flow: after risk assessment, choose recovery help for urgent cases or normal advice otherwise.
def route_by_risk(state: CyberSafetyState) -> str:
    """Meaningful conditional edge: exposed/high-risk users receive recovery help."""
    return "recovery" if state.immediate_action_needed else "advice"


def route_by_scope(state: CyberSafetyState) -> str:
    print("========== SCOPE ROUTER ==========")
    print("is_security_related:", state.is_security_related)

    if not state.is_security_related:
        print("ROUTING TO: scope_response")
        return "out_of_scope"

    print("ROUTING TO: threat_investigator")
    return "in_scope"


# Flow: build the fixed multi-agent pipeline and persist its state by thread_id.
def build_graph():
    builder = StateGraph(CyberSafetyState)
    builder.add_node("situation_analyzer", situation_analyzer)
    builder.add_node("scope_response", scope_response)
    builder.add_node("threat_investigator", threat_investigator)
    builder.add_node("risk_assessor", risk_assessor)
    builder.add_node("advice_agent", advice_agent)
    builder.add_node("recovery_agent", recovery_agent)
    builder.add_node("report_agent", report_agent)

    builder.add_edge(START, "situation_analyzer")
    builder.add_conditional_edges(
        "situation_analyzer",
        route_by_scope,
        {
            "out_of_scope": "scope_response",
            "in_scope": "threat_investigator",
        },
    )
    builder.add_edge("scope_response", END)
    builder.add_edge("threat_investigator", "risk_assessor")
    builder.add_conditional_edges(
        "risk_assessor",
        route_by_risk,
        {"advice": "advice_agent", "recovery": "recovery_agent"},
    )
    builder.add_edge("advice_agent", "report_agent")
    builder.add_edge("recovery_agent", "report_agent")
    builder.add_edge("report_agent", END)

    # MemorySaver keeps each thread's state separate while the server is running.
    return builder.compile(checkpointer=MemorySaver())

