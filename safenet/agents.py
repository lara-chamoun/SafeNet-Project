import os
import json

from langchain_openai import ChatOpenAI

from .models import CyberSafetyState, InvestigationResult, SituationAnalysis
from .tools import extract_domains, match_scam_patterns, recovery_playbook,score_risk


def _snapshot(stage: str, **values: object) -> dict[str, object]:
    return {"stage": stage, **values}


# OpenAI reads the current update together with the incident history kept by this thread.
def situation_analyzer(state: CyberSafetyState) -> dict:
    # ---------------------------------------------------------
    # 1. Check that the OpenAI API key exists
    # ---------------------------------------------------------
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is required for SafeNet live analysis."
        )

    # ---------------------------------------------------------
    # 2. Separate previous conversation from current message
    # ---------------------------------------------------------
    previous_history = list(state.conversation_history)

    current_message = state.user_message.strip()

    # Previous messages only.
    # We do NOT add the current message here.
    incident_context = "\n\n".join(previous_history)

    # Complete history including the current message.
    history = [*previous_history, state.user_message]

    # ---------------------------------------------------------
    # 3. Create the LLM
    # ---------------------------------------------------------
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    llm = ChatOpenAI(
        model=model,
        temperature=0,
    )

    # Structured Output Mode
    structured_llm = llm.with_structured_output(
        SituationAnalysis
    )

    # ---------------------------------------------------------
    # 4. Build the prompt
    # ---------------------------------------------------------
    prompt = f"""
You are SafeNet, a cybersecurity incident assessment assistant.

SafeNet is specifically designed to help users with cybersecurity
and digital-safety situations.

Your task is to analyze the CURRENT USER MESSAGE and determine
whether it is related to cybersecurity.

============================================================
SCOPE
============================================================

IN-SCOPE examples:

- suspicious emails, messages, links, or websites
- phishing or scams
- passwords or credentials being exposed
- OTP or verification-code exposure
- suspicious downloads or files
- malware or suspected malware
- unauthorized account access or login
- compromised accounts
- suspicious activity on a computer or phone
- Windows Security / Microsoft Defender and other security tools
- account/device security
- privacy or security incidents

OUT-OF-SCOPE examples:

- greetings such as "hello", "hi", or "good morning"
- weather
- general homework unrelated to cybersecurity
- entertainment
- general programming questions unrelated to cybersecurity
- cooking
- travel
- shopping
- other unrelated everyday questions

============================================================
IMPORTANT SCOPE CLASSIFICATION RULE
============================================================

You MUST primarily classify the CURRENT USER MESSAGE.

Previous conversation context may be used ONLY to understand
a current message that clearly refers to the previous cybersecurity
incident.

Do NOT automatically inherit the cybersecurity classification
from previous messages.

A standalone greeting or unrelated message remains OUT-OF-SCOPE,
even if the previous conversation was about cybersecurity.

Examples:

Example 1:

Previous context:
"I clicked a suspicious link."

Current user message:
"Should I change my password?"

Result:
IN-SCOPE

Reason:
The current message clearly refers to the previous cybersecurity
incident.

------------------------------------------------------------

Example 2:

Previous context:
"I clicked a suspicious link."

Current user message:
"hello"

Result:
OUT-OF-SCOPE

Reason:
The current message is only a greeting and does not refer to
the cybersecurity incident.

------------------------------------------------------------

Example 3:

Previous context:
"I clicked a suspicious link."

Current user message:
"I also entered my OTP."

Result:
IN-SCOPE

Reason:
The current message clearly provides new information about
the cybersecurity incident.

------------------------------------------------------------

Example 4:

Previous context:
"I clicked a suspicious link."

Current user message:
"What is the weather today?"

Result:
OUT-OF-SCOPE

Reason:
The current message is unrelated to cybersecurity.

============================================================
OUT-OF-SCOPE BEHAVIOR
============================================================

For an OUT-OF-SCOPE message:

- Set is_security_related to false.
- Do not invent a cybersecurity incident.
- Do not assign cybersecurity risk based on an unrelated message.
- Do not inherit risk from previous messages.
- Keep situation_type empty when appropriate.
- Keep suspicious_elements empty when appropriate.
- Keep incident indicators false unless the current message
  clearly provides them.

============================================================
IN-SCOPE BEHAVIOR
============================================================

For an IN-SCOPE message:

- Set is_security_related to true.
- Analyze the actual current message.
- Use previous conversation context when it helps understand
  the current message.
- Treat the conversation as an ongoing incident when the current
  message clearly continues or updates that incident.
- New information can increase OR decrease risk.
- Do not invent facts.
- Do not treat previous statements as new events.
- Only mark an event as occurring now if it is supported by
  the current message or clearly established previous context.

============================================================
PREVIOUS CONVERSATION CONTEXT
============================================================

{incident_context if incident_context else "(No previous conversation.)"}

============================================================
CURRENT USER MESSAGE
============================================================

{current_message}

============================================================
FINAL INSTRUCTION
============================================================

Determine the structured SituationAnalysis for the CURRENT USER
MESSAGE while using previous context only when necessary to
interpret a clear follow-up to an existing incident.
"""

    # ---------------------------------------------------------
    # 5. Run Structured Output Mode
    # ---------------------------------------------------------
    analysis = structured_llm.invoke(prompt)

    # ---------------------------------------------------------
    # 6. Debug information
    # ---------------------------------------------------------
    print("========== SAFENET DEBUG ==========")
    print("PREVIOUS HISTORY:")
    print(previous_history)

    print("CURRENT USER MESSAGE:")
    print(state.user_message)

    print("SECURITY RELATED:")
    print(analysis.is_security_related)

    print("SITUATION TYPE:")
    print(analysis.situation_type)

    print("ANALYSIS:")
    print(analysis)

    print("===================================")

    # ---------------------------------------------------------
    # 7. Create snapshot
    # ---------------------------------------------------------
    snap = _snapshot(
        "analyzed",
        type=analysis.situation_type,
        indicators=analysis.suspicious_elements,
    )

    # ---------------------------------------------------------
    # 8. Return updated LangGraph state
    # ---------------------------------------------------------
    return {
        # Complete conversation including current message
        "conversation_history": history,

        # Previous context only
        "incident_context": incident_context,

        # Structured analysis
        "analysis": analysis.model_dump(),

        # Scope classification
        "is_security_related": analysis.is_security_related,

        # Situation information
        "situation_type": analysis.situation_type,
        "suspicious_elements": analysis.suspicious_elements,

        # Security indicators
        "contains_link": analysis.contains_link,
        "clicked_link": analysis.clicked_link,
        "shared_password": analysis.shared_password,
        "shared_otp": analysis.shared_otp,
        "downloaded_file": analysis.downloaded_file,
        "unknown_login": analysis.unknown_login,

        # Execution metadata
        "current_stage": "analyzed",

        "agents_completed": [
            *state.agents_completed,
            "situation_analyzer",
        ],

        "snapshots": [
            *state.snapshots,
            snap,
        ],

        "iteration": state.iteration + 1,
    }
def scope_response(state: CyberSafetyState) -> dict:
    print("========== SCOPE RESPONSE ==========")
    print("is_security_related:", state.is_security_related)

    result = {
        "final_report": (
            "Sorry, SafeNet is focused on cybersecurity and "
            "digital-safety concerns. Please describe a suspicious "
            "message, link, website, account activity, file, login, "
            "device-security issue, or other security concern."
        ),
        "current_stage": "complete",
        "agents_completed": [
            *state.agents_completed,
            "scope_response",
        ],
        "iteration": state.iteration + 1,
    }

    print("FINAL REPORT:", result["final_report"])

    return result

#  the investigation agent analyzes the complete incident state already built by the thread.
#  inspect the incident context for URLs and known scam indicators.
def threat_investigator(state: CyberSafetyState) -> dict:
    text = state.incident_context or state.user_message
    domains = extract_domains(text)
    patterns = match_scam_patterns(text)
    scores = {name: 1 for name in patterns}
    notes = ["URLs were parsed locally and were not opened."] if domains else ["No explicit URL was supplied."]
    result = InvestigationResult(
        parsed_domains=domains, pattern_matches=patterns, indicator_scores=scores, notes=notes
    )
    snap = _snapshot("investigated", domains=domains, patterns=patterns)
    return {
        "investigation": result.model_dump(),
        "parsed_domains": domains,
        "current_stage": "investigated",
        "agents_completed": [*state.agents_completed, "threat_investigator"],
        "snapshots": [*state.snapshots, snap],
        "iteration": state.iteration + 1,
    }


# convert the investigation into a risk score and risk level.
def risk_assessor(state: CyberSafetyState) -> dict:
    assert state.analysis is not None and state.investigation is not None
    analysis = SituationAnalysis.model_validate(state.analysis)
    investigation = InvestigationResult.model_validate(state.investigation)
    score, reasons = score_risk(analysis, investigation.pattern_matches, investigation.parsed_domains)
    if score >= 0.85:
        level = "critical"
    elif score >= 0.60:
        level = "high"
    elif score >= 0.30:
        level = "medium"
    else:
        level = "low"
    urgent = level in {"high", "critical"}
    snap = _snapshot("assessed", score=score, level=level, immediate_action=urgent)
    return {
        "risk_score": score,
        "risk_level": level,
        "risk_reasons": reasons,
        "immediate_action_needed": urgent,
        "current_stage": "assessed",
        "agents_completed": [*state.agents_completed, "risk_assessor"],
        "snapshots": [*state.snapshots, snap],
        "iteration": state.iteration + 1,
    }


# OpenAI reads the current incident, risk assessment, conversation,
# and latest user message, then generates contextual security advice.
def advice_agent(state: CyberSafetyState) -> dict:
    actions = generate_security_advice(state)

    return {
        "route_taken": "advice",
        "recommended_actions": actions,
        "current_stage": "advice_created",
        "agents_completed": [
            *state.agents_completed,
            "advice_agent"
        ],
        "snapshots": [
            *state.snapshots,
            _snapshot("advice_created", action_count=len(actions))
        ],
        "iteration": state.iteration + 1,
    }



#  use OpenAI to generate contextual security advice from the
# current thread state, current analysis, risk, and latest user message.
def generate_security_advice(state: CyberSafetyState) -> list[str]:

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0,
    )

    # LangGraph checkpointing may restore Pydantic objects as dictionaries.
    # Support both formats so the same thread can continue safely.
    if state.analysis is None:
        current_analysis = {}
    elif isinstance(state.analysis, dict):
        current_analysis = state.analysis
    else:
        current_analysis = state.analysis.model_dump()

    prompt = f"""
You are SafeNet, a cybersecurity safety assistant.

Your job is to give practical, specific, and logically appropriate
security guidance based on the user's CURRENT incident and latest question.

IMPORTANT RULES:

1. This is ONE ongoing incident represented by the current LangGraph thread.
2. The current analysis represents the latest understanding of the incident.
3. Previous conversation messages may contain corrections.
4. If the user explicitly corrects previous information, treat the
   correction as the current truth.
5. Answer the user's actual latest question.
6. Do not give generic advice when the user asks a specific question.
7. Give actionable step-by-step instructions when appropriate.
8. Never invent that the user performed an action they did not report.
9. If the user asks about a specific product, operating system,
   account, browser, or security tool, tailor the instructions to it.
10. If you are uncertain about a current UI or product behavior,
    clearly say so rather than inventing a menu or setting.
11. Do not claim that a device or account is completely safe.
12. Do not ask the user to provide passwords, OTPs, API keys,
    recovery codes, or other secrets.
13. Keep advice proportional to the current risk.
14. If the latest message is a general cybersecurity question rather
    than an incident update, answer that question directly.
15. Do not repeat old recommendations if they are no longer relevant.

CURRENT INCIDENT ANALYSIS:
{json.dumps(current_analysis, indent=2)}

CURRENT RISK:
Level: {state.risk_level or "unknown"}
Score: {state.risk_score if state.risk_score is not None else "unknown"}

RISK REASONS:
{json.dumps(state.risk_reasons, indent=2)}

USER'S LATEST MESSAGE:
{state.user_message}

RECENT CONVERSATION:
{json.dumps(state.conversation_history[-10:], indent=2)}

Generate the most useful response to the user's latest message.

Return ONLY a JSON array of concise action strings.

Example:
[
    "Open Windows Security from the Start menu.",
    "Select Virus & threat protection.",
    "Select Quick scan.",
    "Review Protection history for anything suspicious."
]
"""

    response = llm.invoke(prompt)

    try:
        actions = json.loads(response.content)

        if isinstance(actions, list):
            return [
                str(action).strip()
                for action in actions
                if str(action).strip()
            ]

    except (json.JSONDecodeError, TypeError):
        pass

    return [response.content.strip()]

# create recovery actions when the updated incident needs immediate action.
def recovery_agent(state: CyberSafetyState) -> dict:
    assert state.analysis is not None
    actions = recovery_playbook(SituationAnalysis.model_validate(state.analysis))
    return {
        "route_taken": "recovery",
        "recommended_actions": actions,
        "current_stage": "recovery_created",
        "agents_completed": [*state.agents_completed, "recovery_agent"],
        "snapshots": [*state.snapshots, _snapshot("recovery_created", action_count=len(actions))],
        "iteration": state.iteration + 1,
    }


#  turn the final state into the response shown to the user.
def report_agent(state: CyberSafetyState) -> dict:
    level = (state.risk_level or "unknown").upper()
    reasons = "\n".join(f"- {r}" for r in state.risk_reasons) or "- No strong danger signal was found."
    actions = "\n".join(f"{i}. {a}" for i, a in enumerate(state.recommended_actions, 1))
    report = (
        f"SAFENET ASSESSMENT\nRisk: {level} ({state.risk_score:.0%})\n\n"
        f"Why:\n{reasons}\n\nWhat to do now:\n{actions}\n\n"
        "This educational assessment cannot guarantee that something is safe. "
        "Use official support channels for financial, identity, or account emergencies."
    )
    return {
        "final_report": report,
        "current_stage": "complete",
        "agents_completed": [*state.agents_completed, "report_agent"],
        "snapshots": [*state.snapshots, _snapshot("complete", route=state.route_taken)],
        "iteration": state.iteration + 1,
    }
