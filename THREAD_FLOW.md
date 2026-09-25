# SafeNet Thread-Based Conversation Flow

**UI:** creates one conversation ID for each incident.

**Web layer:** uses that conversation ID directly as the LangGraph `thread_id`; it sends only the newest user message.

**LangGraph thread:** keeps the accumulated incident state, including `conversation_history` and `incident_context`.

**OpenAI:** receives the thread's full incident context plus the newest update and reassesses the same incident.

**Agents:** investigate, calculate risk, choose advice/recovery, and generate the final report from the updated thread state.

**SQLite:** stores conversation history for the UI (titles, messages, timestamps, and displayed assessments). It is not used to rebuild the AI context.

So there is one source of truth for AI continuity: **the LangGraph thread**.
