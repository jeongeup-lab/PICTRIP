const SEEDS = [
  "통영 2박3일 일정 짜줘",
  "경주 2일 일정인데 맛집도 넣어줘",
  "내가 저장한 곳이랑 비슷한 데 추천해줘",
  "여수 바다 보이는 카페",
  "파리 가볼 만한 곳",
  "환전 어디서 해?",
  "좋아 그럼",
];

const ANCHORS = [
  ["food", "근처 맛집"],
  ["cafe", "근처 카페"],
  ["nearby", "근처 볼거리"],
  ["related", "닮은 곳"],
  ["crowd", "지금 붐비나"],
];

const thread = document.getElementById("thread");
const opening = document.getElementById("opening");
const form = document.getElementById("form");
const ask = document.getElementById("ask");
const go = document.getElementById("go");
const photo = document.getElementById("photo");
const clip = document.getElementById("clip");
const clipName = document.getElementById("clipname");
const where = document.getElementById("where");
const who = document.getElementById("who");
const multi = document.getElementById("multi");
const jump = document.getElementById("jump");
const jumpDown = document.getElementById("jumpdown");
const inspector = document.getElementById("inspector");
const stats = document.getElementById("stats");
const sent = document.getElementById("sent");
const tip = document.getElementById("tip");

let history = [];
let lastIntent = null;
let lastSpots = [];
let focused = null;
let busy = false;
let pinned = true;
let abort = null;
let minted = { seed: "", token: "" };

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

function nudge() {
  if (pinned) thread.scrollTop = thread.scrollHeight;
}

thread.addEventListener("scroll", () => {
  pinned = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 80;
  jumpDown.classList.toggle("show", !pinned && busy);
});

jumpDown.addEventListener("click", () => {
  pinned = true;
  jumpDown.classList.remove("show");
  thread.scrollTop = thread.scrollHeight;
});

function fillLine(node, text, trailing) {
  node.replaceChildren();
  for (const part of text.split(/(\*\*[^*]+\*\*|\[\d+\])/g)) {
    if (/^\*\*[^*]+\*\*$/.test(part)) {
      node.appendChild(el("b", null, part.slice(2, -2)));
    } else if (/^\[\d+\]$/.test(part)) {
      const mark = el("button", "cite", part.slice(1, -1));
      mark.type = "button";
      mark.dataset.at = part.slice(1, -1);
      node.appendChild(mark);
    } else if (part) {
      node.appendChild(document.createTextNode(part));
    }
  }
  if (trailing) node.appendChild(el("span", "caret"));
}

function paintSay(view, text, streaming) {
  const lines = text.split("\n");
  view.lines ??= [];
  for (let i = 0; i < lines.length; i += 1) {
    if (!view.lines[i]) {
      view.lines[i] = el("div", "line");
      view.say.appendChild(view.lines[i]);
    }
    const isLast = i === lines.length - 1;
    if (isLast || !view.lines[i].dataset.set) {
      fillLine(view.lines[i], lines[i], streaming && isLast);
      if (!isLast) view.lines[i].dataset.set = "1";
    }
  }
  wireCites(view.turn);
}

function wireCites(turn) {
  for (const mark of turn.querySelectorAll(".cite:not([data-wired])")) {
    mark.dataset.wired = "1";
    const at = Number(mark.dataset.at) - 1;
    const card = () => turn.querySelectorAll(".src")[at];
    mark.addEventListener("mouseenter", () => {
      const target = card();
      if (!target) return;
      target.classList.add("lit");
      const rect = mark.getBoundingClientRect();
      tip.replaceChildren(
        el("b", null, target.querySelector(".name").textContent),
        el("span", null, target.querySelector(".where").textContent),
      );
      tip.style.display = "block";
      tip.style.left = `${Math.min(rect.left, window.innerWidth - 260)}px`;
      tip.style.top = `${rect.bottom + 6}px`;
    });
    mark.addEventListener("mouseleave", () => {
      card()?.classList.remove("lit");
      tip.style.display = "none";
    });
    mark.addEventListener("click", () =>
      card()?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" }),
    );
  }
}

async function bearer() {
  const raw = who.value.trim();
  if (!raw) return null;
  if (!/^\d+$/.test(raw)) return raw;
  if (minted.seed === raw) return minted.token;
  const res = await fetch(`/admin/api/agent/token?user_id=${raw}`);
  if (!res.ok) throw new Error("토큰을 발급하지 못했습니다.");
  minted = { seed: raw, token: (await res.json()).data.token };
  return minted.token;
}

function coords() {
  if (!where.value) return null;
  const [lat, lng] = where.value.split(",").map(Number);
  return { lat, lng };
}

function context() {
  if (!lastSpots.length && !lastIntent) return null;
  const box = { spots: lastSpots.slice(0, 8).map((s) => ({ contentId: s.contentId, title: s.title })) };
  if (lastIntent) box.intent = lastIntent;
  if (focused) box.focusContentId = focused;
  return box;
}

function payloadOf({ message, intent, patch }) {
  const out = { clientRequestId: `console-${Date.now()}` };
  if (message) out.message = message;
  Object.assign(out, coords() || {});
  out.clientTime = new Date().toISOString();
  const box = context();
  if (box) out.context = box;
  if (intent) out.intent = intent;
  if (patch) out.patch = patch;
  if (multi.checked && history.length) out.history = history.slice(-8);
  return out;
}

function trim(intent) {
  const out = {};
  for (const [key, value] of Object.entries(intent || {})) {
    const empty =
      value == null || value === false || value === "" ||
      (Array.isArray(value) && !value.length) || value === "any" || value === "search";
    if (!empty) out[key] = value;
  }
  return out;
}

function report(rows) {
  stats.replaceChildren();
  for (const [key, value] of rows) {
    const row = el("div", "stat");
    row.appendChild(el("span", null, key));
    row.appendChild(el("code", null, value));
    stats.appendChild(row);
  }
}

function open(title, replay) {
  opening?.remove();
  const turn = el("section", "turn");
  turn.appendChild(el("h2", replay ? "replay" : null, title));
  const steps = el("div", "steps");
  const say = el("div", "say");
  turn.append(steps, say);
  thread.querySelector(".col").appendChild(turn);

  const dot = el("button", "rail-dot on");
  dot.type = "button";
  dot.title = title;
  for (const other of jump.querySelectorAll(".rail-dot")) other.classList.remove("on");
  dot.onclick = () => turn.scrollIntoView({ behavior: "smooth", block: "start" });
  jump.appendChild(dot);

  pinned = true;
  nudge();
  return { turn, steps, say, lines: [] };
}

function paintSteps(box, list) {
  box.replaceChildren();
  for (const step of list) {
    const row = el("div", `step${step.status === "run" ? " run" : ""}${step.failed ? " fail" : ""}`);
    row.appendChild(el("span", "mark"));
    row.appendChild(el("span", null, step.label));
    if (step.badge) row.appendChild(el("span", "count", step.badge));
    if (step.took != null) row.appendChild(el("span", "took", tookOf(step.took)));
    box.appendChild(row);
  }
}

function tookOf(ms) {
  return ms < 950 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}


function paintCards(turn, spots) {
  turn.querySelector(".label")?.remove();
  turn.querySelector(".sources")?.remove();
  turn.querySelector(".follow.anchors")?.remove();
  if (!spots.length) return;

  const head = el("div", "label", `근거 ${spots.length}곳 — 누르면 그 곳 기준으로 다시 물어봅니다`);
  const rail = el("div", "sources");
  spots.forEach((spot, index) => {
    const card = el("button", "src");
    card.type = "button";
    if (spot.imageUrl) {
      const frame = el("figure");
      const img = el("img");
      img.src = spot.imageUrl;
      img.alt = "";
      img.loading = "lazy";
      frame.appendChild(img);
      card.appendChild(frame);
    }
    const body = el("div", "body");
    body.appendChild(el("div", "idx", String(index + 1).padStart(2, "0")));
    body.appendChild(el("div", "name", spot.title));
    body.appendChild(el("div", "where", spot.regionLabel || ""));
    card.appendChild(body);
    card.onclick = () => choose(turn, spot, card);
    rail.appendChild(card);
  });
  turn.querySelector(".steps").after(head, rail);
}

function choose(turn, spot, node) {
  focused = spot.contentId;
  for (const other of turn.querySelectorAll(".src")) other.classList.remove("on");
  node.classList.add("on");
  turn.querySelector(".follow.anchors")?.remove();
  const bar = el("div", "follow anchors");
  for (const [action, label] of ANCHORS) {
    const chip = el("button", "chip ghost", label);
    chip.type = "button";
    chip.onclick = () => anchor({ contentId: spot.contentId, action }, `${spot.title} · ${label}`);
    bar.appendChild(chip);
  }
  turn.appendChild(bar);
  nudge();
}

function paintChips(turn, refinements) {
  turn.querySelector(".follow.chips")?.remove();
  if (!refinements?.length) return;
  const bar = el("div", "follow chips");
  for (const item of refinements) {
    const chip = el("button", "chip", item.label);
    chip.type = "button";
    chip.onclick = () => send({ intent: lastIntent, patch: item.patch, title: `조건 · ${item.label}` });
    bar.appendChild(chip);
  }
  turn.appendChild(bar);
}

function paintRefs(turn, items) {
  turn.querySelector(".refs")?.remove();
  if (!items?.length) return;
  const bar = el("div", "refs");
  bar.appendChild(el("span", "tag", "블로그"));
  for (const item of items.slice(0, 5)) {
    const shown = item.title.length > 24 ? `${item.title.slice(0, 24)}…` : item.title;
    if (item.url) {
      const link = el("a", null, shown);
      link.href = item.url;
      link.title = item.title;
      link.target = "_blank";
      link.rel = "noreferrer";
      bar.appendChild(link);
    } else {
      bar.appendChild(el("span", null, shown));
    }
  }
  turn.appendChild(bar);
}

function paintTail(turn, text, took) {
  turn.querySelector(".tail")?.remove();
  const bar = el("div", "tail");
  if (took != null) bar.appendChild(el("span", "took", tookOf(took)));
  const copy = el("button", "mini", "복사");
  copy.type = "button";
  copy.onclick = async () => {
    await navigator.clipboard.writeText(text);
    copy.textContent = "복사됨";
    setTimeout(() => (copy.textContent = "복사"), 1400);
  };
  bar.appendChild(copy);
  turn.querySelector(".say").after(bar);
}

function blame(turn, code, message) {
  const box = el("div", "bad");
  box.appendChild(el("code", null, code));
  box.appendChild(document.createTextNode(message || ""));
  turn.appendChild(box);
}

function lock(on) {
  busy = on;
  go.classList.toggle("stop", on);
  go.title = on ? "중단" : "보내기";
  go.replaceChildren(iconOf(on ? "stop" : "send"));
  if (!on) jumpDown.classList.remove("show");
}

function iconOf(kind) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", kind === "stop" ? "M7 7h10v10H7z" : "M5 12h14M13 6l6 6-6 6");
  svg.appendChild(path);
  return svg;
}

async function send({ message, intent, patch, title, file }) {
  if (busy) {
    abort?.abort();
    return;
  }
  lock(true);
  abort = new AbortController();
  const shown = title || message || "사진으로 찾기";
  const view = open(shown, Boolean(title));
  const payload = payloadOf({ message, intent, patch });
  sent.textContent = JSON.stringify(payload, null, 2);
  const started = performance.now();

  try {
    const headers = {};
    const token = await bearer();
    if (token) headers.Authorization = `Bearer ${token}`;

    let init;
    if (file) {
      const body = new FormData();
      body.append("photo", file);
      for (const [key, value] of Object.entries(payload)) {
        if (value == null) continue;
        body.append(key, typeof value === "object" ? JSON.stringify(value) : String(value));
      }
      init = { method: "POST", headers, body, signal: abort.signal };
    } else {
      init = {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abort.signal,
      };
    }

    const res = await fetch("/v1/agent/chat", init);
    if (!res.ok) {
      const envelope = await res.json().catch(() => null);
      blame(view.turn, envelope?.error?.code || `HTTP ${res.status}`, envelope?.error?.message);
      return;
    }
    await drain(res, view, shown, started);
  } catch (error) {
    if (error.name === "AbortError") blame(view.turn, "STOPPED", "중단했습니다.");
    else blame(view.turn, "CONSOLE", error.message);
  } finally {
    lock(false);
    abort = null;
    nudge();
  }
}

async function drain(res, view, shown, started) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const steps = [];
  let buffer = "";
  let text = "";
  let done = null;
  let queued = false;

  const flush = () => {
    queued = false;
    paintSay(view, text, true);
    nudge();
  };

  for (;;) {
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
      try {
        data = JSON.parse(raw);
      } catch {
        continue;
      }

      if (name === "step") {
        const at = steps.findIndex((s) => s.index === data.index);
        const now = performance.now();
        if (at < 0) {
          steps.push({ ...data, at: now });
        } else {
          const failed = (data.badge || "").includes("시간 초과");
          steps[at] = { ...steps[at], ...data, failed, took: now - steps[at].at };
        }
        paintSteps(view.steps, steps);
        nudge();
      } else if (name === "delta") {
        text += data.text;
        if (!queued) {
          queued = true;
          requestAnimationFrame(flush);
        }
      } else if (name === "cards") {
        lastSpots = data.spots || [];
        paintCards(view.turn, lastSpots);
        paintChips(view.turn, data.refinements);
        nudge();
      } else if (name === "sources") {
        paintRefs(view.turn, data.items);
      } else if (name === "done") {
        done = data;
      } else if (name === "error") {
        blame(view.turn, data.code, data.message);
      }
    }
  }

  if (!done) return;
  view.lines = [];
  view.say.replaceChildren();
  paintSay(view, done.answerText, false);
  lastSpots = done.spots || [];
  lastIntent = done.intent || null;
  focused = null;
  paintCards(view.turn, lastSpots);
  paintTail(view.turn, done.answerText, performance.now() - started);
  paintChips(view.turn, done.refinements);
  paintRefs(view.turn, done.sources);
  report([
    ["결과", `${done.spots.length}곳 · 전체 ${done.totalCount}`],
    ["소요", `${Math.round(performance.now() - started)}ms`],
    ["도구", `${steps.length}회`],
    ["intent", JSON.stringify(trim(done.intent))],
    ["trace", done.traceId || "–"],
  ]);
  history.push({ role: "user", text: shown });
  history.push({
    role: "assistant",
    text: done.answerText,
    spotIds: lastSpots.slice(0, 8).map((s) => s.contentId),
  });
}

async function anchor(target, title) {
  if (busy) return;
  lock(true);
  const view = open(title, true);
  const payload = { anchor: target, ...(coords() || {}) };
  const box = context();
  if (box) payload.context = box;
  sent.textContent = JSON.stringify(payload, null, 2);
  const started = performance.now();

  try {
    const headers = { "Content-Type": "application/json" };
    const token = await bearer();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch("/v1/agent/ask", { method: "POST", headers, body: JSON.stringify(payload) });
    const envelope = await res.json();
    if (!res.ok) {
      blame(view.turn, envelope?.error?.code || `HTTP ${res.status}`, envelope?.error?.message);
      return;
    }
    const data = envelope.data;
    paintSteps(view.steps, (data.steps || []).map((step, index) => ({ ...step, index, status: "done" })));
    const said = (data.answer || []).map((seg) => seg.text).join("");
    paintSay(view, said, false);
    lastSpots = data.spots || [];
    lastIntent = data.intent || null;
    paintCards(view.turn, lastSpots);
    paintTail(view.turn, said, performance.now() - started);
    paintChips(view.turn, data.refinements);
    report([
      ["결과", `${lastSpots.length}곳 · 전체 ${data.totalCount}`],
      ["소요", `${Math.round(performance.now() - started)}ms`],
      ["intent", JSON.stringify(trim(lastIntent))],
    ]);
  } catch (error) {
    blame(view.turn, "CONSOLE", error.message);
  } finally {
    lock(false);
    nudge();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy) {
    abort?.abort();
    return;
  }
  const message = ask.value.trim();
  const file = photo.files?.[0] || null;
  if (!message && !file) return;
  ask.value = "";
  ask.style.height = "auto";
  photo.value = "";
  clip.classList.remove("on");
  clipName.textContent = "";
  send({ message: message || null, file });
});

ask.addEventListener("input", () => {
  ask.style.height = "auto";
  ask.style.height = `${Math.min(ask.scrollHeight, 140)}px`;
});

ask.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

photo.addEventListener("change", () => {
  const file = photo.files?.[0];
  clip.classList.toggle("on", Boolean(file));
  clipName.textContent = file ? file.name : "";
});

document.getElementById("fresh").addEventListener("click", () => location.reload());

document.getElementById("peek").addEventListener("click", (event) => {
  inspector.classList.toggle("open");
  event.currentTarget.classList.toggle("on");
});

const seedBar = document.getElementById("seeds");
for (const seed of SEEDS) {
  const chip = el("button", "chip", seed);
  chip.type = "button";
  chip.onclick = () => send({ message: seed });
  seedBar.appendChild(chip);
}

fetch("/admin/api/agent/router")
  .then((res) => res.json())
  .then((body) => {
    document.getElementById("router").textContent = `router ${body.data.router}`;
  })
  .catch(() => {});
