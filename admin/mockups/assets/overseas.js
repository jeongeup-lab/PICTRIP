// PicTrip ADMIN — 게시물(해외 스팟) 숨김 관리 (live fetch wiring)
//
// 목록은 id 커서 페이지네이션(더 보기 append), 상단 검색은 이름(name_ko) substring.
// 각 행의 숨김/해제 버튼 → PUT /admin/api/overseas/{id}/visibility → 행 즉시 갱신.
// 숨김 처리는 앱 피드(/v1/feed)가 이미 적용하는 필터(is_hidden=false)와 동일 → 즉시 반영.
// 동적 마크업은 <template> 클론 + DOM 프로퍼티 대입(innerHTML에 서버 문자열 삽입 없음).
//
// API: GET /admin/api/overseas?q=&cursor=&limit=
//      PUT /admin/api/overseas/{id}/visibility  body {"isHidden": bool}

async function ovFetch(path, method, body) {
  const opts = { method: method || "GET", credentials: "same-origin" };
  if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401) {
    location.href = "/admin/login";
    throw new Error("세션이 만료되었습니다");
  }
  let json = null;
  try { json = await res.json(); } catch (_) { /* non-JSON */ }
  if (!res.ok || (json && json.error)) {
    const e = (json && json.error) || {};
    const err = new Error(e.message || `HTTP ${res.status} ${res.statusText}`);
    err.code = e.code || null;
    throw err;
  }
  return json ? json.data : null;
}

const OV = {
  q: "",
  cursor: null,
  loaded: 0,
  searchTimer: null,
  loading: false,
};

const el = (id) => document.getElementById(id);
const fmtNum = (n) => (n != null ? n.toLocaleString("ko-KR") : "—");

function showLoading() {
  el("ov-loading").style.display = "";
  el("ov-error").style.display = "none";
  el("ov-data").style.display = "none";
}
function showError(msg) {
  el("ov-loading").style.display = "none";
  el("ov-error").style.display = "";
  el("ov-data").style.display = "none";
  el("ov-error-msg").textContent = msg;
}
function showData() {
  el("ov-loading").style.display = "none";
  el("ov-error").style.display = "none";
  el("ov-data").style.display = "";
}

function applyRow(tr, item) {
  tr.dataset.id = item.id;
  const im = tr.querySelector(".ovim img");
  const ph = tr.querySelector(".ovim .phx");
  if (item.imageUrl) {
    im.src = item.imageUrl;
    im.hidden = false;
    ph.hidden = true;
    im.onerror = () => { im.hidden = true; ph.hidden = false; };
  } else {
    im.hidden = true;
    ph.hidden = false;
  }
  tr.querySelector("[data-name]").textContent = item.nameKo;
  tr.querySelector("[data-country]").textContent = item.countryNameKo;
  tr.querySelector("[data-fame]").textContent = fmtNum(item.fameScore);
  setRowStatus(tr, item.isHidden);
}

function setRowStatus(tr, hidden) {
  tr.dataset.hidden = hidden ? "1" : "0";
  tr.classList.toggle("is-hidden", hidden);
  const status = tr.querySelector("[data-status]");
  status.className = "chip " + (hidden ? "idle" : "ok");
  status.textContent = hidden ? "숨김" : "노출";
  const btn = tr.querySelector("[data-toggle]");
  btn.textContent = hidden ? "해제" : "숨김";
}

function appendRows(items) {
  const tpl = el("tpl-overseas-row");
  const rows = el("ov-rows");
  items.forEach((item) => {
    const frag = tpl.content.cloneNode(true);
    const tr = frag.querySelector("tr");
    applyRow(tr, item);
    tr.querySelector("[data-toggle]").addEventListener("click", () => onToggle(tr));
    rows.appendChild(tr);
  });
}

async function onToggle(tr) {
  const id = Number(tr.dataset.id);
  const next = tr.dataset.hidden !== "1";
  const btn = tr.querySelector("[data-toggle]");
  btn.disabled = true;
  try {
    const data = await ovFetch(`/admin/api/overseas/${id}/visibility`, "PUT", { isHidden: next });
    setRowStatus(tr, data.isHidden);
    toast(data.isHidden ? "게시물을 숨겼습니다" : "게시물 숨김을 해제했습니다");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function loadPage(reset) {
  if (OV.loading) return;
  OV.loading = true;
  if (reset) {
    OV.cursor = null;
    OV.loaded = 0;
    el("ov-rows").innerHTML = "";
    showLoading();
  }
  const params = new URLSearchParams({ limit: "50" });
  if (OV.q) params.set("q", OV.q);
  if (OV.cursor != null) params.set("cursor", String(OV.cursor));
  try {
    const data = await ovFetch(`/admin/api/overseas?${params.toString()}`);
    showData();
    appendRows(data.items);
    OV.loaded += data.items.length;
    OV.cursor = data.nextCursor;
    el("ov-empty").hidden = OV.loaded > 0;
    el("ov-more").hidden = data.nextCursor == null;
    el("ov-count").textContent = OV.loaded > 0 ? `${fmtNum(OV.loaded)}건 표시` : "";
    el("ov-caption").textContent = OV.q ? `검색 · ${OV.q}` : "페이지당 50건";
  } catch (err) {
    if (reset) showError(err.message);
    else toast(err.message);
  } finally {
    OV.loading = false;
  }
}

function onSearchInput(e) {
  clearTimeout(OV.searchTimer);
  const v = e.target.value.trim();
  OV.searchTimer = setTimeout(() => {
    OV.q = v;
    loadPage(true);
  }, 250);
}

window.addEventListener("load", () => {
  el("ov-search").addEventListener("input", onSearchInput);
  el("ov-more-btn").addEventListener("click", () => loadPage(false));
  el("ov-retry").addEventListener("click", () => loadPage(true));
  loadPage(true);
});
