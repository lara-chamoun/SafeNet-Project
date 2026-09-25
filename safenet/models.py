from typing import Literal

from pydantic import BaseModel, Field


class SituationAnalysis(BaseModel):
    """Validated Structured Output Mode result produced by the analyzer."""

    situation_type: Literal[
        "phishing", "account_access", "malware", "impersonation", "scareware", "other"
    ]
    requested_action: str | None = None
    contains_link: bool = False
    clicked_link: bool = False
    shared_password: bool = False
    shared_otp: bool = False
    downloaded_file: bool = False
    unknown_login: bool = False
    urgency_language: bool = False
    suspicious_elements: list[str] = Field(default_factory=list)
    is_security_related: bool


class InvestigationResult(BaseModel):
    parsed_domains: list[str] = Field(default_factory=list)
    pattern_matches: list[str] = Field(default_factory=list)
    indicator_scores: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class CyberSafetyState(BaseModel):
    # Flow: one LangGraph thread represents one ongoing security incident.
    user_message: str
    use_live_llm: bool = True
    conversation_history: list[str] = Field(default_factory=list)
    incident_context: str = ""

    # Analyzer output
    analysis: dict[str, object] | None = None
    situation_type: str | None = None
    suspicious_elements: list[str] = Field(default_factory=list)
    contains_link: bool = False
    clicked_link: bool = False
    shared_password: bool = False
    shared_otp: bool = False
    downloaded_file: bool = False
    unknown_login: bool = False

    # Investigation output
    investigation: dict[str, object] | None = None
    parsed_domains: list[str] = Field(default_factory=list)

    # Risk output
    risk_score: float = 0.0
    risk_level: Literal["low", "medium", "high", "critical"] | None = None
    risk_reasons: list[str] = Field(default_factory=list)
    immediate_action_needed: bool = False

    # Guidance and report
    route_taken: Literal["advice", "recovery"] | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    final_report: str | None = None

    # Execution tracking
    current_stage: str = "initial"
    agents_completed: list[str] = Field(default_factory=list)
    snapshots: list[dict[str, object]] = Field(default_factory=list)
    iteration: int = 0
    is_security_related: bool = True
