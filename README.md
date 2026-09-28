# SafeNet AI – Multi-Agent Cybersecurity Safety Assistant

## 1. Project Overview

SafeNet AI is a multi-agent cybersecurity safety assistant built using **LangGraph**. The system analyzes a user's cybersecurity-related situation, investigates potential threats, assesses risk, and provides either preventive advice or recovery actions depending on the assessed risk.

The system uses a stateful LangGraph workflow where multiple specialized agents collaborate through a shared **Pydantic state**.

### Main objectives

* Analyze cybersecurity-related user messages.
* Determine whether a message is within the scope of SafeNet.
* Investigate suspicious indicators.
* Assess the security risk.
* Route the incident to either an advice or recovery agent.
* Generate a final cybersecurity report.
* Maintain state across the workflow using **MemorySaver**.

---

# 2. System Architecture

The SafeNet workflow consists of the following agents/nodes:

1. **Situation Analyzer**
2. **Scope Response**
3. **Threat Investigator**
4. **Risk Assessor**
5. **Advice Agent**
6. **Recovery Agent**
7. **Report Agent**

The overall flow is:

```text
                         ┌──────────────────────┐
                         │        START         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                     ┌──────────────────────────┐
                     │   Situation Analyzer     │
                     │                          │
                     │ Analyze user situation   │
                     │ Extract security facts  │
                     └────────────┬─────────────┘
                                  │
                         ┌────────▼────────┐
                         │  In Scope for   │
                         │    SafeNet?      │
                         └───────┬──────────┘
                         No      │      Yes
                         │       │
                         ▼       ▼
              ┌────────────────┐  ┌──────────────────────┐
              │ Scope Response │  │ Threat Investigator  │
              └───────┬────────┘  └──────────┬───────────┘
                      │                      │
                      ▼                      ▼
                    END              ┌──────────────────┐
                                     │   Risk Assessor  │
                                     └────────┬─────────┘
                                              │
                                      ┌───────▼────────┐
                                      │  Risk Routing   │
                                      └───────┬─────────┘
                                      Low     │    High
                                       │      │
                                       ▼      ▼
                              ┌────────────┐ ┌──────────────┐
                              │   Advice   │ │   Recovery   │
                              │   Agent    │ │    Agent     │
                              └─────┬──────┘ └──────┬───────┘
                                    │               │
                                    └───────┬───────┘
                                            ▼
                                   ┌─────────────────┐
                                   │   Report Agent  │
                                   └────────┬────────┘
                                            │
                                            ▼
                                           END
```

---

# 3. LangGraph Workflow

The graph is implemented using `StateGraph`:

```python
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

    builder.add_edge(
        "threat_investigator",
        "risk_assessor"
    )

    builder.add_conditional_edges(
        "risk_assessor",
        route_by_risk,
        {
            "advice": "advice_agent",
            "recovery": "recovery_agent",
        },
    )

    builder.add_edge(
        "advice_agent",
        "report_agent"
    )

    builder.add_edge(
        "recovery_agent",
        "report_agent"
    )

    builder.add_edge(
        "report_agent",
        END
    )

    return builder.compile(
        checkpointer=MemorySaver()
    )
```

---

# 4. Agent Responsibilities

## 4.1 Situation Analyzer

The Situation Analyzer is the first agent in the workflow.

### Responsibilities

* Understand the user's message.
* Determine whether the situation is cybersecurity-related.
* Extract important security indicators.
* Identify the type of incident.
* Determine whether the message should continue through the cybersecurity workflow.

The agent uses **Structured Output Mode (SOM)** with a Pydantic schema so that the analysis is returned in a structured and validated format.

---

## 4.2 Scope Response

This node handles messages that are determined to be outside the scope of SafeNet.

The routing function is:

```text
route_by_scope()
```

If the situation is:

```text
out_of_scope
```

the graph follows:

```text
Situation Analyzer
        ↓
Scope Response
        ↓
       END
```

If the situation is:

```text
in_scope
```

the graph continues to:

```text
Threat Investigator
```

---

## 4.3 Threat Investigator

The Threat Investigator examines the cybersecurity situation identified by the Situation Analyzer.

### Responsibilities

* Investigate suspicious indicators.
* Extract domains or URLs when present.
* Identify potential threat patterns.
* Add investigation information to the shared state.

The investigation results are then passed to the Risk Assessor.

---

## 4.4 Risk Assessor

The Risk Assessor evaluates the collected information and determines the severity of the incident.

### Responsibilities

* Analyze the situation and investigation results.
* Calculate a risk score.
* Determine the risk level.
* Identify reasons contributing to the risk.
* Determine whether immediate action is required.

The Risk Assessor is followed by a **conditional edge**.

---

# 5. Conditional Risk Routing

SafeNet uses `route_by_risk()` to determine the next agent.

```text
                    Risk Assessor
                          │
                          ▼
                   ┌──────────────┐
                   │  route_by_   │
                   │     risk     │
                   └──────┬───────┘
                          │
              ┌───────────┴───────────┐
              │                       │
           Advice                  Recovery
              │                       │
              ▼                       ▼
        Advice Agent            Recovery Agent
              │                       │
              └───────────┬───────────┘
                          ▼
                    Report Agent
```

If immediate action is not required:

```text
Risk Assessor → Advice Agent
```

If immediate action is required:

```text
Risk Assessor → Recovery Agent
```

This conditional edge demonstrates dynamic control flow because different incidents can follow different execution paths.

---

# 6. Advice Agent

The Advice Agent handles situations where immediate recovery is not required.

### Responsibilities

* Provide cybersecurity advice.
* Recommend preventive actions.
* Explain what the user should do next.
* Provide practical safety recommendations.

After generating the recommendations, the workflow continues to the Report Agent.

```text
Risk Assessor
      ↓
Advice Agent
      ↓
Report Agent
```

---

# 7. Recovery Agent

The Recovery Agent handles situations where the risk assessment indicates that immediate action is required.

### Responsibilities

* Provide recovery steps.
* Recommend containment actions.
* Provide remediation guidance.
* Explain what the user should do immediately.

The workflow then continues to the Report Agent.

```text
Risk Assessor
      ↓
Recovery Agent
      ↓
Report Agent
```

---

# 8. Report Agent

The Report Agent is the final agent in the main cybersecurity workflow.

It combines the information accumulated in the shared state and produces the final user-facing assessment.

The final report can include:

* Identified situation
* Threat indicators
* Risk level
* Risk reasons
* Recommended actions
* Recovery recommendations when required

The final workflow is:

```text
Report Agent
     ↓
    END
```

---

# 9. State Management

SafeNet uses a Pydantic model called:

```python
CyberSafetyState
```

The state is shared between the different LangGraph nodes.

The state contains information such as:

* User message
* Conversation history
* Incident context
* Situation analysis
* Suspicious elements
* Investigation results
* Parsed domains
* Risk score
* Risk level
* Risk reasons
* Immediate-action flag
* Recommended actions
* Final report
* Current execution stage
* Completed agents
* State snapshots
* Iteration count

Using a shared state allows each agent to build on the information produced by previous agents.

---

# 10. Memory and Checkpointing

SafeNet uses LangGraph's `MemorySaver` checkpointer:

```python
return builder.compile(
    checkpointer=MemorySaver()
)
```

`MemorySaver` allows the graph to maintain state separately for different conversation threads while the application is running.

A `thread_id` is used when executing the graph so that messages belonging to the same incident can continue using the same state.

This allows SafeNet to support stateful conversations rather than treating every message as a completely independent interaction.

---

# 11. Structured Output Mode

The Situation Analyzer uses Structured Output Mode with a Pydantic schema.

Example:

```python
structured_llm = llm.with_structured_output(
    SituationAnalysis
)
```

The LLM output is therefore parsed into the `SituationAnalysis` Pydantic model.

This provides structured information such as:

* Situation type
* Whether a link is present
* Whether a link was clicked
* Whether a password was shared
* Whether an OTP was shared
* Whether a file was downloaded
* Whether an unknown login occurred
* Suspicious elements
* Whether the situation is security-related

---

# 12. Tools

Different agents use different tools according to their responsibilities.

Examples include:

| Agent               | Tool / Capability                                 | Purpose                                 |
| ------------------- | ------------------------------------------------- | --------------------------------------- |
| Situation Analyzer  | Structured LLM output                             | Extract structured security information |
| Threat Investigator | URL/domain extraction and threat-pattern analysis | Investigate suspicious indicators       |
| Risk Assessor       | `score_risk`                                      | Calculate the risk score                |
| Recovery Agent      | `recovery_playbook`                               | Provide deterministic recovery actions  |
| Advice Agent        | LLM-based guidance                                | Generate contextual recommendations     |

The agents therefore do not all use the same toolset.

---

# 13. Project Structure

The repository is organized around the LangGraph workflow.

Example structure:

```text
SafeNet/
│
├── safenet/
│   ├── __init__.py
│   ├── graph.py
│   ├── models.py
│   ├── nodes.py
│   ├── tools.py
│   └── web.py
│
├── tests/
│   └── ...
│
├── .env
├── .gitignore
├── requirements.txt
├── README.md
└── ...
```

> Update the filenames above if your repository uses different filenames.

---

# 14. Installation

## Step 1 – Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SafeNet
```

## Step 2 – Create a virtual environment

Windows:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

Mac/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Step 3 – Install dependencies

```bash
pip install -r requirements.txt
```

---

# 15. Environment Variables

Create a `.env` file in the project root.

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

The API key should never be committed to GitHub.

Make sure `.env` is included in `.gitignore`:

```text
.env
.venv/
__pycache__/
*.pyc
```

---

# 16. Running the Application

After activating the virtual environment and configuring the environment variables, run the SafeNet application using the project's main entry point.

For example:

```bash
python -m safenet
```

If the project uses the web interface:

```bash
uvicorn safenet.web:app --reload
```

Then open the local address shown by Uvicorn in the terminal.

> Replace the command with the exact command used by your final repository.

---

# 17. Example Workflow

### Example 1 – Low-risk situation

```text
User
 ↓
Situation Analyzer
 ↓
In Scope
 ↓
Threat Investigator
 ↓
Risk Assessor
 ↓
Advice Agent
 ↓
Report Agent
 ↓
END
```

### Example 2 – High-risk situation

```text
User
 ↓
Situation Analyzer
 ↓
In Scope
 ↓
Threat Investigator
 ↓
Risk Assessor
 ↓
Recovery Agent
 ↓
Report Agent
 ↓
END
```

### Example 3 – Out-of-scope message

```text
User
 ↓
Situation Analyzer
 ↓
Out of Scope
 ↓
Scope Response
 ↓
END
```

These examples demonstrate the conditional control flow of the LangGraph system.

---
