
(function () {
  const el = document.getElementById("clock");
  if (!el) return;
  function tick() {
    const t = new Date().toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    el.textContent = `${t} KST`;
  }
  tick();
  setInterval(tick, 1000);
})();

// Escape untrusted sync_runs/error text before innerHTML (XSS).
const escapeHtml = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

function toast(msg, mono) {
  let t = document.querySelector(".toast");
  if (!t) {
    t = document.createElement("div");
    t.className = "toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  if (mono) {
    t.append(" ");
    const span = document.createElement("span");
    span.className = "mono";
    span.textContent = mono;
    t.append(span);
  }
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2600);
}

// JSend fetch: returns the data field, throws on non-2xx or error payload.
async function adminFetch(path) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (res.status === 401) {
    location.href = "/admin/login";
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText}`);
  }
  const json = await res.json();
  if (json.error) {
    throw new Error(json.error.message || JSON.stringify(json.error));
  }
  return json.data;
}

function relativeTime(isoStr) {
  if (!isoStr) return "";
  const then = new Date(isoStr);
  const diffSec = Math.floor((Date.now() - then.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}초 전`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}시간 ${diffMin % 60}분 전`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}일 전`;
}

function fmtDatetime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fmtDuration(sec) {
  if (sec == null) return "—";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

function fmtUptime(sec) {
  if (sec == null) return "—";
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function showCollectionLoading() {
  const l = document.getElementById("collection-loading");
  const e = document.getElementById("collection-error");
  const d = document.getElementById("collection-data");
  if (l) l.style.display = "";
  if (e) e.style.display = "none";
  if (d) d.style.display = "none";
}

function showCollectionError(msg) {
  const l = document.getElementById("collection-loading");
  const e = document.getElementById("collection-error");
  const d = document.getElementById("collection-data");
  if (l) l.style.display = "none";
  if (e) { e.style.display = ""; }
  if (d) d.style.display = "none";
  const em = document.getElementById("collection-error-msg");
  if (em) em.textContent = msg;
}

function renderCollection(data) {
  const l = document.getElementById("collection-loading");
  const e = document.getElementById("collection-error");
  const d = document.getElementById("collection-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "none";
  if (d) d.style.display = "";

  const run = data.source && data.source.lastRun;

  const ranAtEl = document.getElementById("col-ran-at");
  const ranRelEl = document.getElementById("col-ran-rel");
  if (ranAtEl && ranRelEl) {
    const ts = run ? (run.finishedAt || run.ranAt) : null;
    ranAtEl.childNodes[0].textContent = ts ? fmtDatetime(ts) : "—";
    ranRelEl.textContent = ts ? relativeTime(ts) : "";
  }

  const apiEl = document.getElementById("col-api-calls");
  if (apiEl) apiEl.textContent = run ? (run.apiCalls != null ? run.apiCalls.toLocaleString("ko-KR") : "—") : "—";

  const chEl = document.getElementById("col-changes");
  if (chEl) {
    if (run) {
      const ins = run.inserted != null ? run.inserted.toLocaleString("ko-KR") : "—";
      const upd = run.updated != null ? run.updated.toLocaleString("ko-KR") : "—";
      const del = run.softDeleted != null ? run.softDeleted.toLocaleString("ko-KR") : "—";
      chEl.textContent = `${ins} / ${upd} / ${del}`;
    } else {
      chEl.textContent = "—";
    }
  }

  const durEl = document.getElementById("col-duration");
  if (durEl) durEl.textContent = run ? fmtDuration(run.durationSec) : "—";

  const statusEl = document.getElementById("col-status-icon");
  if (statusEl) {
    const status = run ? run.status : null;
    if (status === "success") {
      statusEl.className = "status ok";
      statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg> 업데이트 완료`;
    } else if (status === "error") {
      statusEl.className = "status bad";
      statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg> 실패`;
    } else if (status === "running") {
      statusEl.className = "status";
      statusEl.style.color = "var(--warn)";
      statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg> 실행 중…`;
    } else {
      statusEl.className = "";
      statusEl.textContent = "—";
    }
  }

  const footEl = document.getElementById("col-footer");
  if (footEl) {
    const total = data.totalSpots != null ? data.totalSpots.toLocaleString("ko-KR") : "—";
    const next = data.nextScheduledAt ? fmtDatetime(data.nextScheduledAt) : "내일 04:00";
    footEl.textContent = `다음 자동 실행 · ${next} · 총 ${total} spots 수집됨`;
  }
}

async function loadCollection() {
  showCollectionLoading();
  try {
    const data = await adminFetch("/admin/api/collection");
    renderCollection(data);
  } catch (err) {
    showCollectionError(err.message);
  }
}

async function adminPost(path) {
  const res = await fetch(path, { method: "POST", credentials: "same-origin" });
  const json = await res.json().catch(() => ({}));
  if (res.status === 401) {
    location.href = "/admin/login";
  }
  if (!res.ok || (json && json.error)) {
    const msg = (json && json.error && json.error.message) || `HTTP ${res.status} ${res.statusText}`;
    throw new Error(msg);
  }
  return json.data;
}

let _triggerPoll = null;
// Safety cap: stop trigger polling after ~10 min so the button never sticks.
const _POLL_MAX_ATTEMPTS = 120;

function setTriggerBtn(disabled, label) {
  const btn = document.getElementById("col-trigger-btn");
  if (!btn) return;
  btn.disabled = disabled;
  if (label != null) btn.textContent = label;
}

function startTriggerPolling() {
  if (_triggerPoll) clearInterval(_triggerPoll);
  let _pollAttempts = 0;
  _triggerPoll = setInterval(async () => {
    if (document.hidden) return;
    _pollAttempts += 1;
    if (_pollAttempts > _POLL_MAX_ATTEMPTS) {
      clearInterval(_triggerPoll);
      _triggerPoll = null;
      setTriggerBtn(false, "수집 즉시 실행");
      toast("여전히 진행 중 — 수집 이력을 확인하세요");
      return;
    }
    try {
      const data = await adminFetch("/admin/api/collection");
      renderCollection(data);
      const run = data.source && data.source.lastRun;
      const status = run ? run.status : null;
      if (status !== "running") {
        clearInterval(_triggerPoll);
        _triggerPoll = null;
        setTriggerBtn(false, "수집 즉시 실행");
        toast(status === "error" ? "수집 실패" : "수집 완료");
      }
    } catch (_e) {
    }
  }, 5000);
}

async function onTriggerClick() {
  setTriggerBtn(true, "시작 중…");
  try {
    await adminPost("/admin/api/collection/trigger");
    toast("수집 시작됨");
    setTriggerBtn(true, "수집 중…");
    startTriggerPolling();
  } catch (err) {
    toast(err.message);
    setTriggerBtn(false, "수집 즉시 실행");
  }
}

function wireTriggerButton() {
  const btn = document.getElementById("col-trigger-btn");
  if (!btn) return;
  btn.disabled = false;
  btn.removeAttribute("title");
  btn.textContent = "수집 즉시 실행";
  btn.addEventListener("click", onTriggerClick);
}

// --- 임베딩 현황 (collection/embedding are separate steps) --------------------
function showEmbeddingLoading() {
  const l = document.getElementById("embedding-loading");
  const e = document.getElementById("embedding-error");
  const d = document.getElementById("embedding-data");
  if (l) l.style.display = "";
  if (e) e.style.display = "none";
  if (d) d.style.display = "none";
}

function showEmbeddingError(msg) {
  const l = document.getElementById("embedding-loading");
  const e = document.getElementById("embedding-error");
  const d = document.getElementById("embedding-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "";
  if (d) d.style.display = "none";
  const em = document.getElementById("embedding-error-msg");
  if (em) em.textContent = msg;
}

const _EMB_REASON_KO = { download_failed: "다운로드실패", clip_error: "이미지오류" };

function renderEmbedding(d) {
  const l = document.getElementById("embedding-loading");
  const e = document.getElementById("embedding-error");
  const dd = document.getElementById("embedding-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "none";
  if (dd) dd.style.display = "";

  const fmt = (n) => (n != null ? n.toLocaleString("ko-KR") : "—");
  const rec = d.recent || {};

  const recentEl = document.getElementById("emb-recent");
  if (recentEl) recentEl.childNodes[0].textContent = `${fmt(rec.target)}건`;
  const recentDetailEl = document.getElementById("emb-recent-detail");
  if (recentDetailEl) {
    const done = rec.embedded != null ? fmt(rec.embedded) : "—";
    const out = rec.outstanding != null ? fmt(rec.outstanding) : "—";
    recentDetailEl.textContent = `완료 ${done} · 미완료 ${out}`;
  }

  const failedEl = document.getElementById("emb-failed");
  if (failedEl) failedEl.childNodes[0].textContent = fmt(d.failed);
  const reasonsEl = document.getElementById("emb-failed-reasons");
  if (reasonsEl) {
    const by = d.failuresByReason || {};
    const parts = Object.keys(by).map((k) => `${_EMB_REASON_KO[k] || k} ${by[k]}`);
    reasonsEl.textContent = parts.join(" · ");
  }

  const backlogEl = document.getElementById("emb-backlog");
  if (backlogEl) backlogEl.childNodes[0].textContent = fmt(d.missing);
  const lastEl = document.getElementById("emb-last");
  if (lastEl) lastEl.textContent = d.lastComputedAt ? `최근 ${relativeTime(d.lastComputedAt)}` : "기록 없음";

  const statusEl = document.getElementById("emb-status-icon");
  if (statusEl) {
    if (d.running) {
      statusEl.className = "status";
      statusEl.style.color = "var(--warn)";
      statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg> 임베딩 중…`;
    } else if (d.missing === 0) {
      statusEl.className = "status ok";
      statusEl.style.color = "";
      statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg> 전체 완료`;
    } else {
      statusEl.className = "status";
      statusEl.style.color = "";
      statusEl.textContent = "";
    }
  }

  setEmbButtons(d.running, d.failed, d.missing);

  const footEl = document.getElementById("emb-footer");
  if (footEl) {
    const pct = d.withImage > 0 ? Math.round((d.embedded / d.withImage) * 100) : 0;
    footEl.textContent = `커버리지 ${fmt(d.embedded)} / ${fmt(d.withImage)} 이미지보유 (${pct}%) · 미임베딩 ${fmt(d.missing)} (대기 ${fmt(d.pending)} · 실패 ${fmt(d.failed)})`;
  }
}

function setEmbButtons(running, failed, missing) {
  const retry = document.getElementById("emb-retry-btn");
  const all = document.getElementById("emb-all-btn");
  if (retry) {
    retry.disabled = !!running || !failed;
    retry.textContent = failed ? `실패분 재임베딩 ${failed.toLocaleString("ko-KR")}` : "실패분 재임베딩";
  }
  if (all) {
    all.disabled = !!running || !missing;
    all.textContent = running ? "임베딩 중…" : "전체 처리";
  }
}

async function loadEmbedding() {
  // Only flash the spinner on the first load; auto-refresh re-renders in place.
  const dataEl = document.getElementById("embedding-data");
  if (!dataEl || dataEl.style.display === "none") showEmbeddingLoading();
  try {
    const data = await adminFetch("/admin/api/embedding");
    renderEmbedding(data);
    if (data.running) startEmbeddingPolling();
  } catch (err) {
    if (!dataEl || dataEl.style.display === "none") showEmbeddingError(err.message);
  }
}

let _embPoll = null;
const _EMB_POLL_MAX = 240; // ~20 min safety cap (5s interval)

function startEmbeddingPolling() {
  if (_embPoll) return;
  let attempts = 0;
  _embPoll = setInterval(async () => {
    if (document.hidden) return;
    attempts += 1;
    if (attempts > _EMB_POLL_MAX) {
      clearInterval(_embPoll);
      _embPoll = null;
      return;
    }
    try {
      const data = await adminFetch("/admin/api/embedding");
      renderEmbedding(data);
      if (!data.running) {
        clearInterval(_embPoll);
        _embPoll = null;
        toast("임베딩 완료");
      }
    } catch (_e) {}
  }, 5000);
}

async function onEmbedTrigger(scope) {
  setEmbButtons(true, 0, 0);
  try {
    await adminPost(`/admin/api/embedding/trigger?scope=${scope}`);
    toast("임베딩 시작됨");
    startEmbeddingPolling();
  } catch (err) {
    toast(err.message);
    loadEmbedding();
  }
}

function wireEmbeddingButtons() {
  const retry = document.getElementById("emb-retry-btn");
  if (retry) retry.addEventListener("click", () => onEmbedTrigger("failed"));
  const all = document.getElementById("emb-all-btn");
  if (all) all.addEventListener("click", () => onEmbedTrigger("missing"));
}

function showHistoryLoading() {
  const l = document.getElementById("history-loading");
  const e = document.getElementById("history-error");
  const d = document.getElementById("history-data");
  if (l) l.style.display = "";
  if (e) e.style.display = "none";
  if (d) d.style.display = "none";
}

function showHistoryError(msg) {
  const l = document.getElementById("history-loading");
  const e = document.getElementById("history-error");
  const d = document.getElementById("history-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "";
  if (d) d.style.display = "none";
  const em = document.getElementById("history-error-msg");
  if (em) em.textContent = msg;
}

function renderHistory(data) {
  const l = document.getElementById("history-loading");
  const e = document.getElementById("history-error");
  const d = document.getElementById("history-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "none";
  if (d) d.style.display = "";

  const rowsEl = document.getElementById("history-rows");
  if (!rowsEl || !data.days) return;

  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  rowsEl.innerHTML = "";
  data.days.forEach((day) => {
    const isToday = day.date === today;
    const isYesterday = day.date === yesterday;
    const hasFail = day.error > 0;
    const hasRunning = day.running > 0;

    const row = document.createElement("div");
    row.className = "date-row" + (hasFail ? " fail" : "");
    row.dataset.date = day.date;

    let dateLabel = "";
    if (isToday) dateLabel = `<small>오늘</small>`;
    else if (isYesterday) dateLabel = `<small>어제</small>`;

    let chips = "";
    if (day.success > 0) chips += `<span class="chip ok">성공 ${day.success}</span> `;
    if (day.error > 0) chips += `<span class="chip bad">실패 ${day.error}</span> `;
    if (day.running > 0) chips += `<span class="chip warn">실행 중 ${day.running}</span>`;

    const retryLabel = day.runs > 1 ? " · 재시도" : "";
    const runLabel = `${day.runs} run${day.runs !== 1 ? "s" : ""}${retryLabel}`;

    row.innerHTML = `
      <div class="date">${escapeHtml(day.date)}${dateLabel}</div>
      <div class="counts">${chips}</div>
      <div class="runs">${runLabel}</div>
      <span class="chev">›</span>
    `;
    row.addEventListener("click", () => openHistoryDetail(day.date));
    rowsEl.appendChild(row);
  });
}

async function loadHistory() {
  showHistoryLoading();
  try {
    const data = await adminFetch("/admin/api/history?days=7");
    renderHistory(data);
  } catch (err) {
    showHistoryError(err.message);
  }
}

function openHistoryDetail(date) {
  const bg = document.getElementById("logmodal");
  if (!bg) return;

  const titleEl = document.getElementById("modal-title");
  const loadingEl = document.getElementById("modal-loading");
  const errorEl = document.getElementById("modal-error");
  const contentEl = document.getElementById("modal-content");
  const logEl = document.getElementById("modal-log");

  if (titleEl) titleEl.textContent = `${date} 수집 로그`;
  if (loadingEl) loadingEl.style.display = "";
  if (errorEl) errorEl.style.display = "none";
  if (contentEl) contentEl.style.display = "none";

  bg.classList.add("show");

  adminFetch(`/admin/api/history/${date}`)
    .then((data) => {
      if (loadingEl) loadingEl.style.display = "none";
      if (contentEl) contentEl.style.display = "";
      if (logEl) {
        if (!data.runs || data.runs.length === 0) {
          logEl.innerHTML = `<span class="dim2">이 날짜에 수집 기록이 없습니다.</span>`;
        } else {
          logEl.innerHTML = data.runs.map((run, i) => {
            const statusClass = run.status === "success" ? "ok2" : run.status === "error" ? "bad2" : "warn2";
            const dur = fmtDuration(run.durationSec);
            const ins = run.inserted != null ? run.inserted.toLocaleString("ko-KR") : "—";
            const upd = run.updated != null ? run.updated.toLocaleString("ko-KR") : "—";
            const del = run.softDeleted != null ? run.softDeleted.toLocaleString("ko-KR") : "—";
            const started = run.startedAt ? fmtDatetime(run.startedAt) : "—";
            const statusText = escapeHtml((run.status || "—").toUpperCase());
            let lines = [
              `<span class="dim2">── run #${escapeHtml(run.id)} · ${escapeHtml(run.mode || "—")} · ${started} ──</span>`,
              `<span class="dim2">API 호출:</span> ${run.apiCalls != null ? run.apiCalls.toLocaleString("ko-KR") : "—"} &nbsp; 소요: ${dur}`,
              `<span class="dim2">변경:</span> +${ins} 추가 · ${upd} 수정 · ${del} 숨김`,
              `<span class="${statusClass}">상태: ${statusText}</span>`,
            ];
            if (run.error) {
              lines.push(`<span class="bad2">오류: ${escapeHtml(run.error)}</span>`);
            }
            return lines.join("\n");
          }).join("\n\n");
        }
      }
    })
    .catch((err) => {
      if (loadingEl) loadingEl.style.display = "none";
      if (errorEl) {
        errorEl.style.display = "";
        const emEl = document.getElementById("modal-error-msg");
        if (emEl) emEl.textContent = err.message;
      }
    });
}

function closeLog() {
  const bg = document.getElementById("logmodal");
  if (bg) bg.classList.remove("show");
}

(function () {
  const bg = document.getElementById("logmodal");
  if (!bg) return;
  bg.addEventListener("click", (e) => { if (e.target === bg) closeLog(); });
  const xBtn = bg.querySelector(".x");
  if (xBtn) xBtn.addEventListener("click", closeLog);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeLog(); });
})();

function showHealthLoading() {
  const l = document.getElementById("health-loading");
  const e = document.getElementById("health-error");
  const d = document.getElementById("health-data");
  if (l) l.style.display = "";
  if (e) e.style.display = "none";
  if (d) d.style.display = "none";
}

function showHealthError(msg) {
  const l = document.getElementById("health-loading");
  const e = document.getElementById("health-error");
  const d = document.getElementById("health-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "";
  if (d) d.style.display = "none";
  const em = document.getElementById("health-error-msg");
  if (em) em.textContent = msg;
}

function renderHealth(h) {
  const l = document.getElementById("health-loading");
  const e = document.getElementById("health-error");
  const d = document.getElementById("health-data");
  if (l) l.style.display = "none";
  if (e) e.style.display = "none";
  if (d) d.style.display = "";

  const uptimeEl = document.getElementById("h-api-uptime");
  if (uptimeEl) uptimeEl.textContent = fmtUptime(h.api && h.api.uptimeSec);
  const p95El = document.getElementById("h-api-p95");
  if (p95El) p95El.textContent = h.api && h.api.p95Ms != null ? `p95 ${h.api.p95Ms.toFixed(0)}ms` : "p95 —";

  const dbPoolEl = document.getElementById("h-db-pool");
  if (dbPoolEl) {
    const inUse = h.db && h.db.poolInUse != null ? h.db.poolInUse : "—";
    const size = h.db && h.db.poolSize != null ? h.db.poolSize : "—";
    dbPoolEl.textContent = `${inUse} / ${size}`;
  }

  const usersTotalEl = document.getElementById("h-users-total");
  if (usersTotalEl) usersTotalEl.textContent = h.users && h.users.total != null ? h.users.total.toLocaleString("ko-KR") : "—";
  const usersActiveEl = document.getElementById("h-users-active");
  if (usersActiveEl) usersActiveEl.textContent = h.users && h.users.active != null ? `활성 ${h.users.active.toLocaleString("ko-KR")}` : "—";

  const apiDetailEl = document.getElementById("h-api-detail");
  if (apiDetailEl) {
    const ver = h.api && h.api.version ? h.api.version : "—";
    const uptime = fmtUptime(h.api && h.api.uptimeSec);
    const p95 = h.api && h.api.p95Ms != null ? `p95 ${h.api.p95Ms.toFixed(0)}ms` : "p95 —";
    apiDetailEl.textContent = `${ver} · uptime ${uptime} · ${p95}`;
  }

  const dbDetailEl = document.getElementById("h-db-detail");
  const dbReadingEl = document.getElementById("h-db-reading");
  if (dbDetailEl) {
    const spots = h.db && h.db.spots != null ? h.db.spots.toLocaleString("ko-KR") : "—";
    const inUse = h.db && h.db.poolInUse != null ? h.db.poolInUse : "—";
    const size = h.db && h.db.poolSize != null ? h.db.poolSize : "—";
    dbDetailEl.textContent = `CT110 · pool ${inUse}/${size} · ${spots} spots`;
  }
  if (dbReadingEl) {
    if (h.db && h.db.ok) {
      dbReadingEl.innerHTML = `<span class="chip ok">connected</span>`;
    } else {
      dbReadingEl.innerHTML = `<span class="chip bad">error</span>`;
    }
    const svcEl = document.getElementById("h-db-svc");
    if (svcEl) {
      const dotClass = h.db && h.db.ok ? "ok" : "bad";
      svcEl.innerHTML = `<span class="dot ${dotClass}"></span> PostgreSQL`;
    }
  }

  const tunnelDetailEl = document.getElementById("h-tunnel-detail");
  const tunnelReadingEl = document.getElementById("h-tunnel-reading");
  const tunnelSvcEl = document.getElementById("h-tunnel-svc");
  const tunnel = h.tunnel;
  if (tunnelDetailEl) {
    tunnelDetailEl.textContent = tunnel && tunnel.detail ? tunnel.detail : "미구현 (차기)";
  }
  if (tunnelReadingEl) {
    if (tunnel == null || tunnel.ok == null) {
      tunnelReadingEl.innerHTML = `<span class="chip idle">—</span>`;
    } else if (tunnel.ok) {
      tunnelReadingEl.innerHTML = `<span class="chip ok">ok</span>`;
    } else {
      tunnelReadingEl.innerHTML = `<span class="chip bad">error</span>`;
    }
  }
  if (tunnelSvcEl) {
    const dotClass = tunnel == null || tunnel.ok == null ? "warn" : tunnel.ok ? "ok" : "bad";
    tunnelSvcEl.innerHTML = `<span class="dot ${dotClass}"></span> Cloudflare 터널`;
  }

  const usersDetailEl = document.getElementById("h-users-detail");
  const usersReadingEl = document.getElementById("h-users-reading");
  if (usersDetailEl && h.users) {
    const total = h.users.total != null ? h.users.total.toLocaleString("ko-KR") : "—";
    const del30d = h.users.deleted30d != null ? h.users.deleted30d.toLocaleString("ko-KR") : "—";
    usersDetailEl.textContent = `${total} 가입 · ${del30d} 탈퇴(30d)`;
  }
  if (usersReadingEl && h.users) {
    const active = h.users.active != null ? h.users.active.toLocaleString("ko-KR") : "—";
    usersReadingEl.textContent = `${active} 활성`;
  }

  const uTotalEl = document.getElementById("h-u-total");
  const uActiveEl = document.getElementById("h-u-active");
  const uNew7dEl = document.getElementById("h-u-new7d");
  const uDelEl = document.getElementById("h-u-deleted30d");
  const uKakaoEl = document.getElementById("h-u-kakao");
  if (h.users) {
    if (uTotalEl) uTotalEl.textContent = h.users.total != null ? h.users.total.toLocaleString("ko-KR") : "—";
    if (uActiveEl) uActiveEl.textContent = h.users.active != null ? h.users.active.toLocaleString("ko-KR") : "—";
    if (uNew7dEl) uNew7dEl.textContent = h.users.new7d != null ? `+${h.users.new7d.toLocaleString("ko-KR")}` : "—";
    if (uDelEl) uDelEl.textContent = h.users.deleted30d != null ? h.users.deleted30d.toLocaleString("ko-KR") : "—";
    if (uKakaoEl) uKakaoEl.textContent = h.users.kakao != null ? h.users.kakao.toLocaleString("ko-KR") : "—";
  }

  const pillEl = document.getElementById("health-probe-pill");
  if (pillEl) {
    const dbOk = h.db && h.db.ok;
    pillEl.innerHTML = `<span class="dot ${dbOk ? "live" : "bad"}"></span> probe · 방금`;
  }
}

async function loadHealth() {
  showHealthLoading();
  try {
    const data = await adminFetch("/admin/api/health");
    renderHealth(data);
  } catch (err) {
    showHealthError(err.message);
  }
}

function ovSet(id, txt) { const e = document.getElementById(id); if (e) e.textContent = txt; }
function ovHtml(id, html) { const e = document.getElementById(id); if (e) e.innerHTML = html; }

async function loadOverviewCollection() {
  try {
    const data = await adminFetch("/admin/api/collection");
    renderCollection(data);
    ovSet("ov-total", data.totalSpots != null ? data.totalSpots.toLocaleString("ko-KR") : "—");
    const run = data.source && data.source.lastRun;
    const status = run ? run.status : null;
    const label = status === "success" ? "성공" : status === "error" ? "실패" : status === "running" ? "실행 중" : "—";
    ovSet("ov-laststatus", label);
    const lsEl = document.getElementById("ov-laststatus");
    if (lsEl)
      lsEl.style.color =
        status === "success" ? "var(--ok)" : status === "error" ? "var(--bad)" : status === "running" ? "var(--warn)" : "";
    if (run) {
      const ts = run.finishedAt || run.ranAt;
      ovSet("ov-lastrun-meta", `${fmtDuration(run.durationSec)} · ${ts ? relativeTime(ts) : ""}`.trim());
    } else {
      ovSet("ov-lastrun-meta", "기록 없음");
    }
  } catch (err) {
    showCollectionError(err.message);
    ovSet("ov-total", "—"); ovSet("ov-laststatus", "오류"); ovSet("ov-lastrun-meta", err.message);
  }
}

async function loadOverviewHealth() {
  try {
    const h = await adminFetch("/admin/api/health");
    if (h.db) {
      const inUse = h.db.poolInUse != null ? h.db.poolInUse : "—";
      const size = h.db.poolSize != null ? h.db.poolSize : "—";
      ovHtml("ov-dbpool", `${inUse}<small> / ${size}</small>`);
    }
    if (h.users) {
      ovSet("ov-users", h.users.total != null ? h.users.total.toLocaleString("ko-KR") : "—");
      ovHtml("ov-users-new", h.users.new7d != null ? `<b>+${h.users.new7d.toLocaleString("ko-KR")}</b> 신규 7일` : "—");
    }
    const ver = h.api && h.api.version ? h.api.version : "—";
    ovSet("ov-h-api-detail", `${ver} · uptime ${fmtUptime(h.api && h.api.uptimeSec)}`);
    ovHtml("ov-h-api-reading", `<span class="chip ok">200 OK</span>`);

    const dbOk = h.db && h.db.ok;
    const spots = h.db && h.db.spots != null ? h.db.spots.toLocaleString("ko-KR") : "—";
    const inUse = h.db && h.db.poolInUse != null ? h.db.poolInUse : "—";
    const size = h.db && h.db.poolSize != null ? h.db.poolSize : "—";
    ovSet("ov-h-db-detail", `CT110 · pool ${inUse}/${size} · ${spots} spots`);
    ovHtml("ov-h-db-reading", dbOk ? `<span class="chip ok">connected</span>` : `<span class="chip bad">error</span>`);
    ovHtml("ov-h-db-svc", `<span class="dot ${dbOk ? "ok" : "bad"}"></span> PostgreSQL`);

    const tunnel = h.tunnel;
    ovSet("ov-h-tunnel-detail", tunnel && tunnel.detail ? tunnel.detail : "미구현 (차기)");
    if (tunnel == null || tunnel.ok == null) {
      ovHtml("ov-h-tunnel-reading", `<span class="chip idle">—</span>`);
      ovHtml("ov-h-tunnel-svc", `<span class="dot warn"></span> Cloudflare 터널`);
    } else {
      ovHtml("ov-h-tunnel-reading", tunnel.ok ? `<span class="chip ok">ok</span>` : `<span class="chip bad">error</span>`);
      ovHtml("ov-h-tunnel-svc", `<span class="dot ${tunnel.ok ? "ok" : "bad"}"></span> Cloudflare 터널`);
    }

    if (h.users) {
      const total = h.users.total != null ? h.users.total.toLocaleString("ko-KR") : "—";
      const del30d = h.users.deleted30d != null ? h.users.deleted30d.toLocaleString("ko-KR") : "—";
      const active = h.users.active != null ? h.users.active.toLocaleString("ko-KR") : "—";
      ovSet("ov-h-users-detail", `${total} 가입 · ${del30d} 탈퇴(30d)`);
      ovSet("ov-h-users-reading", `${active} 활성`);
    }
  } catch (err) {
    ovHtml("ov-h-api-reading", `<span class="chip bad">probe 실패</span>`);
    ovSet("ov-h-api-detail", err.message);
  }
}

async function loadOverviewHistory() {
  const el = document.getElementById("ov-hist");
  if (!el) return;
  try {
    const data = await adminFetch("/admin/api/history?days=14");
    const days = (data.days || []).slice().sort((a, b) => (a.date < b.date ? -1 : 1));
    if (days.length === 0) {
      el.innerHTML = `<div class="col" style="justify-content:center"><span style="color:var(--ink-3);font-size:12px">기록 없음</span></div>`;
      return;
    }
    const maxRuns = Math.max(1, ...days.map((d) => d.runs || 0));
    const today = new Date().toISOString().slice(0, 10);
    el.innerHTML = days
      .map((d) => {
        const fail = d.error > 0;
        const pct = Math.round(30 + ((d.runs || 0) / maxRuns) * 70);
        const md = escapeHtml(d.date.slice(5));
        const cls = `col${fail ? " fail" : ""}${d.date === today ? " today" : ""}`;
        return `<div class="${cls}" title="${escapeHtml(d.date)} · 성공 ${d.success} / 실패 ${d.error}"><div class="stack" style="height:${pct}%"><div class="seg ins" style="height:100%"></div></div><div class="xlabel">${md}</div></div>`;
      })
      .join("");
  } catch (err) {
    el.innerHTML = `<div class="col" style="justify-content:center"><span style="color:var(--bad);font-size:12px">${escapeHtml(err.message)}</span></div>`;
  }
}

async function loadOverviewCuration() {
  const el = document.getElementById("ov-curation");
  if (!el) return;
  try {
    const data = await adminFetch("/admin/api/curations");
    const heroes = (data.heroes || []).slice(0, 4);
    const railCount = (data.rails || []).length;
    if (heroes.length === 0) {
      el.innerHTML = `<span style="color:var(--ink-3);font-size:12px">큐레이션 없음</span>`;
    } else {
      el.innerHTML = heroes
        .map((it, i) => {
          const url = it.coverUrl ? escapeHtml(it.coverUrl) : "";
          const pubColor = it.isPublished ? "var(--ok)" : "var(--warn)";
          const num = String(i + 1).padStart(2, "0");
          return `<div style="flex:1;position:relative;aspect-ratio:4/5;border:2px solid var(--ink);border-radius:4px;overflow:hidden;background:var(--surface-2)">${url ? `<img src="${url}" alt="" style="width:100%;height:100%;object-fit:cover">` : ""}<span style="position:absolute;top:0;left:0;background:var(--accent);color:#fff;font-family:var(--mono);font-size:10px;font-weight:700;padding:2px 7px">${num}</span><span style="position:absolute;left:0;right:0;bottom:0;background:var(--ink);color:var(--surface);font-size:12px;font-weight:700;padding:5px 8px;display:flex;justify-content:space-between;align-items:center">${escapeHtml(it.title || "—")}<span style="width:8px;height:8px;border-radius:2px;background:${pubColor};flex:none"></span></span></div>`;
        })
        .join("");
    }
    ovSet("ov-curation-meta", `히어로 ${heroes.length} · 무드 레일 ${railCount}`);
  } catch (err) {
    el.innerHTML = `<span style="color:var(--bad);font-size:12px">${escapeHtml(err.message)}</span>`;
  }
}

// Overview aggregates read-only endpoints; each section fails independently.
function loadOverview() {
  loadOverviewCollection();
  loadEmbedding();
  loadOverviewHealth();
  loadOverviewHistory();
  loadOverviewCuration();
}

let _refreshInterval = null;

function startRefresh(fn, intervalMs) {
  if (_refreshInterval) clearInterval(_refreshInterval);
  _refreshInterval = setInterval(() => {
    if (!document.hidden) fn();
  }, intervalMs);
}

// Detect page via a marker element, then load + auto-refresh.
window.addEventListener("load", () => {
  if (document.getElementById("overview-page")) {
    loadOverview();
    wireTriggerButton();
    wireEmbeddingButtons();
    startRefresh(loadOverview, 30000);
  } else if (document.getElementById("collection-loading")) {
    loadCollection();
    wireTriggerButton();
    startRefresh(loadCollection, 30000);
  } else if (document.getElementById("history-loading")) {
    loadHistory();
    startRefresh(loadHistory, 60000);
  } else if (document.getElementById("health-loading")) {
    loadHealth();
    startRefresh(loadHealth, 30000);
  }

  document.querySelectorAll(".bar i[data-w]").forEach((el, i) => {
    setTimeout(() => { el.style.width = el.dataset.w + "%"; }, 200 + i * 80);
  });
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden && _refreshInterval) {
    clearInterval(_refreshInterval);
    _refreshInterval = null;
  } else if (!document.hidden) {
    if (document.getElementById("overview-page") !== null) {
      loadOverview();
      startRefresh(loadOverview, 30000);
    } else if (document.getElementById("collection-loading") !== null || document.getElementById("collection-data") !== null) {
      loadCollection();
      startRefresh(loadCollection, 30000);
    } else if (document.getElementById("history-loading") !== null || document.getElementById("history-data") !== null) {
      loadHistory();
      startRefresh(loadHistory, 60000);
    } else if (document.getElementById("health-loading") !== null || document.getElementById("health-data") !== null) {
      loadHealth();
      startRefresh(loadHealth, 30000);
    }
  }
});
