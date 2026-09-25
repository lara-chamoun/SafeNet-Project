"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  conversations: [], active: null, busy: false, loading: false,
  config: null, failed: null, dialog: null,
};
const mobileLayout = matchMedia("(max-width: 700px)");
const storage = {
  get(key, fallback = "") { try { return localStorage.getItem(`safenet:${key}`) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(`safenet:${key}`, value); } catch { /* Browser storage may be disabled. */ } },
  remove(key) { try { localStorage.removeItem(`safenet:${key}`); } catch { /* Optional preference storage. */ } },
};

// All user and model text is inserted as text, never interpreted as HTML or links.
function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.setAttribute("aria-hidden", "true");
  svg.append(use);
  return svg;
}

function iconButton(name, label, action) {
  const button = element("button", "icon-button");
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.append(icon(name));
  button.addEventListener("click", action);
  return button;
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", "X-SafeNet-Client": "web", ...options.headers },
    });
  } catch {
    throw new Error("Cannot reach SafeNet. Make sure the local server is running, then try again. Your draft is still here.");
  }
  let data;
  try { data = await response.json(); } catch {
    throw new Error("SafeNet returned an unexpected response. Please check the server and try again.");
  }
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "Please check your message and try again.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function showError(message) {
  $("error-message").textContent = message;
  $("error-banner").hidden = false;
}

function clearError() { $("error-banner").hidden = true; }
let toastTimer;
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 2800);
}

function draftKey() { return `draft:${state.active?.id || "new"}`; }
function saveDraft() { storage.set(draftKey(), $("message-input").value); }
function restoreDraft() {
  $("message-input").value = storage.get(draftKey());
  resizeInput();
}

function resizeInput() {
  const input = $("message-input");
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
  updateControls();
}

function updateControls() {
  const unavailable = state.busy || state.loading;
  $("send").disabled = unavailable || !$("message-input").value.trim();
  $("message-input").disabled = state.busy;
  $("new-chat").disabled = unavailable;
  document.querySelectorAll(".conversation-select, .conversation-actions button, .prompt-card").forEach((button) => {
    button.disabled = unavailable;
  });
  $("composer").setAttribute("aria-busy", String(state.busy));
}

function updateMode() {
  $("mode-description").textContent = `Live analysis · ${state.config?.model || "OpenAI"}`;
}

function setMode() {
  updateMode();
}

function renderSidebar() {
  const list = $("conversation-list");
  list.replaceChildren();
  $("history-count").textContent = state.conversations.length;
  if (!state.conversations.length) {
    list.append(element("p", "history-empty", "Your saved conversations will appear here. Each new chat keeps a separate incident history."));
  }
  for (const conversation of state.conversations) {
    const selected = state.active?.id === conversation.id;
    const row = element("div", `conversation-row${selected ? " active" : ""}`);
    const button = element("button", "conversation-select");
    button.type = "button";
    button.title = conversation.title;
    if (selected) button.setAttribute("aria-current", "true");
    button.append(icon("chat"), element("span", "", conversation.title));
    button.addEventListener("click", () => openConversation(conversation.id));
    const actions = element("div", "conversation-actions");
    actions.append(
      iconButton("edit", `Rename ${conversation.title}`, () => openDialog("rename", conversation)),
      iconButton("trash", `Delete ${conversation.title}`, () => openDialog("delete", conversation)),
    );
    row.append(button, actions);
    list.append(row);
  }
  updateControls();
}

async function refreshHistory() {
  state.conversations = await api("/conversations");
  renderSidebar();
}

function upsertConversation(conversation) {
  const { turns, ...summary } = conversation;
  state.conversations = [summary, ...state.conversations.filter((item) => item.id !== conversation.id)]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  renderSidebar();
}

function assistantHeader(_mode, timestamp) {
  const header = element("div", "assistant-header");
  header.append(icon("shield"), element("strong", "", "SafeNet assessment"), element("span", "response-mode", "Live"));
  if (timestamp) {
    const time = element("time", "response-time", new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(timestamp)));
    time.dateTime = timestamp;
    time.title = new Date(timestamp).toLocaleString();
    header.append(time);
  }
  return header;
}

function userMessage(message) {
  const block = element("div", "user-message");
  block.append(element("span", "message-label", "Your description"), element("div", "user-text", message));
  return block;
}

function detailRow(label, value) {
  const row = element("div", "detail-row");
  row.append(element("dt", "", label), element("dd", "", value));
  return row;
}

function renderAssessment(assessment) {

  console.log("========== FRONTEND ASSESSMENT ==========");
  console.log("is_security_related:", assessment.is_security_related);
  console.log("final_report:", assessment.final_report);
  console.log("risk_level:", assessment.risk_level);
  console.log("agents:", assessment.agents_completed);
  console.log("==========================================");

  const content = element("div", "assessment");

  // Handle out-of-scope messages separately.
  // Do not show a risk score or risk meter.
  if (
    assessment.current_stage === "complete" &&
    assessment.is_security_related === false
  ) {
    const section = element("section", "scope-response");

    section.append(
      element("h3", "", "Outside SafeNet's scope"),
      element(
        "p",
        "",
        assessment.final_report ||
        "Sorry, SafeNet is focused on cybersecurity and digital-safety concerns. Please describe a security-related concern."
      )
    );

    content.append(section);

    // Stop here. Do NOT execute the risk-assessment code below.
    return content;
  }

  // -----------------------------
  // Normal security assessment
  // -----------------------------

  const level = ["low", "medium", "high", "critical"].includes(assessment.risk_level)
    ? assessment.risk_level
    : "low";

  const risk = element("div", `risk-summary ${level}`);

  const percentage = `${Math.round(assessment.risk_score * 100)}%`;

  const score = element("div");

  score.append(
    element("strong", "risk-score", percentage),
    element("span", "risk-caption", "Risk score")
  );

  const severity = element("div");

  const meter = element("meter", "risk-meter");
  meter.min = 0;
  meter.max = 1;
  meter.value = assessment.risk_score;
  meter.setAttribute("aria-label", "Risk score");
  meter.setAttribute(
    "aria-valuetext",
    `${percentage}, ${level} risk`
  );

  severity.append(
    element("span", "risk-label", `${level.toUpperCase()} RISK`),
    meter
  );

  risk.append(score, severity);
  content.append(risk);

  // Risk reasons
  const riskReasons = assessment.risk_reasons?.length
    ? assessment.risk_reasons
    : ["No strong danger signal was found."];

  const sections = element("div", "assessment-sections");

  for (const [heading, tag, className, items] of [
    ["Why this assessment", "ul", "reasons", riskReasons],
    ["What to do now", "ol", "actions", assessment.recommended_actions || []],
  ]) {
    const section = element("section");
    const list = element(tag, className);

    list.append(
      ...items.map((text) => element("li", "", text))
    );

    section.append(
      element("h3", "", heading),
      list
    );

    sections.append(section);
  }

  content.append(sections);

  // Analysis details
  const details = element("details", "analysis-details");
  details.append(
    element("summary", "", "Analysis details")
  );

  const facts = element("dl");

  const agents = (assessment.agents_completed || [])
    .map((agent) => agent.replaceAll("_", " "))
    .join(" → ");

  facts.append(
    detailRow("Agents", agents),
    detailRow("Route", assessment.route_taken || "N/A"),
    detailRow(
      "Incident type",
      (assessment.situation_type || "unknown").replaceAll("_", " ")
    )
  );

  if (assessment.parsed_domains?.length) {
    facts.append(
      detailRow(
        "Domains",
        assessment.parsed_domains.join(", ")
      )
    );
  }

  if (assessment.investigation?.pattern_matches?.length) {
    facts.append(
      detailRow(
        "Patterns",
        assessment.investigation.pattern_matches.join(", ")
      )
    );
  }

  if (assessment.investigation?.notes?.length) {
    facts.append(
      detailRow(
        "Notes",
        assessment.investigation.notes.join(" ")
      )
    );
  }

  details.append(facts);
  content.append(details);

  // Copy report
  const footer = element("div", "assessment-footer");

  const copy = element("button", "copy-report");
  copy.type = "button";

  copy.append(
    icon("copy"),
    element("span", "", "Copy report")
  );

  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(
        assessment.final_report || ""
      );
      toast("Report copied");
    } catch {
      toast(
        "Copy is unavailable in this browser. You can select the response text instead."
      );
    }
  });

  footer.append(copy);
  content.append(footer);

  return content;
}
function renderChat() {
  const turns = state.active?.turns || [];
  $("welcome").hidden = turns.length > 0;
  $("messages").hidden = !turns.length;
  $("messages").replaceChildren();
  $("chat-title").textContent = state.active?.title || "New conversation";
  document.title = state.active ? `${state.active.title} — SafeNet` : "SafeNet — Security assistant";
  $("context-note").hidden = !turns.length;
  $("message-input").placeholder = turns.length ? "Add a detail or tell me what happened next…" : "Describe the message, link, or activity that concerned you…";
  for (const turn of turns) {
    const article = element("article", "turn");
    article.append(userMessage(turn.user), assistantHeader(turn.mode, turn.created_at), renderAssessment(turn.assessment));
    $("messages").append(article);
  }
  if (!turns.length) $("chat-scroll").scrollTo({ top: 0, behavior: "instant" });
}

function scrollToLatest(smooth = false) {
  requestAnimationFrame(() => {
    // Keep the newest assessment's risk score in view, even for long reports.
    const latest = $("messages").lastElementChild?.querySelector(".assistant-header");
    $("chat-scroll").scrollTo({
      top: latest ? Math.max(0, latest.offsetTop - 24) : 0,
      behavior: smooth && !matchMedia("(prefers-reduced-motion: reduce)").matches ? "smooth" : "instant",
    });
  });
}

function closeMobileSidebar() { $("app").classList.remove("sidebar-mobile-open"); syncSidebar(); }

async function openConversation(id) {
  if (state.busy || state.loading) return;
  saveDraft();
  clearError();
  state.loading = true;
  updateControls();
  try {
    const conversation = await api(`/conversations/${id}`);
    state.active = conversation;
    state.failed = null;
    storage.set("active", id);
    setMode(conversation.mode);
    renderChat();
    renderSidebar();
    restoreDraft();
    closeMobileSidebar();
    scrollToLatest();
  } catch (error) {
    if (error.status === 404) {
      storage.remove("active");
      try { await refreshHistory(); } catch { /* Keep the original error visible. */ }
    }
    showError(error.message);
  } finally { state.loading = false; updateControls(); }
}

function newChat() {
  if (state.busy || state.loading) return;
  saveDraft();
  state.active = null;
  state.failed = null;
  storage.remove("active");
  clearError();
  renderSidebar();
  renderChat();
  restoreDraft();
  closeMobileSidebar();
  $("message-input").focus();
}

function showPending(message, mode) {
  $("welcome").hidden = true;
  $("messages").hidden = false;
  const pending = element("article", "turn");
  pending.id = "pending-message";
  const processing = element("div", "processing");
  processing.textContent = "Assessing your incident…";
  pending.append(userMessage(message), assistantHeader(mode), processing);
  $("messages").append(pending);
  $("announcer").textContent = "SafeNet is processing your message.";
  scrollToLatest(true);
}

async function sendMessage(event) {
  event.preventDefault();
  const message = $("message-input").value.trim();
  const mode = "live";
  if (!message || state.busy || state.loading) return;
  state.busy = true;
  clearError();
  saveDraft();
  updateControls();
  showPending(message, mode);
  try {
    if (!state.active) {
      state.active = await api("/conversations", { method: "POST", body: JSON.stringify({ title: message.replace(/\s+/g, " ").slice(0, 65) }) });
      storage.set("active", state.active.id);
      storage.set(draftKey(), message);
      storage.remove("draft:new");
      upsertConversation(state.active);
      $("chat-title").textContent = state.active.title;
    }
    const previous = state.failed;
    const requestId = previous?.message === message && previous.mode === mode && previous.conversation === state.active.id
      ? previous.id : crypto.randomUUID();
    state.failed = { id: requestId, message, mode, conversation: state.active.id };
    state.active = await api(`/conversations/${state.active.id}/messages`, {
      method: "POST", body: JSON.stringify({ message, request_id: requestId }),
    });
    state.failed = null;
    storage.remove(draftKey());
    $("message-input").value = "";
    upsertConversation(state.active);
    renderChat();
    scrollToLatest(true);
    $("announcer").textContent = `Assessment complete. ${state.active.turns.at(-1).assessment.risk_level} risk.`;
  } catch (error) {
    renderChat();
    showError(error.message);
    $("announcer").textContent = "The assessment could not be completed. Your message is ready to try again.";
  } finally {
    state.busy = false;
    resizeInput();
    $("message-input").focus();
  }
}

function openDialog(action, conversation) {
  if (state.busy || state.loading) return;
  state.dialog = { action, conversation };
  const deleting = action === "delete";
  $("dialog-title").textContent = deleting ? "Delete conversation?" : "Rename conversation";
  $("dialog-description").textContent = deleting
    ? `“${conversation.title}” and its messages will be removed from this device. This cannot be undone.`
    : "Give this conversation a name that’s easy to find later.";
  $("rename-input").hidden = deleting;
  $("rename-label").hidden = deleting;
  $("rename-input").required = !deleting;
  $("rename-input").value = conversation.title;
  $("dialog-confirm").textContent = deleting ? "Delete conversation" : "Save name";
  $("dialog-confirm").classList.toggle("danger", deleting);
  $("conversation-dialog").showModal();
  if (!deleting) { $("rename-input").focus(); $("rename-input").select(); }
  else $("dialog-cancel").focus();
}

async function submitDialog(event) {
  event.preventDefault();
  const { action, conversation } = state.dialog;
  const title = $("rename-input").value.trim();
  if (action === "rename" && !title) { $("rename-input").focus(); return; }
  $("dialog-confirm").disabled = true;
  try {
    const result = await api(`/conversations/${conversation.id}`, {
      method: action === "delete" ? "DELETE" : "PATCH",
      ...(action === "rename" ? { body: JSON.stringify({ title }) } : {}),
    });
    if (action === "delete") {
      if (state.active?.id === conversation.id) { newChat(); }
      storage.remove(`draft:${conversation.id}`);
      state.conversations = state.conversations.filter((item) => item.id !== conversation.id);
    } else {
      state.conversations = state.conversations.map((item) => item.id === conversation.id ? { ...item, title } : item);
      if (state.active?.id === conversation.id) { state.active = result; renderChat(); }
    }
    renderSidebar();
    $("conversation-dialog").close();
    toast(action === "delete" ? "Conversation deleted" : "Conversation renamed");
  } catch (error) { $("conversation-dialog").close(); showError(error.message); }
  finally { $("dialog-confirm").disabled = false; }
}

function syncSidebar() {
  const mobile = mobileLayout.matches;
  const open = mobile ? $("app").classList.contains("sidebar-mobile-open") : !$("app").classList.contains("sidebar-collapsed");
  $("sidebar-open").setAttribute("aria-expanded", String(open));
  $("sidebar").inert = !open;
  $("sidebar").setAttribute("aria-hidden", String(!open));
  document.querySelector(".main").inert = mobile && open;
}

function toggleSidebar(open) {
  const app = $("app");
  if (mobileLayout.matches) app.classList.toggle("sidebar-mobile-open", open);
  else {
    app.classList.toggle("sidebar-collapsed", !open);
    storage.set("sidebar-collapsed", String(!open));
  }
  syncSidebar();
  if (open) $("sidebar-close").focus();
  else $("sidebar-open").focus();
}

$("composer").addEventListener("submit", sendMessage);
$("message-input").addEventListener("input", () => { resizeInput(); saveDraft(); });
$("message-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (!$("send").disabled) $("composer").requestSubmit();
  }
});
$("new-chat").addEventListener("click", newChat);
$("dismiss-error").addEventListener("click", clearError);
$("sidebar-close").addEventListener("click", () => toggleSidebar(false));
$("sidebar-open").addEventListener("click", () => toggleSidebar(true));
$("sidebar-scrim").addEventListener("click", () => toggleSidebar(false));
$("dialog-form").addEventListener("submit", submitDialog);
$("dialog-close").addEventListener("click", () => $("conversation-dialog").close());
$("dialog-cancel").addEventListener("click", () => $("conversation-dialog").close());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("app").classList.contains("sidebar-mobile-open")) toggleSidebar(false);
});
document.querySelectorAll(".prompt-card").forEach((button) => button.addEventListener("click", () => {
  $("message-input").value = button.dataset.prompt;
  resizeInput();
  saveDraft();
  $("message-input").focus();
}));
mobileLayout.addEventListener("change", syncSidebar);
window.addEventListener("beforeunload", saveDraft);

async function init() {
  $("app").classList.toggle("sidebar-collapsed", storage.get("sidebar-collapsed") === "true");
  syncSidebar();
  setMode();
  restoreDraft();
  state.loading = true;
  updateControls();
  try {
    const [config, conversations] = await Promise.all([api("/config"), api("/conversations")]);
    state.config = config;
    state.conversations = conversations;
    updateMode();
    const active = storage.get("active");
    if (active && conversations.some((item) => item.id === active)) {
      state.active = await api(`/conversations/${active}`);
      setMode();
      restoreDraft();
    }
  } catch (error) { showError(error.message); }
  finally {
    state.loading = false;
    renderSidebar();
    renderChat();
    updateControls();
    scrollToLatest();
  }
}

init();
