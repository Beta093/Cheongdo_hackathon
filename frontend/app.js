"use strict";

const $ = (id) => document.getElementById(id);
let sessionId;
let busy = false;
let lastQuestion = "";
let chatRetries = 0;
let todayRetries = 0;
let storageAvailable = true;

function newSessionId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

try {
  sessionId = localStorage.getItem("gamjaba-session");
  if (!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(sessionId || "")) {
    sessionId = newSessionId();
    localStorage.setItem("gamjaba-session", sessionId);
  }
} catch {
  storageAvailable = false;
  sessionId = newSessionId();
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    signal: options.signal || AbortSignal.timeout(55000),
    headers: { "X-Session-Id": sessionId, ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { /* Use a local, safe fallback. */ }
    throw new Error(typeof detail === "string" ? detail : `요청을 처리하지 못했습니다 (${response.status}).`);
  }
  return response;
}

function badges(evidence) {
  const row = element("div", undefined, "badges");
  row.append(element("span", "AI 생성", "ai-label"));
  row.append(element("span", evidence, `evidence ${evidence === "확인 필요" ? "uncertain" : ""}`));
  return row;
}

function sources(items = []) {
  const details = element("details", undefined, "sources");
  details.append(element("summary", items.length ? `근거 자료 ${items.length}개` : "검토된 근거 자료 없음 · 확인 필요"));
  const list = element("ul");
  for (const source of items) {
    const item = element("li");
    let valid = false;
    try { valid = new URL(source.source_url).protocol === "https:" && source.reviewed === true; } catch { /* Unverified URL. */ }
    if (valid) {
      const link = element("a", source.source_title);
      link.href = source.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      item.append(link, document.createTextNode(` · 확인일 ${source.retrieved_at}`));
    } else {
      item.textContent = `${source.source_title} · 확인 필요`;
    }
    list.append(item);
  }
  details.append(list);
  return details;
}

function modelBanner(mode) {
  $("model-banner").textContent = mode === "fake"
    ? "테스트용 가짜 모델 모드입니다. 실제 AI 모델 응답이 아닙니다. 자료가 검토되기 전에는 작업·일정 제안이 제한됩니다."
    : "AI 생성 답변은 근거와 함께 확인하세요. 날씨 정보 없음 · 현장 측정 정보 없음";
}

async function loadToday() {
  $("retry-today").hidden = true;
  $("today-content").replaceChildren(element("p", "자료를 확인하고 있습니다…", "empty"));
  try {
    const data = await (await api("/farms/demo/today")).json();
    modelBanner(data.model_mode);
    $("today-date").textContent = `${data.date} · 서울 기준`;
    const nodes = [];
    for (const task of data.tasks) {
      const card = element("article", undefined, "card");
      card.append(badges(task.evidence), element("h3", task.title), element("p", task.reason), sources(task.sources));
      const request = element("button", "일정 제안 요청", "secondary");
      request.type = "button";
      request.addEventListener("click", () => fillQuestion(`${task.title} 작업을 오늘 일정으로 제안해줘`));
      card.append(request);
      nodes.push(card);
    }
    for (const notice of data.notices) {
      const card = element("article", undefined, "card");
      card.append(badges(notice.evidence), element("p", notice.text));
      nodes.push(card);
    }
    nodes.push(element("p", data.weather, "fine"));
    $("today-content").replaceChildren(...nodes);
  } catch (error) {
    $("today-content").replaceChildren(element("p", friendlyError(error), "empty"));
    $("retry-today").hidden = todayRetries >= 2;
  }
}

async function loadCalendar() {
  $("refresh-calendar").disabled = true;
  try {
    const items = await (await api("/farms/demo/calendar")).json();
    const nodes = items.map((event) => {
      const card = element("article", undefined, "card");
      card.append(element("div", event.date, "calendar-date"), badges(event.evidence),
        element("h3", event.title), element("p", event.reason), sources(event.sources));
      return card;
    });
    $("calendar-content").replaceChildren(...(nodes.length ? nodes : [element("p", "아직 승인한 일정이 없습니다.", "empty")]));
  } catch (error) {
    $("calendar-content").replaceChildren(element("p", friendlyError(error), "empty"));
  } finally {
    $("refresh-calendar").disabled = false;
  }
}

function renderProposal(proposal) {
  const box = element("section", undefined, "proposal");
  box.append(element("h3", "승인 대기 · 일정 제안"), badges(proposal.event.evidence),
    element("p", `${proposal.event.date} · ${proposal.event.title}`), element("p", proposal.event.reason),
    sources(proposal.event.sources), element("p", "승인하기 전에는 일정에 저장되지 않습니다. 제안은 30분 후 만료됩니다.", "fine"));
  const actions = element("div", undefined, "actions");
  const status = element("p", "", "fine");
  status.setAttribute("role", "status");
  for (const [action, label] of [["approve", "승인하고 일정 추가"], ["reject", "거절"]]) {
    const button = element("button", label, action === "approve" ? "primary" : "secondary");
    button.type = "button";
    button.addEventListener("click", async () => {
      for (const control of actions.children) control.disabled = true;
      try {
        await api(`/proposals/${encodeURIComponent(proposal.id)}/${action}`, { method: "POST" });
        status.textContent = action === "approve" ? "승인되었습니다. 일정 목록에 추가했어요." : "거절했습니다. 일정은 저장되지 않았어요.";
        actions.remove();
        await loadCalendar();
      } catch (error) {
        status.textContent = friendlyError(error);
        for (const control of actions.children) control.disabled = false;
      }
    });
    actions.append(button);
  }
  box.append(actions, status);
  return box;
}

function addMessage(text, kind, payload) {
  const message = element("article", undefined, `message ${kind}`);
  if (kind === "assistant") message.append(badges(payload.evidence));
  message.append(element("p", text));
  if (kind === "assistant") {
    message.append(sources(payload.sources));
    for (const proposal of payload.proposals || []) message.append(renderProposal(proposal));
  }
  $("chat-messages").append(message);
  $("chat-messages").scrollTop = $("chat-messages").scrollHeight;
}

function friendlyError(error) {
  if (["TimeoutError", "AbortError"].includes(error.name)) return "응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.";
  return error.message || "연결을 확인한 뒤 다시 시도해 주세요.";
}

// fetch is used because EventSource cannot POST or send X-Session-Id.
async function readSSE(response, handle) {
  if (!response.body) throw new Error("이 브라우저에서 응답 스트림을 읽을 수 없습니다.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (!block || block.startsWith(":")) continue;
        const lines = block.split("\n");
        const name = lines.find((line) => line.startsWith("event: "))?.slice(7);
        const data = lines.filter((line) => line.startsWith("data: ")).map((line) => line.slice(6)).join("\n");
        if (name && data) handle(name, JSON.parse(data));
      }
      if (done) break;
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

async function sendQuestion(question, isRetry = false) {
  if (busy || !question.trim() || question.length > 2000) return;
  busy = true;
  $("send").disabled = true;
  $("retry-chat").hidden = true;
  if (!isRetry) {
    chatRetries = 0;
    lastQuestion = question;
    addMessage(question, "user");
    $("question").value = "";
    updateCount();
  }
  $("chat-status").textContent = "연결 중…";
  let receivedDone = false;
  let receivedMessage = false;
  let receivedError = false;
  try {
    const response = await api("/farms/demo/chat", { method: "POST", body: JSON.stringify({ message: question }) });
    await readSSE(response, (name, data) => {
      if (name === "status") $("chat-status").textContent = data.text;
      if (name === "tool_call") $("chat-status").textContent = data.name === "search_knowledge" ? "근거 자료를 검색하고 있습니다…" : "승인할 일정 제안을 준비하고 있습니다…";
      if (name === "message" && !receivedMessage) {
        receivedMessage = true;
        modelBanner(data.model_mode);
        addMessage(data.text, "assistant", data);
      }
      if (name === "error") {
        receivedError = true;
        addMessage(data.text, "error");
        $("retry-chat").hidden = !data.retryable || chatRetries >= 2;
      }
      if (name === "done") receivedDone = true;
    });
    if (!receivedDone || (!receivedMessage && !receivedError)) throw new Error("응답 연결이 끊겼습니다. 다시 시도해 주세요.");
    $("chat-status").textContent = receivedError ? "응답을 완료하지 못했습니다." : "답변 확인이 끝났습니다.";
  } catch (error) {
    addMessage(friendlyError(error), "error");
    // A delivered final response may already contain a pending proposal; do not duplicate it.
    $("retry-chat").hidden = receivedMessage || chatRetries >= 2;
    $("chat-status").textContent = "연결 상태를 확인해 주세요.";
  } finally {
    busy = false;
    $("send").disabled = false;
  }
}

function updateCount() { $("char-count").textContent = `${$("question").value.length.toLocaleString("ko-KR")} / 2,000자`; }
function fillQuestion(text) {
  $("question").value = text;
  updateCount();
  $("question").focus();
  $("chat").scrollIntoView();
}

$("start").addEventListener("click", async () => {
  $("start").disabled = true;
  $("global-status").textContent = "데모 과원을 준비하고 있습니다…";
  try {
    const farm = await (await api("/farms/demo")).json();
    $("farm-name").textContent = farm.name;
    $("farm-context").textContent = `${farm.region} · ${farm.weather}`;
    modelBanner(farm.model_mode);
    $("workspace").hidden = false;
    $("start").hidden = true;
    $("global-status").textContent = storageAvailable ? "데모 과원이 준비되었습니다." : "브라우저 저장소를 사용할 수 없어 이 페이지에서만 세션이 유지됩니다.";
    await Promise.all([loadToday(), loadCalendar()]);
  } catch (error) {
    $("global-status").textContent = friendlyError(error);
    $("start").disabled = false;
  }
});
$("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendQuestion($("question").value.trim()); });
$("question").addEventListener("input", updateCount);
$("retry-chat").addEventListener("click", () => { chatRetries += 1; sendQuestion(lastQuestion, true); });
$("retry-today").addEventListener("click", () => { todayRetries += 1; loadToday(); });
$("refresh-calendar").addEventListener("click", loadCalendar);
document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => fillQuestion(button.dataset.question)));
