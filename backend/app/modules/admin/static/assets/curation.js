// PicTrip ADMIN — 홈 큐레이션 편성 보드 (live fetch wiring)
//
// 보드가 곧 미리보기: 히어로 6장은 앱 홈과 동일 렌더의 카드 갤러리, 무드 레일은
// 와이드 로우. 카드 클릭 → 우측 슬라이드오버에서 카피·표지·손픽·발행·순서 편집.
// 모든 동적 마크업은 <template> 클론 + DOM 프로퍼티 대입(innerHTML에 서버 문자열
// 삽입 없음 → XSS/CSS-injection 표면 제거). 공용 헬퍼(adminFetch)는 admin.js.
//
// API: GET /admin/api/curations · GET/PUT /admin/api/curations/{id}
//      PUT /admin/api/curations/{id}/spots · GET /admin/api/curations/{id}/preview
//      GET /admin/api/spots/search?q=&region=   (region = ldong_regn_cd)

// ─── fetch (JSend, 세션 만료 시 로그인으로) ──────────────────────────────────
async function cuFetch(path, method, body) {
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
    err.details = e.details || null;
    err.status = res.status;
    throw err;
  }
  return json ? json.data : null;
}

// ─── state ───────────────────────────────────────────────────────────────────
const CU = {
  hero: [], rail: [], editorial: [],
  open: null,          // 슬라이드오버에 열린 item
  busy: false,
  pickerMode: null,    // 'picks' | 'cover'
  searchTimer: null, searchSeq: 0,
  dragging: null,      // 보드 카드 드래그 중인 item
};
const qs = (id) => document.getElementById(id);
const KIND_LABEL = { hero: "지역 히어로", rail: "무드 레일", editorial: "에디토리얼" };
const groupOf = (it) => CU[it.kind];
const allItems = () => [...CU.hero, ...CU.rail, ...CU.editorial];
const dirtyItems = () => allItems().filter((it) => it.dirty);

function mkItem(d, kind) {
  return {
    id: d.id, type: d.type, kind, slug: d.slug || "", position: d.position || 0,
    isPublished: !!d.isPublished, title: d.title || "", subtitle: d.subtitle || "",
    lead: "", intro: "",
    cover: { contentId: null, name: "", imageUrl: d.coverUrl || null },
    picks: [], previewSpots: null,
    detailLoaded: false, dirty: false, picksDirty: false, savedAt: null,
  };
}
function applyDetail(it, d) {
  it.title = d.title || ""; it.subtitle = d.subtitle || "";
  it.lead = d.lead || ""; it.intro = d.intro || "";
  it.isPublished = !!d.isPublished; it.position = d.position || 0; it.slug = d.slug || it.slug;
  it.cover = d.coverSpot
    ? { contentId: d.coverSpot.contentId, name: d.coverSpot.name || "", imageUrl: d.coverSpot.imageUrl || null }
    : { contentId: null, name: "", imageUrl: it.cover.imageUrl || null };
  it.picks = (d.handpicks || []).map((h) => ({
    contentId: h.contentId, name: h.name || "", sub: h.category || "스팟", imageUrl: h.imageUrl || null,
  }));
  it.detailLoaded = true;
}
async function ensureDetail(it) {
  if (!it.detailLoaded) applyDetail(it, await cuFetch(`/admin/api/curations/${it.id}`));
}
async function ensurePreview(it) {
  if (it.previewSpots !== null) return;
  try {
    const d = await cuFetch(`/admin/api/curations/${it.id}/preview`);
    it.previewSpots = (d.spots || []).map((s) => ({
      contentId: s.contentId, name: s.name || "", sub: s.category || "스팟", imageUrl: s.imageUrl || null,
    }));
  } catch (_) { it.previewSpots = []; }
}
async function refreshPreview(it) { it.previewSpots = null; await ensurePreview(it); }
// 앱이 실제 표시할 스팟: 손픽(로컬 편집 반영) 있으면 손픽, 없으면 자동충전 풀
function displaySpots(it) { return it.picks.length ? it.picks : it.previewSpots || []; }
function coverImageUrl(it) { return it.cover.imageUrl || (displaySpots(it)[0] || {}).imageUrl || null; }

// ─── 공용 렌더 유틸 (템플릿 클론 + 프로퍼티 대입만) ──────────────────────────
function setImg(scope, url) {
  const img = scope.querySelector("img");
  const ph = scope.querySelector(".phx");
  if (url) { img.src = url; img.hidden = false; if (ph) ph.hidden = true; }
  else { img.removeAttribute("src"); img.hidden = true; if (ph) ph.hidden = false; }
}
function toastOk(msg) { showToast(qs("toast"), qs("toast-msg"), msg); }
function toastErr(msg) { showToast(qs("toast-error"), qs("toast-error-msg"), msg); }
function showToast(el, msgEl, msg) {
  msgEl.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2600);
}
function nowLabel() {
  const d = new Date(); const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

// ─── 보드 렌더 ───────────────────────────────────────────────────────────────
function renderBoard() {
  CU.hero.sort((a, b) => a.position - b.position);
  CU.rail.sort((a, b) => a.position - b.position);
  CU.editorial.sort((a, b) => a.position - b.position);

  qs("hero-caption").textContent = `캐러셀 · ${CU.hero.length}장 · 홈 상단`;
  qs("rail-caption").textContent = `가로 스크롤 레일 · ${CU.rail.length}개 · 히어로 아래`;
  const edSec = qs("board-editorial-sec");
  edSec.hidden = false;
  qs("editorial-caption").textContent = `${CU.editorial.length}개`;
  qs("editorial-empty").hidden = CU.editorial.length > 0;

  const heroes = qs("board-heroes");
  heroes.replaceChildren(...CU.hero.map(heroCardEl));
  const rails = qs("board-rails");
  rails.replaceChildren(...CU.rail.map(railRowEl));
  const eds = qs("board-editorial");
  eds.replaceChildren(...CU.editorial.map(railRowEl));

  updateGlobalDirty();
}
function heroCardEl(it) {
  const el = qs("tpl-hero-card").content.firstElementChild.cloneNode(true);
  el.dataset.slotId = it.slug || String(it.id);
  const card = el.querySelector(".hcard");
  card.classList.toggle("off", !it.isPublished);
  card.classList.toggle("sel", CU.open === it);
  card.setAttribute("aria-label", `${KIND_LABEL.hero} 편집 — ${it.title.split("\n").join(" ")}${it.isPublished ? "" : " (비공개)"}`);
  setImg(card, coverImageUrl(it));
  card.querySelector(".phx").hidden = !!coverImageUrl(it);
  card.querySelector("[data-pos]").textContent = `#${it.position}`;
  card.querySelector(".offbadge").hidden = it.isPublished;
  card.querySelector("[data-t]").textContent = it.title;
  card.querySelector("[data-s]").textContent = it.subtitle || "";
  el.querySelector(".st").classList.toggle("off", !it.isPublished);
  el.querySelector("[data-slug]").textContent = it.slug;
  el.querySelector(".m").hidden = !it.dirty;
  wireBoardItem(el, card, it);
  return el;
}
function railRowEl(it) {
  const el = qs("tpl-rail-row").content.firstElementChild.cloneNode(true);
  el.dataset.slotId = it.slug || String(it.id);
  el.dataset.kind = it.kind;
  el.classList.toggle("sel", CU.open === it);
  el.setAttribute("aria-label", `${KIND_LABEL[it.kind]} 편집 — ${it.title.split("\n").join(" ")}`);
  el.querySelector("[data-pos]").textContent = `#${it.position}`;
  const stack = el.querySelector("[data-stack]");
  const spots = displaySpots(it);
  stack.replaceChildren(...spots.slice(0, 3).map((s) => {
    const sp = document.createElement("span");
    if (s.imageUrl) { const im = document.createElement("img"); im.src = s.imageUrl; im.alt = ""; sp.appendChild(im); }
    return sp;
  }));
  if (spots.length > 3) {
    const more = document.createElement("span");
    more.className = "more"; more.textContent = `+${spots.length - 3}`;
    stack.appendChild(more);
  }
  el.querySelector("[data-t]").textContent = it.title.split("\n").join(" ");
  el.querySelector("[data-s]").textContent = [it.subtitle, it.slug].filter(Boolean).join(" · ");
  const chip = el.querySelector("[data-chip]");
  if (it.dirty) { chip.className = "chip dirtyc"; chip.textContent = "수정됨 · 저장 안 됨"; }
  else if (!it.picks.length) { chip.className = "chip auto"; chip.textContent = "자동충전 · 품질랭킹"; }
  else if (it.picks.length >= 8) { chip.className = "chip full"; chip.textContent = "손픽 8 / 8"; }
  else { chip.className = "chip hand"; chip.textContent = `손픽 ${it.picks.length} / 8`; }
  const tgl = el.querySelector(".tglwrap input");
  tgl.checked = it.isPublished;
  tgl.setAttribute("aria-label", `${it.title.split("\n").join(" ")} — 홈에 발행`);
  tgl.addEventListener("click", (e) => e.stopPropagation());
  tgl.addEventListener("change", () => inlinePublishToggle(it, tgl));
  wireBoardItem(el, el, it);
  return el;
}
function wireBoardItem(root, clickable, it) {
  const open = (e) => {
    if (e.target.closest("[data-stop]")) return;
    openDrawer(it);
  };
  clickable.addEventListener("click", open);
  clickable.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    // 행 내부 컨트롤(발행 토글 등)의 네이티브 키 동작을 삼키지 않는다
    if (e.target.closest("[data-stop]")) return;
    e.preventDefault(); open(e);
  });
  // 보드 드래그 = 순서 교환 (두 큐레이션의 position swap, 저장 즉시)
  root.addEventListener("dragstart", (e) => {
    if (CU.busy) { e.preventDefault(); return; }
    if (it.dirty) { e.preventDefault(); toastErr("저장 안 된 변경이 있어 순서를 바꿀 수 없어요"); return; }
    CU.dragging = it;
    e.dataTransfer.effectAllowed = "move";
  });
  root.addEventListener("dragend", () => { CU.dragging = null; clearDragOver(); });
  root.addEventListener("dragover", (e) => {
    if (!CU.dragging || CU.dragging === it || CU.dragging.kind !== it.kind) return;
    e.preventDefault();
    root.classList.add("drag-over");
  });
  root.addEventListener("dragleave", () => root.classList.remove("drag-over"));
  root.addEventListener("drop", (e) => {
    e.preventDefault();
    root.classList.remove("drag-over");
    if (CU.busy) return;
    if (CU.dragging && CU.dragging !== it && CU.dragging.kind === it.kind) swapPositions(CU.dragging, it);
  });
}
function clearDragOver() {
  document.querySelectorAll(".drag-over").forEach((el) => el.classList.remove("drag-over"));
}
function updateGlobalDirty() {
  const n = dirtyItems().length;
  qs("global-dirty").hidden = n === 0;
  qs("global-dirty-n").textContent = n;
}

// 발행 인라인 토글 (보드에서 즉시 저장 — 로컬 미저장 편집이 있으면 거부)
async function inlinePublishToggle(it, tgl) {
  if (CU.busy) { tgl.checked = it.isPublished; return; }
  if (it.dirty) {
    tgl.checked = it.isPublished;
    toastErr("저장 안 된 변경이 있어요 — 편집 패널에서 저장하세요");
    openDrawer(it);
    return;
  }
  const next = tgl.checked;
  CU.busy = true;
  try {
    await ensureDetail(it);
    const d = await cuFetch(`/admin/api/curations/${it.id}`, "PUT", { ...putPayload(it), isPublished: next });
    applyDetail(it, d);
    renderBoard();
    if (CU.open === it) fillDrawer(it);
    toastOk(`${next ? "발행" : "비공개"} 전환 · ${it.title.split("\n").join(" ")}`);
  } catch (err) {
    tgl.checked = it.isPublished;
    toastErr(`발행 전환 실패 · ${err.message}`);
  } finally {
    CU.busy = false;
  }
}

// 보드 드래그: 두 항목 position 교환 (둘 다 clean 전제)
async function swapPositions(a, b) {
  if (b.dirty) { toastErr("상대 항목에 저장 안 된 변경이 있어요"); return; }
  CU.busy = true;
  try {
    await ensureDetail(a); await ensureDetail(b);
    const pa = a.position, pb = b.position;
    const da = await cuFetch(`/admin/api/curations/${a.id}`, "PUT", { ...putPayload(a), position: pb });
    const db = await cuFetch(`/admin/api/curations/${b.id}`, "PUT", { ...putPayload(b), position: pa });
    applyDetail(a, da); applyDetail(b, db);
    renderBoard();
    if (CU.open) fillDrawer(CU.open);
    toastOk(`순서 변경 · #${pa} ↔ #${pb}`);
  } catch (err) {
    toastErr(`순서 변경 실패 · ${err.message}`);
    loadAll(); // 부분 반영됐을 수 있으니 서버 상태로 리로드
  } finally {
    CU.busy = false;
  }
}

// ─── load ────────────────────────────────────────────────────────────────────
async function loadAll() {
  qs("board-skeleton").hidden = false;
  qs("board-content").hidden = true;
  qs("board-error").hidden = true;
  try {
    const list = await cuFetch("/admin/api/curations");
    CU.hero = (list.heroes || []).map((d) => mkItem(d, "hero"));
    CU.rail = (list.rails || []).map((d) => mkItem(d, "rail"));
    CU.editorial = (list.editorial || []).map((d) => mkItem(d, "editorial"));
    CU.open = null;
    document.body.classList.remove("drawer-open");
    qs("board-skeleton").hidden = true;
    qs("board-content").hidden = false;
    renderBoard();
    // 상세+프리뷰를 미리 채워 레일 스택/자동충전 썸네일을 정확히
    await Promise.all(allItems().map((it) => ensureDetail(it).catch(() => {})));
    await Promise.all(allItems().map((it) => ensurePreview(it)));
    renderBoard();
  } catch (err) {
    qs("board-skeleton").hidden = true;
    qs("board-content").hidden = true;
    qs("board-error").hidden = false;
    qs("board-error-detail").textContent = `GET /admin/api/curations · ${err.message}`;
  }
}

// ─── 슬라이드오버 ────────────────────────────────────────────────────────────
function putPayload(it) {
  return {
    title: it.title || "",
    subtitle: it.subtitle || null,
    lead: it.lead || null,
    intro: it.intro || null,
    coverSpotId: it.cover.contentId || null,
    isPublished: it.isPublished,
    position: it.position | 0,
  };
}
async function openDrawer(it) {
  if (CU.open && CU.open !== it && CU.open.dirty) {
    confirmDiscard(CU.open, () => { discardEdits(CU.open); openDrawer(it); });
    return;
  }
  CU.open = it;
  document.body.classList.add("drawer-open");
  try { await ensureDetail(it); } catch (_) { /* 목록 값으로 표시 */ }
  if (CU.open !== it) return; // fetch 중 다른 카드로 전환됨 — 늦은 응답이 폼을 덮지 않게
  ensurePreview(it).then(() => { if (CU.open === it) updateMiniPreview(it); });
  fillDrawer(it);
  renderBoard();
}
function closeDrawer() {
  if (CU.open && CU.open.dirty) {
    confirmDiscard(CU.open, () => { discardEdits(CU.open); reallyCloseDrawer(); });
    return;
  }
  reallyCloseDrawer();
}
function reallyCloseDrawer() {
  CU.open = null;
  document.body.classList.remove("drawer-open");
  renderBoard();
}
function discardEdits(it) {
  it.detailLoaded = false; it.dirty = false; it.picksDirty = false;
  // renderBoard는 ensureDetail을 호출하지 않으므로 여기서 서버 상태를 즉시 재적용
  // (안 하면 버린 편집이 저장된 것처럼 보드에 남는다)
  ensureDetail(it)
    .then(() => { renderBoard(); if (CU.open === it) fillDrawer(it); })
    .catch(() => { /* 재조회 실패 시 기존 표시 유지 */ });
}

function fillDrawer(it) {
  const isHero = it.kind === "hero", isRail = it.kind === "rail";
  qs("so-kind").textContent = KIND_LABEL[it.kind];
  qs("so-pos-chip").textContent = `position #${it.position}`;
  qs("so-slug").textContent = it.slug || `id ${it.id}`;
  qs("so-heading").textContent = it.title.split("\n").join(" ") || "(제목 없음)";
  const st = qs("so-status");
  st.textContent = it.isPublished ? "발행됨" : "비공개";
  st.className = `chip ${it.isPublished ? "pub" : "unpub"}`;
  qs("so-lastsaved").hidden = !it.savedAt;
  if (it.savedAt) qs("so-lastsaved").textContent = `이 세션에서 저장 ${it.savedAt}`;

  // kind별 표시 전환
  qs("so-cover-sec").hidden = isRail;
  qs("so-lead-fld").hidden = isRail;
  qs("so-intro-fld").hidden = isRail;
  qs("so-title-label").textContent = isRail ? "섹션 제목" : "제목";
  qs("so-title-help").textContent = isRail
    ? "홈에 굵게 노출되는 섹션 타이틀"
    : "줄바꿈(\\n) 보존 · 표지 이미지 위에 그대로 오버레이 · 권장 24자";
  qs("so-picks-label").textContent = isHero ? "손픽 스팟 · 상세 그리드" : isRail ? "레일 스팟 편성" : "손픽 스팟";
  qs("so-autonote-txt").textContent = isRail
    ? "비우면 무드 매칭 품질 랭킹으로 자동 편성 · 미리보기에 실제 반영"
    : "비우면 품질 랭킹으로 자동 충전 · 미리보기에 실제 반영";
  qs("so-pos-hint").textContent = `· ${KIND_LABEL[it.kind]} ${groupOf(it).length}개 중 · 이웃과 교환 · 즉시 저장`;

  // 프리뷰 탭: 레일=홈만, 에디토리얼=상세만
  const tabs = document.querySelectorAll("#so-preview .mini-tabs button");
  tabs.forEach((b) => {
    b.disabled = (b.dataset.m === "detail" && isRail) || (b.dataset.m === "home" && it.kind === "editorial");
  });
  setPreviewTab(it.kind === "editorial" ? "detail" : "home");

  // 폼 값
  qs("so-title").value = it.title;
  qs("so-subtitle").value = it.subtitle;
  qs("so-lead").value = it.lead;
  qs("so-intro").value = it.intro;
  qs("so-publish").checked = it.isPublished;
  qs("so-pos-value").textContent = it.position;
  updateCounters();
  clearFieldErrors();
  renderCover(it);
  renderPicks(it);
  updateMiniPreview(it);

  const ep = `PUT /admin/api/curations/${it.id}`;
  qs("so-endpoint-dirty").textContent = ep;
  qs("so-endpoint-clean").textContent = ep;
  updateSaveState(it);
}
function updateSaveState(it) {
  const dirty = !!it.dirty;
  qs("so-dirty-chip").hidden = !dirty;
  qs("so-state-dirty").hidden = !dirty;
  qs("so-state-clean").hidden = dirty;
  qs("so-save").disabled = !dirty || CU.busy;
  qs("so-revert").disabled = !dirty || CU.busy;
  updateGlobalDirty();
}
function markDirty() {
  const it = CU.open; if (!it) return;
  it.dirty = true;
  updateSaveState(it);
}

function renderCover(it) {
  setImg(qs("so-cover").querySelector(".cimg"), it.cover.imageUrl);
  qs("so-cover-name").textContent = it.cover.name || "표지 미지정";
  qs("so-cover-sub").textContent = it.cover.contentId ? `contentId ${it.cover.contentId}` : "표지 스팟을 선택하세요";
  qs("so-cover-kto").textContent = it.cover.contentId
    ? `KTO #${it.cover.contentId} · 이미지 URL 참조만 · 다운로드 없음`
    : "KTO 이미지 URL 참조만 · 다운로드 없음";
}

function renderPicks(it) {
  qs("so-picks-count").textContent = `${it.picks.length} / 8`;
  const wrap = qs("so-picks");
  const empty = qs("so-picks-empty");
  empty.hidden = it.picks.length > 0;
  qs("so-picks-empty-p").innerHTML = it.kind === "rail"
    ? "지금은 전부 무드 매칭 품질 랭킹으로 자동 편성됩니다.<br>직접 고르려면 아래에서 스팟을 검색해 추가하세요."
    : "지금은 전부 품질 랭킹 상위 스팟으로 자동 충전됩니다.<br>직접 고르려면 아래에서 스팟을 검색해 추가하세요.";
  wrap.replaceChildren(...it.picks.map((p, i) => {
    const el = qs("tpl-pick-item").content.firstElementChild.cloneNode(true);
    el.dataset.spotId = p.contentId;
    el.dataset.i = i;
    el.querySelector("[data-no]").textContent = i + 1;
    setImg(el.querySelector(".pim"), p.imageUrl);
    el.querySelector("[data-t]").textContent = p.name;
    el.querySelector("[data-s]").textContent = `${p.sub || "스팟"} · #${p.contentId}`;
    const rm = el.querySelector(".rm");
    rm.setAttribute("aria-label", `${p.name} 제거`);
    rm.addEventListener("click", (e) => {
      e.stopPropagation();
      it.picks.splice(i, 1);
      it.picksDirty = true; markDirty();
      renderPicks(it); updateMiniPreview(it); renderBoard();
    });
    wirePickDrag(el, it);
    return el;
  }));
}
function wirePickDrag(el, it) {
  el.addEventListener("dragstart", (e) => {
    el.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", el.dataset.i);
    e.stopPropagation();
  });
  el.addEventListener("dragend", () => {
    el.classList.remove("dragging");
    qs("so-picks").querySelectorAll(".pick").forEach((p) => p.classList.remove("drag-over"));
  });
  el.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); el.classList.add("drag-over"); });
  el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
  el.addEventListener("drop", (e) => {
    e.preventDefault(); e.stopPropagation();
    const from = +e.dataTransfer.getData("text/plain"), to = +el.dataset.i;
    if (Number.isNaN(from) || from === to) return;
    const [m] = it.picks.splice(from, 1);
    it.picks.splice(to, 0, m);
    it.picksDirty = true; markDirty();
    renderPicks(it); updateMiniPreview(it); renderBoard();
  });
}

// ─── 미니 프리뷰 (실데이터 렌더) ─────────────────────────────────────────────
function setPreviewTab(m) {
  document.querySelectorAll("#so-preview .mini-tabs button").forEach((b) => {
    const on = b.dataset.m === m;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
  });
  qs("so-preview").classList.toggle("detail", m === "detail");
}
function miniSpotEl(s, cls) {
  const el = qs("tpl-mini-spot").content.firstElementChild.cloneNode(true);
  if (cls) el.classList.add(cls);
  setImg(el, s ? s.imageUrl : null);
  return el;
}
function updateMiniPreview(it) {
  const isRail = it.kind === "rail";
  qs("mp-card").hidden = isRail;
  qs("mp-rail").hidden = !isRail;
  if (isRail) {
    qs("mp-rail-title").textContent = it.title.split("\n").join(" ");
    qs("mp-rail-subtitle").textContent = it.subtitle || "";
    const spots = displaySpots(it);
    qs("mp-rail-empty").hidden = spots.length > 0;
    qs("mp-rail-spots").replaceChildren(...spots.slice(0, 4).map((s) => miniSpotEl(s)));
  } else {
    setImg(qs("mp-card"), coverImageUrl(it));
    qs("mp-card-title").textContent = it.title;
    qs("mp-card-subtitle").textContent = it.subtitle || "";
  }
  // 상세 탭
  setImg(qs("mp-detail").querySelector(".mh2"), coverImageUrl(it));
  qs("mp-detail-title").textContent = it.title;
  qs("mp-detail-lead").textContent = it.lead || "";
  const grid = displaySpots(it).slice(0, 4);
  qs("mp-detail-grid").replaceChildren(...grid.map((s) => miniSpotEl(s)));
  qs("mp-cap").textContent = it.picks.length
    ? "실제 앱과 동일 렌더 · 손픽 순서 그대로"
    : "실제 앱과 동일 렌더 · 자동충전 풀 반영";
}

// ─── 카운터 / 검증 오류 ──────────────────────────────────────────────────────
function updateCounters() {
  document.querySelectorAll("#slideover [data-max]").forEach((f) => {
    const c = document.querySelector(`[data-cnt-for="${f.id}"]`);
    if (!c) return;
    const max = +f.dataset.max, len = (f.value || "").length;
    c.textContent = `${len} / ${max}`;
    c.classList.toggle("over", len > max);
  });
}
function clearFieldErrors() {
  document.querySelectorAll("#slideover .fld.err").forEach((el) => el.classList.remove("err"));
  document.querySelectorAll("#slideover .emsg[data-err-for]").forEach((el) => { el.hidden = true; el.textContent = ""; });
  document.querySelectorAll("#slideover [aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
}
function showValidationErrors(err) {
  clearFieldErrors();
  const inputs = { title: "so-title", subtitle: "so-subtitle", lead: "so-lead", intro: "so-intro" };
  let shown = false;
  (err.details || []).forEach((det) => {
    const key = (det.field || "").split(".").pop();
    const slot = document.querySelector(`#slideover .emsg[data-err-for="${key}"]`);
    if (slot) {
      slot.textContent = det.issue || det.message || "입력값을 확인하세요";
      slot.hidden = false;
      shown = true;
    }
    if (inputs[key]) {
      const input = qs(inputs[key]);
      input.setAttribute("aria-invalid", "true");
      const fld = input.closest(".fld");
      if (fld) fld.classList.add("err");
    }
  });
  toastErr(shown ? "입력값을 확인하세요 — 필드 오류 표시됨" : (err.message || "검증에 실패했습니다"));
}

// ─── 저장 / 되돌리기 ─────────────────────────────────────────────────────────
function setSaving(on) {
  CU.busy = on;
  const b = qs("so-save");
  b.querySelector("[data-save-label]").hidden = on;
  b.querySelector("[data-save-saving]").hidden = !on;
  b.disabled = on || !(CU.open && CU.open.dirty);
  qs("so-revert").disabled = on || !(CU.open && CU.open.dirty);
}
async function saveCuration() {
  const it = CU.open;
  if (!it || CU.busy || !it.dirty) return;
  setSaving(true); clearFieldErrors();
  try {
    // applyDetail이 로컬 손픽을 서버 응답(구 값)으로 덮어쓰기 전에 목표 스팟을 확보
    const wantSpots = it.picksDirty ? it.picks.map((p) => p.contentId).filter(Boolean) : null;
    const localPicks = it.picks;
    const d = await cuFetch(`/admin/api/curations/${it.id}`, "PUT", putPayload(it));
    applyDetail(it, d);
    if (wantSpots !== null) {
      let res;
      try {
        res = await cuFetch(`/admin/api/curations/${it.id}/spots`, "PUT", { spotIds: wantSpots });
      } catch (err) {
        // spots PUT 실패: applyDetail이 덮어쓴 픽을 사용자 편집본으로 복원해
        // 화면과 상태를 일치시키고, 재시도가 옛 목록을 저장하지 않게 한다
        it.picks = localPicks;
        throw err;
      }
      if (res && res.handpicks) {
        it.picks = res.handpicks.map((h) => ({
          contentId: h.contentId, name: h.name || "", sub: h.category || "스팟", imageUrl: h.imageUrl || null,
        }));
      }
      it.picksDirty = false;
    }
    // 자동충전 항목만 재조회 — 손픽이 있는 동안 previewSpots는 어떤 표시 경로에서도 안 읽힘
    if (!it.picks.length) await refreshPreview(it);
    it.dirty = false;
    it.savedAt = nowLabel();
    fillDrawer(it); renderBoard();
    toastOk(`저장됨 · ${it.isPublished ? "발행" : "비공개"} · /home/feed 반영`);
  } catch (err) {
    if (err.status === 422 || err.code === "ADMIN_VALIDATION") showValidationErrors(err);
    else if (err.status === 404) toastErr(`큐레이션을 찾을 수 없습니다 · ${err.message}`);
    else toastErr(`저장 실패 · ${err.message}`);
  } finally {
    setSaving(false);
    if (CU.open) updateSaveState(CU.open);
  }
}
async function revertCurrent() {
  const it = CU.open; if (!it) return;
  confirmDiscard(it, async () => {
    try {
      it.detailLoaded = false;
      await ensureDetail(it);
      it.dirty = false; it.picksDirty = false;
      await refreshPreview(it);
      fillDrawer(it); renderBoard();
      toastOk("서버 상태로 되돌렸습니다");
    } catch (err) {
      toastErr(`되돌리기 실패 · ${err.message}`);
    }
  });
}

// ─── 미저장 확인 다이얼로그 ──────────────────────────────────────────────────
let confirmAction = null;
function confirmDiscard(it, onDiscard) {
  qs("confirm-desc").innerHTML = "";
  const b = document.createElement("b");
  b.textContent = it.title.split("\n").join(" ") || it.slug;
  qs("confirm-desc").append(b, "에 저장하지 않은 수정이 있습니다.", document.createElement("br"), "버리면 변경 내용이 사라집니다.");
  confirmAction = onDiscard;
  qs("confirm-discard").classList.add("show");
  qs("confirm-stay").focus();
}
function closeConfirm() { qs("confirm-discard").classList.remove("show"); confirmAction = null; }

// ─── 스팟 피커 ───────────────────────────────────────────────────────────────
function pickerRegion() {
  const on = document.querySelector("#picker-filters .fchip.on");
  return on ? on.dataset.region || "" : "";
}
function openPicker(mode) {
  CU.pickerMode = mode;
  const m = qs("pickermodal");
  m.dataset.mode = mode;
  m.classList.toggle("mode-cover", mode === "cover");
  m.classList.add("show");
  const inp = qs("picker-search");
  inp.value = "";
  qs("picker-count").textContent = "";
  document.querySelectorAll("#picker-filters .fchip").forEach((c, i) => c.classList.toggle("on", i === 0));
  showPickerState("prompt");
  setTimeout(() => inp.focus(), 60);
}
function closePicker() { qs("pickermodal").classList.remove("show"); CU.pickerMode = null; }
function showPickerState(state) {
  qs("picker-results").hidden = state !== "results";
  qs("picker-empty-prompt").hidden = state !== "prompt";
  qs("picker-empty-none").hidden = state !== "none";
  qs("picker-error").hidden = state !== "error";
}
function searchSkeletonCards() {
  return Array.from({ length: 8 }).map(() => {
    const el = document.createElement("div");
    el.className = "pcard";
    const pi = document.createElement("div");
    pi.className = "pi skel sk-thumb";
    el.appendChild(pi);
    return el;
  });
}
async function runSpotSearch() {
  const q = qs("picker-search").value.trim();
  if (!q) { qs("picker-count").textContent = ""; showPickerState("prompt"); return; }
  const seq = ++CU.searchSeq; // 늦게 도착한 이전 응답이 최신 결과를 덮지 않도록
  showPickerState("results");
  qs("picker-results").replaceChildren(...searchSkeletonCards());
  try {
    const region = pickerRegion();
    const url = `/admin/api/spots/search?q=${encodeURIComponent(q)}` + (region ? `&region=${encodeURIComponent(region)}` : "");
    const data = await cuFetch(url);
    if (seq !== CU.searchSeq) return; // stale
    renderSearchResults(data.spots || []);
  } catch (err) {
    if (seq !== CU.searchSeq) return;
    showPickerState("error");
    qs("picker-error-detail").textContent = err.message;
  }
}
function renderSearchResults(spots) {
  qs("picker-count").textContent = `${spots.length}건`;
  if (!spots.length) { showPickerState("none"); return; }
  showPickerState("results");
  const it = CU.open;
  const picked = new Set((it ? it.picks : []).map((p) => p.contentId));
  qs("picker-results").replaceChildren(...spots.map((s) => {
    const el = qs("tpl-picker-card").content.firstElementChild.cloneNode(true);
    el.dataset.spotId = s.contentId;
    const already = CU.pickerMode === "picks" && picked.has(s.contentId);
    el.classList.toggle("added", already);
    setImg(el.querySelector(".pi"), s.imageUrl);
    el.querySelector("[data-t]").textContent = s.name || "";
    el.querySelector("[data-s]").textContent = `${s.regionName || s.regionCd || ""} · #${s.contentId}`;
    const add = el.querySelector(".add");
    if (already) add.querySelector("[data-mode-picks]").textContent = "추가됨";
    add.addEventListener("click", (e) => {
      e.stopPropagation();
      pickSpot(s, el, add);
    });
    return el;
  }));
}
function pickSpot(s, cardEl, addBtn) {
  const it = CU.open; if (!it) return;
  const spot = { contentId: s.contentId, name: s.name || "", sub: s.regionName || "스팟", imageUrl: s.imageUrl || null };
  if (CU.pickerMode === "cover") {
    it.cover = { contentId: spot.contentId, name: spot.name, imageUrl: spot.imageUrl };
    markDirty();
    renderCover(it); updateMiniPreview(it); renderBoard();
    closePicker();
    toastOk(`표지 스팟 설정 · ${spot.name}`);
    return;
  }
  if (cardEl.classList.contains("added")) return;
  if (it.picks.some((p) => p.contentId === spot.contentId)) { toastErr("이미 추가된 스팟입니다"); return; }
  if (it.picks.length >= 8) { toastErr("손픽은 최대 8개입니다"); return; }
  it.picks.push(spot);
  it.picksDirty = true; markDirty();
  renderPicks(it); updateMiniPreview(it); renderBoard();
  cardEl.classList.add("added");
  addBtn.querySelector("[data-mode-picks]").textContent = "추가됨";
  toastOk(`스팟 추가 · ${spot.name}`);
}

// ─── 폼 바인딩 / 전역 배선 ───────────────────────────────────────────────────
function wireForm() {
  const fields = { "so-title": "title", "so-subtitle": "subtitle", "so-lead": "lead", "so-intro": "intro" };
  Object.entries(fields).forEach(([id, key]) => {
    qs(id).addEventListener("input", (e) => {
      const it = CU.open; if (!it) return;
      it[key] = e.target.value;
      markDirty(); updateCounters(); updateMiniPreview(it); renderBoard();
      if (key === "title") qs("so-heading").textContent = it.title.split("\n").join(" ") || "(제목 없음)";
    });
  });
  qs("so-publish").addEventListener("change", (e) => {
    const it = CU.open; if (!it) return;
    it.isPublished = e.target.checked;
    markDirty(); renderBoard();
    const st = qs("so-status");
    st.textContent = it.isPublished ? "발행됨" : "비공개";
    st.className = `chip ${it.isPublished ? "pub" : "unpub"}`;
  });
  qs("so-pos-dec").addEventListener("click", () => stepPosition(-1));
  qs("so-pos-inc").addEventListener("click", () => stepPosition(1));
  qs("so-save").addEventListener("click", saveCuration);
  qs("so-revert").addEventListener("click", revertCurrent);
  qs("so-close").addEventListener("click", closeDrawer);

  document.querySelectorAll("#so-preview .mini-tabs button").forEach((b) =>
    b.addEventListener("click", () => { if (!b.disabled) setPreviewTab(b.dataset.m); }));
}
// 순서 변경 = 정렬상 이웃과 position 교환 (드래그와 동일하게 swapPositions 재사용, 즉시 저장).
// 단독 대입은 형제와 position이 중복돼 보드/피드 정렬이 깨지므로 swap만 허용한다.
async function stepPosition(delta) {
  const it = CU.open; if (!it || CU.busy) return;
  if (it.dirty) { toastErr("저장 안 된 변경이 있어요 — 저장 후 순서를 바꿀 수 있어요"); return; }
  const group = [...groupOf(it)].sort((a, b) => a.position - b.position);
  const neighbor = group[group.indexOf(it) + delta];
  if (!neighbor) return;
  await swapPositions(it, neighbor); // 성공 시 fillDrawer가 position 표시 갱신
}
function wirePicker() {
  document.querySelectorAll("[data-open-picker]").forEach((b) =>
    b.addEventListener("click", () => openPicker(b.dataset.pickerMode || "picks")));
  document.querySelectorAll("[data-close-picker]").forEach((b) => b.addEventListener("click", closePicker));
  qs("pickermodal").addEventListener("click", (e) => { if (e.target === qs("pickermodal")) closePicker(); });
  qs("picker-search").addEventListener("input", () => {
    clearTimeout(CU.searchTimer);
    const q = qs("picker-search").value.trim();
    if (!q) { CU.searchSeq++; qs("picker-count").textContent = ""; showPickerState("prompt"); return; }
    CU.searchTimer = setTimeout(runSpotSearch, 280);
  });
  document.querySelectorAll("#picker-filters .fchip").forEach((c) =>
    c.addEventListener("click", () => {
      document.querySelectorAll("#picker-filters .fchip").forEach((x) => x.classList.remove("on"));
      c.classList.add("on");
      if (qs("picker-search").value.trim()) runSpotSearch();
    }));
}
function wireGlobal() {
  qs("board-retry").addEventListener("click", loadAll);
  qs("confirm-stay").addEventListener("click", closeConfirm);
  qs("confirm-discard-btn").addEventListener("click", () => {
    const act = confirmAction;
    closeConfirm();
    if (act) act();
  });
  qs("confirm-discard").addEventListener("click", (e) => { if (e.target === qs("confirm-discard")) closeConfirm(); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (qs("pickermodal").classList.contains("show")) closePicker();
    else if (qs("confirm-discard").classList.contains("show")) closeConfirm();
    else if (document.body.classList.contains("drawer-open")) closeDrawer();
  });
  // 저장 안 된 편집이 있으면 페이지 이탈 경고
  window.addEventListener("beforeunload", (e) => {
    if (dirtyItems().length) { e.preventDefault(); e.returnValue = ""; }
  });
  document.querySelectorAll("#slideover [data-max]").forEach((f) => f.addEventListener("input", updateCounters));
}

window.addEventListener("load", () => {
  if (!document.querySelector(".cu-page")) return;
  wireForm();
  wirePicker();
  wireGlobal();
  loadAll();
});
