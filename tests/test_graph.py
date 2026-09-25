from safenet.graph import build_graph, route_by_risk
from safenet.models import CyberSafetyState


def invoke(message: str, thread_id: str) -> CyberSafetyState:
    graph = build_graph()
    result = graph.invoke(
        CyberSafetyState(user_message=message),
        config={"configurable": {"thread_id": thread_id}},
    )
    return CyberSafetyState.model_validate(result)


def test_low_risk_uses_advice_route():
    state = invoke("I requested a password reset and used the official app. I did not click anything.", "low-test")
    assert state.route_taken == "advice"
    assert "advice_agent" in state.agents_completed
    assert "recovery_agent" not in state.agents_completed
    assert state.final_report


def test_high_risk_uses_recovery_route():
    state = invoke(
        "I clicked the link, entered my password and verification code, and saw a login I don't recognize.",
        "high-test",
    )
    assert state.route_taken == "recovery"
    assert state.risk_level in {"high", "critical"}
    assert "recovery_agent" in state.agents_completed
    assert any("Change the affected password" in action for action in state.recommended_actions)


def test_router_is_deterministic():
    assert route_by_risk(CyberSafetyState(user_message="x", immediate_action_needed=False)) == "advice"
    assert route_by_risk(CyberSafetyState(user_message="x", immediate_action_needed=True)) == "recovery"

