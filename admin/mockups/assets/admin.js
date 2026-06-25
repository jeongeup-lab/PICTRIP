// PicTrip ADMIN — shared behavior + live fetch wiring

// ─── live clock ────────────────────────────────────────────────────────────
(function () {
  const el = document.getElementById("clock");
  if (!el) return;
  // Render in Asia/Seoul so the "KST" label is truthful regardless of the
  // operator's machine timezone.
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

// ─── HTML escaper ───────────────────────────────────────────────────────────
// Escape server-derived values before interpolating into innerHTML. The
// sync_runs table is externally owned (pipeline writes raw exception messages),
// so run.error etc. are untrusted → prevent stored-DOM-XSS.
const escapeHtml = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

// toast helper
function toast(msg, mono) {
  let t = document.querySelector(".toast");
  if (!t) {
    t = document.createElement("div");
    t.className = "toast";
    document.body.appendChild(t);
  }
  t.innerHTML = msg + (mono ? ` <span class="mono">${mono}</span>` : "");
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2600);
}

// ─── JSend fetch helper ─────────────────────────────────────────────────────
// Browser carries Basic-auth credentials automatically (same-origin session).
// Returns the `data` field of the JSend envelope.
// Throws on non-2xx or JSend error payload.
async function adminFetch(path) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText}`);
  }
  const json = await res.json();
  if (json.error) {
    throw new Error(json.error.message || JSON.stringify(json.error));
  }
  return json.data;
}

// ─── relative-time formatter ────────────────────────────────────────────────
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

// format absolute datetime as "MM-DD HH:MM"
function fmtDatetime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

// format duration seconds as "Xm Ys" or "X.Xs"
function fmtDuration(sec) {
  if (sec == null) return "—";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

// format uptime seconds as "Xd Xh" or "Xh Xm"
function fmtUptime(sec) {
  if (sec == null) return "—";
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

// ─── 수집 현황 (index.html) ─────────────────────────────────────────────────
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

  // ran-at
  const ranAtEl = document.getElementById("col-ran-at");
  const ranRelEl = document.getElementById("col-ran-rel");
  if (ranAtEl && ranRelEl) {
    const ts = run ? (run.finishedAt || run.ranAt) : null;
    ranAtEl.childNodes[0].textContent = ts ? fmtDatetime(ts) : "—";
    ranRelEl.textContent = ts ? relativeTime(ts) : "";
  }

  // api calls
  const apiEl = document.getElementById("col-api-calls");
  if (apiEl) apiEl.textContent = run ? (run.apiCalls != null ? run.apiCalls.toLocaleString("ko-KR") : "—") : "—";

  // changes
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

  // duration
  const durEl = document.getElementById("col-duration");
  if (durEl) durEl.textContent = run ? fmtDuration(run.durationSec) : "—";

  // status icon
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

  // footer
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

// ─── 수집 이력 (history.html) ───────────────────────────────────────────────
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

// log modal for history detail
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

// ─── 서비스 헬스 (health.html) ──────────────────────────────────────────────
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

  // API KPI
  const uptimeEl = document.getElementById("h-api-uptime");
  if (uptimeEl) uptimeEl.textContent = fmtUptime(h.api && h.api.uptimeSec);
  const p95El = document.getElementById("h-api-p95");
  if (p95El) p95El.textContent = h.api && h.api.p95Ms != null ? `p95 ${h.api.p95Ms.toFixed(0)}ms` : "p95 —";

  // DB KPI
  const dbPoolEl = document.getElementById("h-db-pool");
  if (dbPoolEl) {
    const inUse = h.db && h.db.poolInUse != null ? h.db.poolInUse : "—";
    const size = h.db && h.db.poolSize != null ? h.db.poolSize : "—";
    dbPoolEl.textContent = `${inUse} / ${size}`;
  }

  // Users KPI
  const usersTotalEl = document.getElementById("h-users-total");
  if (usersTotalEl) usersTotalEl.textContent = h.users && h.users.total != null ? h.users.total.toLocaleString("ko-KR") : "—";
  const usersActiveEl = document.getElementById("h-users-active");
  if (usersActiveEl) usersActiveEl.textContent = h.users && h.users.active != null ? `활성 ${h.users.active.toLocaleString("ko-KR")}` : "—";

  // API detail row
  const apiDetailEl = document.getElementById("h-api-detail");
  if (apiDetailEl) {
    const ver = h.api && h.api.version ? h.api.version : "—";
    const uptime = fmtUptime(h.api && h.api.uptimeSec);
    const p95 = h.api && h.api.p95Ms != null ? `p95 ${h.api.p95Ms.toFixed(0)}ms` : "p95 —";
    apiDetailEl.textContent = `${ver} · uptime ${uptime} · ${p95}`;
  }

  // DB detail row
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

  // Tunnel row
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

  // Users detail row
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

  // Users mini table
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

  // update probe pill timestamp
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

// ─── page init + auto-refresh ───────────────────────────────────────────────
let _refreshInterval = null;

function startRefresh(fn, intervalMs) {
  if (_refreshInterval) clearInterval(_refreshInterval);
  _refreshInterval = setInterval(() => {
    // pause when page is hidden
    if (!document.hidden) fn();
  }, intervalMs);
}

window.addEventListener("load", () => {
  // detect which page we are on and kick off the right fetch + refresh
  if (document.getElementById("collection-loading")) {
    loadCollection();
    startRefresh(loadCollection, 30000);
  } else if (document.getElementById("history-loading")) {
    loadHistory();
    startRefresh(loadHistory, 60000);
  } else if (document.getElementById("health-loading")) {
    loadHealth();
    startRefresh(loadHealth, 30000);
  }

  // animate coverage bars (used on other potential pages)
  document.querySelectorAll(".bar i[data-w]").forEach((el, i) => {
    setTimeout(() => { el.style.width = el.dataset.w + "%"; }, 200 + i * 80);
  });
});

// clear interval on page hide to be tidy
document.addEventListener("visibilitychange", () => {
  if (document.hidden && _refreshInterval) {
    clearInterval(_refreshInterval);
    _refreshInterval = null;
  } else if (!document.hidden) {
    // re-establish refresh when page becomes visible again
    if (document.getElementById("collection-loading") !== null || document.getElementById("collection-data") !== null) {
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
