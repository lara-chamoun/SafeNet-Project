# Report outline (maximum 6 pages)

## 1. System overview

SafeNet AI helps non-technical users describe suspicious digital situations in natural language and receive plain-language, exposure-aware actions. Multiple agents are appropriate because extraction, indicator investigation, transparent scoring, route selection, and communication require different responsibilities and toolsets.

## 2. Architecture

Include the graph shown in the README. Explain that the Risk Assessor selects one of two paths: preventive advice or urgent recovery.

## 3. State specification

Show `CyberSafetyState` from `models.py`. Explain its optional nested models, booleans, lists, dictionary, float risk score, integer iteration, route, snapshots, and final report.

## 4. Node-by-node reads and writes

| Node | Reads | Partial writes |
|---|---|---|
| Situation Analyzer | `user_message`, `use_live_llm` | `analysis`, exposure booleans, indicators, stage, history |
| Threat Investigator | `user_message` | domains, pattern evidence, investigation object, stage, history |
| Risk Assessor | `analysis`, `investigation` | score, level, reasons, action flag, stage, history |
| Advice Agent | risk level | preventive steps, route, stage, history |
| Recovery Agent | analysis/exposure | recovery steps, route, stage, history |
| Report Agent | score, level, reasons, actions | final plain-language report, completion stage |

## 5. Structured Output Mode

Show `SituationAnalysis` and the `ChatOpenAI(...).with_structured_output(SituationAnalysis)` call. Explain that Pydantic validates the LLM's extracted facts before they enter shared state.

## 6. Conditional edge

Show `route_by_risk`. If `immediate_action_needed` is false, route to Advice Agent; otherwise route to Recovery Agent. Both routes converge at Report Agent.

## 7. Representative scenarios

Run the three included demos and present their risk level, route, and whether advice was appropriate. Define working behavior as accurate extraction of explicit exposure, deterministic routing, complete actions, and readable output.

## 8. Limitations and future work

The prototype does not visit links or scan files. The deterministic scoring is explainable but simplified. Future work could add safe reputation APIs, multilingual support, calibrated evaluation data, and a human escalation option.

