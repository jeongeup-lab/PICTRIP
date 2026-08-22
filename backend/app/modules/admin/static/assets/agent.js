const PRESETS = [
  "통영 2박3일 일정 짜줘",
  "경주 2일 일정인데 맛집도 넣어줘",
  "내가 저장한 곳이랑 비슷한 데 추천해줘",
  "파리 가볼 만한 곳",
  "환전 어디서 해?",
  "좋아 그럼",
  "여수 바다 보이는 카페",
  "제주 호텔 추천해줘",
];

const ANCHORS = [
  ["food", "근처 맛집"],
  ["cafe", "근처 카페"],
  ["nearby", "근처 볼거리"],
  ["related", "닮은 곳"],
  ["crowd", "지금 붐비나"],
];

const log = document.getElementById("ac-log");
const form = document.getElementById("ac-form");
const input = document.getElementById("ac-message");
const send = document.getElementById("ac-send");
const photoInput = document.getElementById("ac-photo");
const photoLabel = photoInput.closest(".ac-photo");
const photoName = document.getElementById("ac-photo-name");
const tokenInput = document.getElementById("ac-token");
const coordsSelect = document.getElementById("ac-coords");
const historyToggle = document.getElementById("ac-history");
const metaBox = document.getElementById("ac-meta");
const reqBox = document.getElementById("ac-req");
const routerPill = document.getElementById("ac-router");

let history = [];
let lastIntent = null;
let lastSpots = [];
let focused = null;
let streaming = false;
let minted = { seed: "", token: "" };

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

const scroll = () => log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });

function renderSaid(text) {
  const node = el("div", "ac-say");
  const parts = String(text).split(/(\*\*[^*]+\*\*|\[\d+\])/g);
  for (const part of parts) {
    if (/^\*\*[^*]+\*\*$/.test(part)) node.appendChild(el("b", null, part.slice(2, -2)));
    else if (/^\[\d+\]$/.test(part)) node.appendChild(el("span", "ac-ref", part));
    else if (part) node.appendChild(document.createTextNode(part));
  }
  return node;
}

async function bearer() {
  const raw = tokenInput.value.trim();
  if (!raw) return null;
  if (!/^\d+$/.test(raw)) return raw;
  if (minted.seed === raw) return minted.token;
  const res = await fetch(`/admin/api/agent/token?user_id=${raw}`);
  if (!res.ok) throw new Error("토큰을 발급하지 못했습니다.");
  const body = await res.json();
  minted = { seed: raw, token: body.data.token };
  return minted.token;
}

function coords() {
  const raw = coordsSelect.value;
  if (!raw) return null;
  const [lat, lng] = raw.split(",").map(Number);
  return { lat, lng };
}

function context() {
  if (!lastSpots.length && !lastIntent) return null;
  const box = { spots: lastSpots.slice(0, 8).map((s) => ({ contentId: s.contentId, title: s.title })) };
  if (lastIntent) box.intent = lastIntent;
  if (focused) box.focusContentId = focused;
  return box;
}

function body({ message, intent, patch }) {
  const out = { clientRequestId: `admin-${Date.now()}` };
  if (message) out.message = message;
  const at = coords();
  if (at) Object.assign(out, at);
  out.clientTime = new Date().toISOString();
  const box = context();
  if (box) out.context = box;
  if (intent) out.intent = intent;
  if (patch) out.patch = patch;
  if (historyToggle.checked && history.length) out.history = history.slice(-8);
  return out;
}

function meta(done, ms) {
  metaBox.replaceChildren();
  const rows = [
    ["결과", `${done.spots.length}곳 / 전체 ${done.totalCount}`],
    ["소요", `${ms}ms`],
    ["intent", JSON.stringify(trimIntent(done.intent))],
    ["traceId", done.traceId || "–"],
  ];
  for (const [key, value] of rows) {
    const row = el("div");
    row.appendChild(el("span", "ac-dim", `${key} · `));
    row.appendChild(el("code", null, value));
    metaBox.appendChild(row);
  }
}

function trimIntent(intent) {
  const out = {};
  for (const [key, value] of Object.entries(intent || {})) {
    const empty = value == null || value === false || value === "" ||
      (Array.isArray(value) && !value.length) || value === "any" || value === "search";
    if (!empty) out[key] = value;
  }
  return out;
}

function turnBox(question, replay) {
  if (log.querySelector(".ac-empty")) log.replaceChildren();
  const turn = el("div", "ac-turn");
  turn.appendChild(el("div", replay ? "ac-ask ac-replay" : "ac-ask", question));
  const steps = el("div", "ac-steps");
  const say = el("div", "ac-say");
  turn.append(steps, say);
  log.appendChild(turn);
  scroll();
  return { turn, steps, say };
}

function drawSteps(box, list) {
  box.replaceChildren();
  for (const step of list) {
    const node = el("div", `ac-step${step.status === "run" ? " run" : ""}`);
    node.appendChild(document.createTextNode(step.label));
    if (step.badge) node.appendChild(el("span", "ac-badge", step.badge));
    box.appendChild(node);
  }
}

function drawCards(turn, spots) {
  turn.querySelector(".ac-cards")?.remove();
  turn.querySelector(".ac-actions")?.remove();
  if (!spots.length) return;
  const grid = el("div", "ac-cards");
  spots.forEach((spot, index) => {
    const card = el("button", "ac-card");
    card.type = "button";
    if (spot.imageUrl) {
      const img = el("img");
      img.src = spot.imageUrl;
      img.alt = "";
      img.loading = "lazy";
      card.appendChild(img);
    }
    const name = el("div", "ac-name");
    name.appendChild(el("span", "ac-n", `${index + 1} `));
    name.appendChild(document.createTextNode(spot.title));
    card.appendChild(name);
    card.appendChild(el("div", "ac-sub", spot.regionLabel || ""));
    card.onclick = () => pickCard(turn, spot, card);
    grid.appendChild(card);
  });
  turn.appendChild(grid);
}

function pickCard(turn, spot, node) {
  focused = spot.contentId;
  for (const other of turn.querySelectorAll(".ac-card")) other.classList.remove("on");
  node.classList.add("on");
  turn.querySelector(".ac-actions")?.remove();
  const bar = el("div", "ac-actions");
  for (const [action, label] of ANCHORS) {
    const chip = el("button", "ac-chip", `${spot.title} · ${label}`);
    chip.type = "button";
    chip.onclick = () => ask({ anchor: { contentId: spot.contentId, action }, label: `${spot.title} — ${label}` });
    bar.appendChild(chip);
  }
  turn.appendChild(bar);
  scroll();
}

function drawChips(turn, refinements) {
  turn.querySelector(".ac-chips")?.remove();
  if (!refinements?.length) return;
  const bar = el("div", "ac-chips");
  for (const item of refinements) {
    const chip = el("button", "ac-chip", item.label);
    chip.type = "button";
    chip.onclick = () => run({ intent: lastIntent, patch: item.patch, label: `칩 · ${item.label}` });
    bar.appendChild(chip);
  }
  turn.appendChild(bar);
}

function drawSources(turn, items) {
  turn.querySelector(".ac-src")?.remove();
  if (!items?.length) return;
  const bar = el("div", "ac-src");
  for (const item of items.slice(0, 6)) {
    if (item.url) {
      const link = el("a", null, item.title);
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      bar.appendChild(link);
    } else {
      bar.appendChild(el("span", null, item.title));
    }
  }
  turn.appendChild(bar);
}

function fail(turn, code, message) {
  const box = el("div", "ac-err");
  box.appendChild(el("code", null, code));
  box.appendChild(document.createTextNode(` ${message}`));
  turn.appendChild(box);
}

async function run({ message, intent, patch, label, photo }) {
  if (streaming) return;
  streaming = true;
  send.disabled = true;
  const shown = label || message || "(사진)";
  const view = turnBox(shown, Boolean(label));
  const payload = body({ message, intent, patch });
  reqBox.textContent = JSON.stringify(payload, null, 2);
  const started = performance.now();

  try {
    const headers = {};
    const token = await bearer();
    if (token) headers.Authorization = `Bearer ${token}`;
    let init;
    if (photo) {
      const form = new FormData();
      form.append("photo", photo);
      for (const [key, value] of Object.entries(payload)) {
        if (value == null) continue;
        form.append(key, typeof value === "object" ? JSON.stringify(value) : String(value));
      }
      init = { method: "POST", headers, body: form };
    } else {
      init = { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(payload) };
    }
    const res = await fetch("/v1/agent/chat", init);
    if (!res.ok) {
      const envelope = await res.json().catch(() => null);
      fail(view.turn, envelope?.error?.code || `HTTP ${res.status}`, envelope?.error?.message || "");
      return;
    }
    await consume(res, view, shown, started);
  } catch (error) {
    fail(view.turn, "CONSOLE", error.message);
  } finally {
    streaming = false;
    send.disabled = false;
    scroll();
  }
}

async function consume(res, view, shown, started) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const steps = [];
  let buffer = "";
  let text = "";
  let done = null;

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      let name = "";
      let raw = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7).trim();
        else if (line.startsWith("data: ")) raw += line.slice(6);
      }
      if (!name || !raw) continue;
      let data;
      try { data = JSON.parse(raw); } catch { continue; }

      if (name === "step") {
        const at = steps.findIndex((s) => s.index === data.index);
        if (at < 0) steps.push(data); else steps[at] = data;
        drawSteps(view.steps, steps);
      } else if (name === "delta") {
        text += data.text;
        view.say.replaceWith(view.say = renderSaid(text));
      } else if (name === "cards") {
        lastSpots = data.spots || [];
        drawCards(view.turn, lastSpots);
        drawChips(view.turn, data.refinements);
      } else if (name === "sources") {
        drawSources(view.turn, data.items);
      } else if (name === "done") {
        done = data;
      } else if (name === "error") {
        fail(view.turn, data.code, data.message);
      }
      scroll();
    }
  }

  if (!done) return;
  view.say.replaceWith(view.say = renderSaid(done.answerText));
  lastSpots = done.spots || [];
  lastIntent = done.intent || null;
  focused = null;
  drawCards(view.turn, lastSpots);
  drawChips(view.turn, done.refinements);
  drawSources(view.turn, done.sources);
  meta(done, Math.round(performance.now() - started));
  history.push({ role: "user", text: shown });
  history.push({ role: "assistant", text: done.answerText, spotIds: lastSpots.slice(0, 8).map((s) => s.contentId) });
}

async function ask({ anchor, label }) {
  if (streaming) return;
  streaming = true;
  send.disabled = true;
  const view = turnBox(label, true);
  const payload = { anchor };
  const at = coords();
  if (at) Object.assign(payload, at);
  const box = context();
  if (box) payload.context = box;
  reqBox.textContent = JSON.stringify(payload, null, 2);
  const started = performance.now();
  try {
    const headers = { "Content-Type": "application/json" };
    const token = await bearer();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch("/v1/agent/ask", { method: "POST", headers, body: JSON.stringify(payload) });
    const envelope = await res.json();
    if (!res.ok) {
      fail(view.turn, envelope?.error?.code || `HTTP ${res.status}`, envelope?.error?.message || "");
      return;
    }
    const data = envelope.data;
    drawSteps(view.steps, (data.steps || []).map((s, i) => ({ ...s, index: i, status: "done" })));
    view.say.replaceWith(view.say = renderSaid((data.answer || []).map((seg) => seg.text).join("")));
    lastSpots = data.spots || [];
    lastIntent = data.intent || null;
    drawCards(view.turn, lastSpots);
    drawChips(view.turn, data.refinements);
    meta({ spots: lastSpots, totalCount: data.totalCount, intent: lastIntent, traceId: null }, Math.round(performance.now() - started));
  } catch (error) {
    fail(view.turn, "CONSOLE", error.message);
  } finally {
    streaming = false;
    send.disabled = false;
    scroll();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  const photo = photoInput.files?.[0] || null;
  if (!message && !photo) return;
  input.value = "";
  photoInput.value = "";
  photoLabel.classList.remove("on");
  photoName.textContent = "";
  run({ message: message || null, photo });
});

photoInput.addEventListener("change", () => {
  const file = photoInput.files?.[0];
  photoLabel.classList.toggle("on", Boolean(file));
  photoName.textContent = file ? `첨부: ${file.name}` : "";
});

document.getElementById("ac-reset").addEventListener("click", () => {
  history = [];
  lastIntent = null;
  lastSpots = [];
  focused = null;
  log.replaceChildren(el("div", "ac-empty", "아래에 질문을 적거나 예시를 누르세요."));
  metaBox.replaceChildren(el("span", "ac-dim", "아직 없습니다."));
  reqBox.textContent = "–";
});

const presetBar = document.getElementById("ac-presets");
for (const preset of PRESETS) {
  const chip = el("button", "ac-chip", preset);
  chip.type = "button";
  chip.onclick = () => run({ message: preset });
  presetBar.appendChild(chip);
}

fetch("/admin/api/agent/router")
  .then((res) => res.json())
  .then((body) => {
    routerPill.replaceChildren();
    routerPill.appendChild(el("span", "dot live"));
    routerPill.appendChild(document.createTextNode(` router: ${body.data.router}`));
  })
  .catch(() => {});
