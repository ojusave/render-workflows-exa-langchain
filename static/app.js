import { apiGetJson, apiPostJson, apiDeleteJson, fetchSsePost, readSseStream } from "./api-client.js";


// -----------------------------------------------------------------------
// Theme
// -----------------------------------------------------------------------
function toggleTheme() {
  const html = document.documentElement;
  const next = html.classList.contains("dark") ? "light" : "dark";
  html.className = next;
  localStorage.setItem("theme", next);
  updateThemeIcons(next);
}

function updateThemeIcons(theme) {
  document.getElementById("icon-sun").style.display = theme === "dark" ? "none" : "block";
  document.getElementById("icon-moon").style.display = theme === "dark" ? "block" : "none";
}

// -----------------------------------------------------------------------
// Config + link setup
// -----------------------------------------------------------------------
const GITHUB_REPO = "https://github.com/ojusave/langchain-test";

function renderSignupUrlWithUtms(content = "footer_link") {
  const params = new URLSearchParams({
    utm_source: "github", utm_medium: "referral",
    utm_campaign: "ojus_demos", utm_content: content,
  });
  return `https://render.com/register?${params.toString()}`;
}

document.getElementById("deploy-btn").href = `https://render.com/deploy?repo=${encodeURIComponent(GITHUB_REPO)}`;
document.getElementById("signup-footer").href = renderSignupUrlWithUtms("footer_link");
document.getElementById("github-link").href = GITHUB_REPO;
document.getElementById("theme-toggle").addEventListener("click", toggleTheme);
updateThemeIcons(document.documentElement.classList.contains("dark") ? "dark" : "light");

// -----------------------------------------------------------------------
// DOM refs
// -----------------------------------------------------------------------
const form = document.getElementById("form");
const inputEl = document.getElementById("input");
const mainEl = document.getElementById("main");
const welcome = document.getElementById("welcome");
const threadEl = document.getElementById("thread");
const sidebar = document.getElementById("sidebar");
const historyList = document.getElementById("history-list");
const sidebarOverlay = document.getElementById("sidebar-overlay");

let currentThreadId = null;
let currentRunId = null;
let timerInterval = null;
let startTime = 0;

// Per-entry live state (reset each query)
let liveBlock = null;
let liveFeed = null;
let liveTimer = null;
let liveError = null;
let classifyItem = null;
let planningItem = null;
let agentItems = {};
let synthesizingItem = null;

// -----------------------------------------------------------------------
// Sidebar: mobile toggle
// -----------------------------------------------------------------------
document.getElementById("sidebar-toggle").addEventListener("click", () => {
  sidebar.classList.toggle("open");
  sidebarOverlay.classList.toggle("open");
});
sidebarOverlay.addEventListener("click", () => {
  sidebar.classList.remove("open");
  sidebarOverlay.classList.remove("open");
});

// -----------------------------------------------------------------------
// Sidebar: threads
// -----------------------------------------------------------------------
function formatRelativeTime(isoString) {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

async function loadHistory() {
  try {
    const threads = await apiGetJson("/history");
    if (!Array.isArray(threads) || threads.length === 0) {
      historyList.innerHTML = '<div class="sidebar-empty">No history yet</div>';
      return;
    }
    historyList.innerHTML = "";
    for (const t of threads) {
      const item = document.createElement("div");
      item.className = "history-item" + (t.id === currentThreadId ? " active" : "");
      item.dataset.id = t.id;
      item.innerHTML =
        `<span class="hi-text">${escapeHtml(t.title)}</span>` +
        `<span class="hi-time">${formatRelativeTime(t.updated_at)}</span>` +
        `<button class="hi-delete" onclick="event.stopPropagation(); deleteThread('${t.id}')" title="Delete">&times;</button>`;
      item.addEventListener("click", () => loadThread(t.id));
      historyList.appendChild(item);
    }
  } catch (e) {
    historyList.innerHTML = '<div class="sidebar-empty">No history yet</div>';
  }
}

async function loadThread(threadId) {
  try {
    const thread = await apiGetJson(`/history/${threadId}`);

    currentThreadId = threadId;
    currentRunId = null;
    stopTimer();

    welcome.style.display = "none";
    threadEl.style.display = "block";
    threadEl.innerHTML = "";

    for (const entry of thread.entries) {
      const block = createEntryBlock(entry.question);
      if (entry.report && entry.report.reply && !entry.report.sections) {
        const answerEl = document.createElement("div");
        answerEl.className = "direct-answer";
        answerEl.innerHTML = renderMarkdown(entry.report.reply);
        block.appendChild(answerEl);
      } else {
        block.appendChild(buildReportHtml(entry.report, entry.run_id));
      }
      threadEl.appendChild(block);
      currentRunId = entry.run_id || null;
    }

    highlightSidebar(threadId);
    updateInputPlaceholder();
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("open");
    mainEl.scrollTop = mainEl.scrollHeight;
  } catch (e) {}
}

async function deleteThread(threadId) {
  try { await apiDeleteJson(`/history/${threadId}`); } catch (e) {}
  if (currentThreadId === threadId) startNewThread();
  loadHistory();
}

function startNewThread() {
  currentThreadId = null;
  currentRunId = null;
  stopTimer();
  threadEl.style.display = "none";
  threadEl.innerHTML = "";
  welcome.style.display = "";
  highlightSidebar(null);
  sidebar.classList.remove("open");
  sidebarOverlay.classList.remove("open");
  updateInputPlaceholder();
  inputEl.focus();
}

function highlightSidebar(threadId) {
  document.querySelectorAll(".history-item").forEach(el => {
    el.classList.toggle("active", el.dataset.id === threadId);
  });
}

// -----------------------------------------------------------------------
// Entry block builder
// -----------------------------------------------------------------------
function createEntryBlock(question) {
  const block = document.createElement("div");
  block.className = "entry-block";
  const q = document.createElement("div");
  q.className = "entry-question";
  q.textContent = question;
  block.appendChild(q);
  return block;
}

function createLiveEntryBlock(question) {
  const block = createEntryBlock(question);

  const timer = document.createElement("span");
  timer.className = "activity-timer";
  timer.textContent = "0:00";
  block.querySelector(".entry-question").prepend(timer);

  const feed = document.createElement("div");
  feed.className = "activity-feed";
  block.appendChild(feed);

  const dashLink = document.createElement("a");
  dashLink.href = "https://render.com/docs/workflows-tutorial";
  dashLink.target = "_blank";
  dashLink.rel = "noopener noreferrer";
  dashLink.className = "pipeline-doc-link";
  dashLink.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px;flex-shrink:0" aria-hidden="true"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Build your first workflow';
  block.appendChild(dashLink);

  const errorEl = document.createElement("div");
  errorEl.className = "activity-error";
  block.appendChild(errorEl);

  return { block, feed, timer, errorEl };
}

// -----------------------------------------------------------------------
// Timer
// -----------------------------------------------------------------------
function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function startTimer() {
  startTime = Date.now();
  if (liveTimer) liveTimer.textContent = "0:00";
  timerInterval = setInterval(() => {
    if (liveTimer) liveTimer.textContent = formatElapsed(Math.floor((Date.now() - startTime) / 1000));
  }, 1000);
}

function stopTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

// -----------------------------------------------------------------------
// Activity feed helpers
// -----------------------------------------------------------------------
function addActivityItem(label, state) {
  const item = document.createElement("div");
  item.className = `activity-item ${state}`;
  item.innerHTML = `<span class="indicator"></span><span class="label">${label}</span>`;
  if (liveFeed) liveFeed.appendChild(item);
  mainEl.scrollTop = mainEl.scrollHeight;
  return item;
}

function markItemDone(item) { item.classList.remove("active"); item.classList.add("done"); }
function markItemError(item) { item.classList.remove("active"); item.classList.add("error"); }

// -----------------------------------------------------------------------
// SSE event handlers
// -----------------------------------------------------------------------
function handleStatus(data) {
  if (data.phase === "classifying") {
    classifyItem = addActivityItem(
      "<strong>Render Workflows</strong> dispatched classify task: <strong>Claude</strong> is analyzing your query...", "active"
    );
  } else if (data.phase === "planning") {
    planningItem = addActivityItem(
      "<strong>Render Workflows</strong> dispatched the plan task: <strong>Claude</strong> is breaking down your question...", "active"
    );
  } else if (data.phase === "synthesizing") {
    synthesizingItem = addActivityItem("<strong>Claude</strong> is synthesizing the final report...", "active");
  }
}

function handleClassified(data) {
  if (classifyItem) markItemDone(classifyItem);
  const label = data.type === "research"
    ? "<strong>Claude</strong> classified this as a research query"
    : "<strong>Claude</strong> classified this as a direct question";
  addActivityItem(label, "done");
}

function handleDirectAnswer(data) {
  stopTimer();
  currentRunId = data.run_id || null;
  if (data.thread_id) currentThreadId = data.thread_id;

  const tools = data.tools || [];
  if (tools.includes("LangSmith")) {
    addActivityItem("<strong>LangSmith</strong> traced all calls in this pipeline", "done");
  }

  setTimeout(() => {
    if (liveBlock) {
      const answerEl = document.createElement("div");
      answerEl.className = "direct-answer";
      answerEl.innerHTML = renderMarkdown(data.reply || "");
      liveBlock.appendChild(answerEl);
      mainEl.scrollTop = mainEl.scrollHeight;
    }
    loadHistory();
    highlightSidebar(currentThreadId);
    updateInputPlaceholder();
  }, 300);
}

function handlePlan(data) {
  if (planningItem) markItemDone(planningItem);
  const subtopics = data.subtopics || [];
  let tagsHtml = '<div class="subtopic-list">';
  for (const st of subtopics) tagsHtml += `<span class="subtopic-tag">${escapeHtml(st)}</span>`;
  tagsHtml += '</div>';
  addActivityItem(`<strong>Claude</strong> planned ${subtopics.length} subtopics` + tagsHtml, "done");
  addActivityItem(`<strong>Render Workflows</strong> launched ${subtopics.length} parallel agents`, "done");
}

function handleAgentStart(data) {
  const item = addActivityItem(
    `<strong>LangGraph</strong> agent is using <strong>Exa</strong> to research: ${escapeHtml(data.subtopic)}`, "active"
  );
  agentItems[data.index] = { item, startTime: Date.now() };
}

function handleAgentDone(data) {
  const entry = agentItems[data.index];
  if (!entry) return;
  markItemDone(entry.item);
  const elapsed = Math.round((Date.now() - entry.startTime) / 1000);
  const elapsedSpan = document.createElement("span");
  elapsedSpan.className = "elapsed";
  elapsedSpan.textContent = `${elapsed}s`;
  entry.item.appendChild(elapsedSpan);
  entry.item.querySelector(".label").innerHTML = `<strong>LangGraph</strong> agent finished: ${escapeHtml(data.subtopic)}`;
}

function updateInputPlaceholder() {
  inputEl.placeholder = currentThreadId
    ? "Ask a follow-up question..."
    : "What do you want to research?";
}

function handleDone(data) {
  if (synthesizingItem) markItemDone(synthesizingItem);
  stopTimer();
  currentRunId = data.run_id || null;
  if (data.thread_id) currentThreadId = data.thread_id;

  const tools = data.tools || [];
  if (tools.includes("LangSmith")) {
    addActivityItem("<strong>LangSmith</strong> traced all calls in this pipeline", "done");
  }

  setTimeout(() => {
    if (liveBlock) {
      const reportCard = buildReportHtml(data.report, data.run_id);
      liveBlock.appendChild(reportCard);
      mainEl.scrollTop = mainEl.scrollHeight;
    }
    loadHistory();
    highlightSidebar(currentThreadId);
    updateInputPlaceholder();
  }, 300);
}

function handleError(data) {
  stopTimer();
  if (classifyItem && classifyItem.classList.contains("active")) markItemError(classifyItem);
  if (planningItem) markItemError(planningItem);
  if (synthesizingItem) markItemError(synthesizingItem);
  for (const key of Object.keys(agentItems)) {
    const e = agentItems[key];
    if (e.item.classList.contains("active")) markItemError(e.item);
  }
  if (liveError) liveError.textContent = data.message || "Unknown error";
}

// -----------------------------------------------------------------------
// Report builder
// -----------------------------------------------------------------------
function renderMarkdown(text) {
  let html = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => `<pre><code>${code.trim()}</code></pre>`);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  const lines = html.split("\n"), blocks = [];
  let listBuffer = [], inList = false;
  for (const line of lines) {
    const m = line.match(/^[\s]*[-•]\s+(.*)/);
    if (m) { inList = true; listBuffer.push(`<li>${m[1]}</li>`); }
    else {
      if (inList) { blocks.push(`<ul>${listBuffer.join("")}</ul>`); listBuffer = []; inList = false; }
      const t = line.trim();
      if (t.startsWith("<pre>")) blocks.push(t);
      else if (t) blocks.push(`<p>${t}</p>`);
    }
  }
  if (inList) blocks.push(`<ul>${listBuffer.join("")}</ul>`);
  return blocks.join("");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function buildReportHtml(data, runId) {
  const card = document.createElement("div");
  card.className = "report-card";
  let html = "";
  if (data.title) html += `<h2>${escapeHtml(data.title)}</h2>`;
  if (data.summary) html += `<div class="report-summary">${escapeHtml(data.summary)}</div>`;
  if (data.sections) {
    for (const s of data.sections) {
      html += `<div class="report-section">`;
      if (s.heading) html += `<h3>${escapeHtml(s.heading)}</h3>`;
      if (s.content) html += `<div class="content">${renderMarkdown(s.content)}</div>`;
      html += `</div>`;
    }
  }
  if (data.sources && data.sources.length > 0) {
    html += `<div class="report-sources"><h3>Sources</h3><ul>`;
    for (const src of data.sources) {
      const title = escapeHtml(src.title || src.url || "Source");
      const url = src.url || "#";
      html += `<li><a href="${url}" target="_blank" rel="noopener">${title}</a>`;
      if (src.url) html += `<span class="source-url">${escapeHtml(src.url)}</span>`;
      html += `</li>`;
    }
    html += `</ul></div>`;
  }
  if (runId) {
    const fbId = "fb-" + runId;
    html += `<div class="feedback-bar" id="${fbId}"><span>Was this helpful?</span>`;
    html += `<button class="feedback-btn" onclick="sendFeedback('${runId}', 1, this)" title="Helpful"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14z"/><path d="M7 22H4a2 2 0 01-2-2v-7a2 2 0 012-2h3"/></svg></button>`;
    html += `<button class="feedback-btn" onclick="sendFeedback('${runId}', 0, this)" title="Not helpful"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 003 3l4-9V2H5.72a2 2 0 00-2 1.7l-1.38 9a2 2 0 002 2.3H10z"/><path d="M17 2h2.67A2.31 2.31 0 0122 4v7a2.31 2.31 0 01-2.33 2H17"/></svg></button>`;
    html += `</div>`;
  }
  card.innerHTML = html;
  return card;
}

// -----------------------------------------------------------------------
// Feedback
// -----------------------------------------------------------------------
async function sendFeedback(runId, score, btn) {
  const bar = btn.closest(".feedback-bar");
  if (!bar) return;
  bar.querySelectorAll(".feedback-btn").forEach(b => { b.disabled = true; b.classList.remove("selected"); });
  btn.classList.add("selected");
  try {
    await apiPostJson("/feedback", { run_id: runId, score });
  } catch (e) {}
  const thanks = document.createElement("span");
  thanks.className = "feedback-thanks";
  thanks.textContent = "Thanks for your feedback";
  bar.appendChild(thanks);
}

// -----------------------------------------------------------------------
// SSE parser
// -----------------------------------------------------------------------
function parseSSE(text) {
  const events = [], parts = text.split("\n\n");
  const remainder = parts.pop();
  for (const part of parts) {
    if (!part.trim()) continue;
    let event = "message", data = "";
    for (const line of part.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7);
      else if (line.startsWith("data: ")) data = line.slice(6);
    }
    if (data) { try { events.push({ event, data: JSON.parse(data) }); } catch (e) {} }
  }
  return { events, remainder: remainder || "" };
}

// -----------------------------------------------------------------------
// Form submit
// -----------------------------------------------------------------------
function sendExample(btn) {
  inputEl.value = btn.textContent;
  form.dispatchEvent(new Event("submit"));
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";

  welcome.style.display = "none";
  threadEl.style.display = "block";

  // Reset per-entry live state
  classifyItem = null;
  planningItem = null;
  agentItems = {};
  synthesizingItem = null;

  const { block, feed, timer, errorEl } = createLiveEntryBlock(text);
  liveBlock = block;
  liveFeed = feed;
  liveTimer = timer;
  liveError = errorEl;
  threadEl.appendChild(block);
  mainEl.scrollTop = mainEl.scrollHeight;
  startTimer();

  const submitBtn = form.querySelector("button[type='submit']");
  submitBtn.disabled = true;

  try {
    const body = { question: text };
    if (currentThreadId) body.thread_id = currentThreadId;

    const res = await fetchSsePost("/research", body, undefined);
    await readSseStream(res, (event, data) => {
      if (event === "status") handleStatus(data);
      else if (event === "classified") handleClassified(data);
      else if (event === "direct_answer") handleDirectAnswer(data);
      else if (event === "plan") handlePlan(data);
      else if (event === "agent_start") handleAgentStart(data);
      else if (event === "agent_done") handleAgentDone(data);
      else if (event === "done") handleDone(data);
      else if (event === "error") handleError(data);
    });

  } catch (err) {
    handleError({ message: err.message });
  } finally {
    submitBtn.disabled = false;
    inputEl.focus();
  }
});

window.sendExample = sendExample;
window.startNewThread = startNewThread;
window.deleteThread = deleteThread;
window.sendFeedback = sendFeedback;

// -----------------------------------------------------------------------
// Init
// -----------------------------------------------------------------------
loadHistory();
inputEl.focus();
