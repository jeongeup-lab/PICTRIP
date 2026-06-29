// PicTrip ADMIN — 홈 큐레이션 WYSIWYG 편집기 (live fetch wiring)
//
// 좌측 편성 리스트 · 가운데 실시간 폰 미리보기 · 우측 종류별 인스펙터.
// 히어로(region)=표지 카드 + 상세 페이지, 무드 레일(mood)=스팟 선반(상세 없음),
// 에디토리얼(editorial)=상세 전용. /admin/api/curation* 엔드포인트에 배선.
// 미리보기는 /preview(handpick else 품질랭킹 자동충전)로 "앱에 실제로 나갈" 스팟을 보여줌.
// 공용 헬퍼(escapeHtml, adminFetch)는 먼저 로드되는 admin.js 에서 온다.

// ─── PUT helper (JSend, same-origin session) ─────────────────────────────────
async function adminFetchJSON(path, method, body) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let json = null;
  try { json = await res.json(); } catch (_) { /* non-JSON */ }
  if (!res.ok || (json && json.error)) {
    const e = json && json.error ? json.error : {};
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
  heroes: [], rails: [], editorial: [],
  sel: { kind: "hero", idx: 0 },
  view: "home", // 'home' | 'detail'
  busy: false,
  pickerMode: null, searchTimer: null,
};

const esc = (s) => (typeof escapeHtml === "function" ? escapeHtml(s) : String(s == null ? "" : s));
const qs = (id) => document.getElementById(id);
const kindOf = (type) => (type === "region" ? "hero" : type === "mood" ? "rail" : "editorial");
const arrOf = (kind) => (kind === "hero" ? CU.heroes : kind === "rail" ? CU.rails : CU.editorial);
const current = () => arrOf(CU.sel.kind)[CU.sel.idx];

function bg(url) { return url ? ` style="background-image:url('${encodeURI(url)}')"` : ""; }
const NOIMG = `<svg class="noimg-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="m21 16-5-5L5 20"/></svg>`;
// thumbnail element with graceful placeholder when the KTO image URL is missing
function tmb(cls, url) { return `<div class="${cls}${url ? "" : " noimg"}"${bg(url)}>${url ? "" : NOIMG}</div>`; }
// spots the phone should display: handpicks (live edits) else resolved auto-fill
function displaySpots(it) { return it.picks.length ? it.picks : it.previewSpots || []; }

// ─── load ────────────────────────────────────────────────────────────────────
function mkItem(it, kind) {
  return {
    id: it.id, type: it.type, kind, slug: it.slug || "", position: it.position || 0,
    isPublished: !!it.isPublished, title: it.title || "", subtitle: it.subtitle || "",
    lead: "", intro: "",
    cover: { contentId: null, name: "", imageUrl: it.coverUrl || null },
    coverUrl: it.coverUrl || null, picks: [], previewSpots: null,
    detailLoaded: false, previewLoading: false, picksDirty: false,
  };
}
function applyDetail(it, d) {
  it.title = d.title || ""; it.subtitle = d.subtitle || ""; it.lead = d.lead || ""; it.intro = d.intro || "";
  it.isPublished = !!d.isPublished; it.position = d.position || 0; it.slug = d.slug || it.slug;
  if (d.coverSpot) {
    it.cover = { contentId: d.coverSpot.contentId, name: d.coverSpot.name || "", imageUrl: d.coverSpot.imageUrl || null };
    it.coverUrl = d.coverSpot.imageUrl || it.coverUrl;
  } else {
    it.cover = { contentId: null, name: "", imageUrl: it.coverUrl || null };
  }
  it.picks = (d.handpicks || []).map((h) => ({
    contentId: h.contentId, name: h.name || "", cat: h.category || "스팟", imageUrl: h.imageUrl || null,
  }));
  it.detailLoaded = true;
}
async function loadDetailInto(it) {
  applyDetail(it, await adminFetch(`/admin/api/curations/${it.id}`));
  return it;
}
async function ensureDetail(it) {
  if (it && !it.detailLoaded) { try { await loadDetailInto(it); } catch (_) { /* keep list data */ } }
}
// fetch the resolved display spots (handpick else auto-fill) for a truthful preview
async function ensurePreview(it) {
  if (!it || it.previewSpots !== null || it.previewLoading) return;
  it.previewLoading = true;
  try {
    const d = await adminFetch(`/admin/api/curations/${it.id}/preview`);
    it.previewSpots = (d.spots || []).map((s) => ({
      contentId: s.contentId, name: s.name || "", cat: s.category || "스팟", imageUrl: s.imageUrl || null,
    }));
  } catch (_) { it.previewSpots = []; }
  finally { it.previewLoading = false; }
}
async function refreshPreview(it) { it.previewSpots = null; await ensurePreview(it); }

async function loadAll() {
  setSaveState("loading");
  try {
    const list = await adminFetch("/admin/api/curations");
    CU.heroes = (list.heroes || []).map((it) => mkItem(it, "hero"));
    CU.rails = (list.rails || []).map((it) => mkItem(it, "rail"));
    CU.editorial = (list.editorial || []).map((it) => mkItem(it, "editorial"));
    renderCounts();
    renderLists();

    // preload details + previews for the home items so the phone is truthful
    const home = [...CU.heroes, ...CU.rails];
    await Promise.all(home.map((it) => loadDetailInto(it).catch(() => {})));
    await Promise.all(home.map((it) => ensurePreview(it)));

    const first = CU.heroes[0] || CU.rails[0] || CU.editorial[0];
    if (!first) { showEmpty(); setSaveState("saved", "큐레이션 없음"); return; }
    CU.sel = { kind: first.kind, idx: 0 };
    CU.view = first.kind === "editorial" ? "detail" : "home";
    await ensureDetail(current()); await ensurePreview(current());
    renderScreen(); renderInspector(); updateToggle();
    if (CU.view === "home") scrollPreviewTo(CU.sel.kind, CU.sel.idx);
    setSaveState("saved", "불러옴");
  } catch (err) {
    showLoadError(err.message);
  }
}

function showEmpty() {
  qs("phoneBody").innerHTML = `<div class="phone-msg">큐레이션이 없습니다.</div>`;
  qs("inspBody").innerHTML = `<div class="insp-empty">편집할 큐레이션이 없습니다.</div>`;
}
function showLoadError(msg) {
  setSaveState("saved", "오류");
  qs("phoneBody").innerHTML =
    `<div class="phone-msg"><b>불러오지 못했습니다</b><div class="d">${esc(msg)}</div>` +
    `<button class="add-pick" style="max-width:160px;margin:14px auto 0" id="cuRetry">다시 시도</button></div>`;
  const r = qs("cuRetry"); if (r) r.addEventListener("click", loadAll);
}

// ─── counts + left list ──────────────────────────────────────────────────────
function renderCounts() {
  qs("heroCount").textContent = CU.heroes.length;
  qs("railCount").textContent = CU.rails.length;
  qs("listCount").textContent = `히어로 ${CU.heroes.length} · 레일 ${CU.rails.length}`;
  const edWrap = qs("editorialWrap");
  if (CU.editorial.length) { edWrap.style.display = ""; qs("edCount").textContent = CU.editorial.length; }
  else edWrap.style.display = "none";
}
function slotLabel(it) {
  if (it.kind === "rail") return it.title || it.slug || "무드 레일";
  return it.slug || (it.title || "").split("\n")[0] || "(제목 없음)";
}
function slotHtml(it, kind, i) {
  const active = CU.sel.kind === kind && CU.sel.idx === i;
  const thumbUrl = it.coverUrl || (it.picks[0] && it.picks[0].imageUrl) || null;
  const n = it.picks.length;
  const sub = (n ? `${n} ${kind === "hero" ? "손픽" : "스팟"}` : "자동 편성") + ` · #${it.position}`;
  return (
    `<div class="slot${active ? " active" : ""}" data-kind="${kind}" data-idx="${i}">` +
    tmb("sthumb", thumbUrl) +
    `<span class="smeta"><span class="stitle">${esc(slotLabel(it))}</span><span class="ssub">${esc(sub)}</span></span>` +
    `<span class="sdot ${it.isPublished ? "on" : "off"}" title="${it.isPublished ? "발행됨" : "미발행"}"></span>` +
    `</div>`
  );
}
function renderLists() {
  qs("heroList").innerHTML = CU.heroes.map((it, i) => slotHtml(it, "hero", i)).join("");
  qs("railList").innerHTML = CU.rails.map((it, i) => slotHtml(it, "rail", i)).join("");
  qs("editorialList").innerHTML = CU.editorial.map((it, i) => slotHtml(it, "editorial", i)).join("");
  document.querySelectorAll(".wcol-list .slot").forEach((el) =>
    el.addEventListener("click", () => selectSlot(el.dataset.kind, +el.dataset.idx)));
}

// ─── phone preview ───────────────────────────────────────────────────────────
function spotCardHtml(s) {
  return `<div class="pcard" data-spot="1">${tmb("pthumb", s.imageUrl)}<div class="nm">${esc(s.name)}</div><div class="cat">${esc(s.cat)}</div></div>`;
}
function skeletonCards() {
  return Array.from({ length: 3 }).map(() =>
    `<div class="pcard"><div class="pthumb sk"></div><div class="sk line" style="margin-top:8px;width:70%"></div></div>`).join("");
}
function railCardsHtml(it) {
  if (it.picks.length) return it.picks.map(spotCardHtml).join("");
  if (it.previewSpots === null) return skeletonCards();
  if (!it.previewSpots.length) return `<div class="rail-empty">표시할 스팟이 없어요</div>`;
  return it.previewSpots.map(spotCardHtml).join("");
}
function isAuto(it) { return !it.picks.length && Array.isArray(it.previewSpots) && it.previewSpots.length > 0; }

function renderScreen() {
  const body = qs("phoneBody");
  qs("stageSub").textContent = CU.view === "home" ? "홈 피드" : "큐레이션 상세";
  body.innerHTML = CU.view === "home" ? homeHTML() : detailHTML(current());
  if (CU.view === "home") {
    body.querySelectorAll(".hero[data-idx]").forEach((el) =>
      el.addEventListener("click", () => selectSlot("hero", +el.dataset.idx, "detail")));
    body.querySelectorAll(".section[data-idx]").forEach((el) =>
      el.addEventListener("click", () => selectSlot("rail", +el.dataset.idx)));
    body.querySelectorAll(".pcard[data-spot]").forEach((el) =>
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const sec = el.closest(".section");
        if (sec) selectSlot("rail", +sec.dataset.idx);
        wzToast("이 스팟은 앱에서 스팟 상세(/spots)로 이동해요");
      }));
  } else {
    const back = body.querySelector(".nav-back");
    if (back) back.addEventListener("click", () => setView("home"));
  }
  positionFocusRing();
}
function homeHTML() {
  const heroes = CU.heroes.map((h, i) => {
    const sel = CU.sel.kind === "hero" && CU.sel.idx === i;
    return (
      `<div class="hero${h.isPublished ? "" : " is-draft"}" data-idx="${i}">` +
      `<div class="himg${h.coverUrl ? "" : " noimg"}"${bg(h.coverUrl)}>${h.coverUrl ? "" : NOIMG}</div>` +
      `<div class="draft-tag"><span style="width:6px;height:6px;border-radius:50%;background:#fff;display:block"></span>미발행</div>` +
      `<div class="hero-cap"><div class="hero-title">${esc(h.title).replace(/\n/g, "<br>")}</div>` +
      (h.subtitle ? `<div class="hero-sub">${esc(h.subtitle)}</div>` : "") + `</div>` +
      (sel ? `<div class="hero-tapcue"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>탭하면 상세</div>` : "") +
      `</div>`
    );
  }).join("");
  const segs = CU.heroes.map((_, i) =>
    `<span class="pseg ${(CU.sel.kind === "hero" ? i === CU.sel.idx : i === 0) ? "active" : ""}"></span>`).join("");
  const rails = CU.rails.map((r, i) => (
    `<div class="section${r.isPublished ? "" : " is-draft"}${CU.sel.kind === "rail" && CU.sel.idx === i ? " sel-rail" : ""}" data-idx="${i}">` +
    `<div class="divider"></div>` +
    `<div class="sec-title">${esc(r.title)}${isAuto(r) ? `<span class="auto-pill">자동 편성</span>` : ""}</div>` +
    (r.subtitle ? `<div class="sec-sub">${esc(r.subtitle)}</div>` : "") +
    `<div class="rail">${railCardsHtml(r)}</div></div>`
  )).join("");
  return (
    `<div class="topbar-app"><div class="wordmark-app">PicTrip</div></div>` +
    `<div class="hero-track" id="heroTrack">${heroes}</div>` +
    `<div class="pagebar">${segs}</div>` +
    `<div id="railSections">${rails}</div>` +
    `<div class="tabbar">` +
    `<div class="tab active"><svg width="23" height="23" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3 3 10v10a1 1 0 0 0 1 1h5v-6h6v6h5a1 1 0 0 0 1-1V10z"/></svg><span class="tlabel">홈</span></div>` +
    `<div class="tab"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6.5 7-11a7 7 0 1 0-14 0c0 4.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg><span class="tlabel">지도</span></div>` +
    `<div class="tab"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h3l1.5-2.2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/></svg><span class="tlabel">사진</span></div>` +
    `<div class="tab"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M5 21c0-3.9 3.1-7 7-7s7 3.1 7 7"/></svg><span class="tlabel">마이</span></div>` +
    `</div>`
  );
}
function gcardHtml(s) {
  return `<div class="gcard">${tmb("gimg", s.imageUrl)}<div class="gnm">${esc(s.name)}</div><div class="gcat">${esc(s.cat)}</div></div>`;
}
function detailGridHtml(it) {
  if (it.picks.length) return it.picks.map(gcardHtml).join("");
  if (it.previewSpots === null) return Array.from({ length: 4 }).map(() => `<div class="gcard"><div class="gimg sk"></div><div class="sk line" style="margin-top:9px;width:65%"></div></div>`).join("");
  if (!it.previewSpots.length) return `<div class="dgrid-empty">표시할 스팟이 없어요</div>`;
  return it.previewSpots.map(gcardHtml).join("");
}
function detailHTML(it) {
  if (!it) return "";
  return (
    `<div class="dnav">` +
    `<div class="nav-btn nav-back"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg></div>` +
    `<div class="nav-btn"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="2.6"/><circle cx="6" cy="12" r="2.6"/><circle cx="18" cy="19" r="2.6"/><path d="M8.3 10.7l7.4-4.4M8.3 13.3l7.4 4.4"/></svg></div>` +
    `</div>` +
    `<div class="dtitle">${esc(it.title).replace(/\n/g, "<br>")}</div>` +
    `<div class="dcover${it.cover.imageUrl ? "" : " noimg"}"${bg(it.cover.imageUrl)}>${it.cover.imageUrl ? "" : NOIMG}</div>` +
    (it.lead ? `<div class="dlead">${esc(it.lead)}</div>` : "") +
    (it.intro ? `<div class="dintro">${esc(it.intro).replace(/\n/g, "<br>")}</div>` : "") +
    `<div class="dchev"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></div>` +
    `<div class="dgrid">${detailGridHtml(it)}</div>`
  );
}

// ─── selection / view ────────────────────────────────────────────────────────
async function selectSlot(kind, idx, wanted) {
  CU.sel = { kind, idx };
  if (kind === "rail") CU.view = "home";
  else if (kind === "editorial") CU.view = "detail";
  else if (wanted) CU.view = wanted;
  const it = current();
  await ensureDetail(it); await ensurePreview(it);
  renderLists(); renderInspector(); updateToggle(); renderScreen();
  if (CU.view === "home") scrollPreviewTo(kind, idx);
  else document.querySelector(".wcol-stage .wcol-b").scrollTo({ top: 0, behavior: "smooth" });
}
function setView(v) {
  const kind = CU.sel.kind;
  if (v === "detail" && kind === "rail") { wzToast("무드 레일은 상세 화면이 없어요"); return; }
  if (v === "home" && kind === "editorial") { wzToast("에디토리얼은 홈에 노출되지 않아요"); return; }
  CU.view = v; updateToggle(); renderScreen();
  if (v === "home") scrollPreviewTo(kind, CU.sel.idx);
  else document.querySelector(".wcol-stage .wcol-b").scrollTo({ top: 0, behavior: "smooth" });
}
function updateToggle() {
  const kind = CU.sel.kind;
  document.querySelectorAll("#viewToggle button").forEach((b) => {
    const v = b.dataset.view;
    b.classList.toggle("on", v === CU.view);
    const disabled = (v === "detail" && kind === "rail") || (v === "home" && kind === "editorial");
    b.classList.toggle("disabled", disabled);
  });
}

// ─── inspector ───────────────────────────────────────────────────────────────
function renderInspector() {
  const it = current();
  if (!it) { qs("inspBody").innerHTML = `<div class="insp-empty">선택된 큐레이션이 없습니다.</div>`; return; }
  const thumbUrl = it.kind === "rail" ? (it.picks[0] && it.picks[0].imageUrl) : it.cover.imageUrl;
  const ct = qs("inspThumb");
  if (thumbUrl) { ct.classList.remove("noimg"); ct.style.backgroundImage = `url('${encodeURI(thumbUrl)}')`; ct.innerHTML = ""; }
  else { ct.classList.add("noimg"); ct.style.backgroundImage = ""; ct.innerHTML = NOIMG; }
  if (it.kind === "rail") {
    qs("inspName").textContent = `${it.picks.length || (it.previewSpots ? it.previewSpots.length : 0)}개 스팟${isAuto(it) ? " · 자동" : ""}`;
    qs("inspPath").textContent = `무드 레일 · 슬롯 ${it.position}`;
  } else {
    qs("inspName").textContent = it.cover.name || "표지 미지정";
    qs("inspPath").textContent = `/curations/${it.slug || ""} · 슬롯 ${it.position}`;
  }
  qs("inspBody").innerHTML = it.kind === "rail" ? railInspectorHTML(it) : heroInspectorHTML(it);
  bindInspector(it);
  renderPicks();
  // footer publish toggle reflects current state
  const pb = qs("pubToggleBtn");
  if (pb) { pb.textContent = it.isPublished ? "발행 취소" : "발행"; pb.classList.toggle("danger", it.isPublished); }
}

function editGroupHTML(it) {
  const n = arrOf(it.kind).length;
  const suffix = it.kind === "hero" ? `/ ${n} 지역 중` : it.kind === "rail" ? `/ ${n} 무드 중` : `/ ${n} 에디토리얼`;
  return (
    `<div class="fgroup">` +
    `<div class="fg-label"><svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>편성</div>` +
    `<div class="status-row"><div class="tr-title">발행 상태</div><span class="pub-badge ${it.isPublished ? "on" : "off"}">${it.isPublished ? "발행됨" : "초안"}</span></div>` +
    `<div class="field" style="margin-top:14px"><label>홈 내 위치</label><div class="pos-row"><button class="pos-step" id="posDown">−</button><span class="pos-val" id="posVal">${it.position}</span><button class="pos-step" id="posUp">+</button><span class="pos-suffix">${suffix}</span></div></div>` +
    `</div>`
  );
}
function heroInspectorHTML(it) {
  return (
    `<div class="fgroup">` +
    `<div class="fg-label"><svg viewBox="0 0 24 24" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="m21 16-5-5L5 20"/></svg>홈 카드 <span class="tagn">캐러셀</span></div>` +
    `<div class="cover-card">${tmb("cc-img", it.cover.imageUrl)}` +
    `<div class="cc-meta"><div class="cc-name">${esc(it.cover.name || "표지 미지정")}</div><div class="cc-sub">${it.cover.contentId ? "contentId " + esc(it.cover.contentId) : "표지 스팟을 선택하세요"}</div></div>` +
    `<button class="mini-btn" data-open-picker="cover">변경</button></div>` +
    `<div class="urlnote"><svg viewBox="0 0 24 24" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>KTO 이미지 URL 참조만 · 다운로드·저장 없음</div>` +
    `<div class="field" style="margin-top:13px"><label>제목 <span class="counter" id="cTitle">0</span></label><textarea class="ta title" id="fTitle" rows="2"></textarea><div class="hint">표지 위 오버레이 · 줄바꿈 그대로 노출</div></div>` +
    `<div class="field"><label>부제 <span class="counter" id="cSub">0</span></label><input class="inp" id="fSub" placeholder="표지 아래 한 줄" /></div>` +
    `</div>` +

    `<div class="fgroup">` +
    `<div class="fg-label"><svg viewBox="0 0 24 24" stroke-linejoin="round"><path d="M7 4h7l4 4v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M13 4v5h5"/></svg>상세 페이지 <span class="tagn">탭 시</span></div>` +
    `<button class="detail-cta" id="previewDetail"><svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>상세 화면 미리보기</button>` +
    `<div class="field"><label>리드문 <span class="counter" id="cLead">0</span></label><input class="inp" id="fLead" placeholder="상세 중앙 한 줄" /></div>` +
    `<div class="field"><label>인트로 <span class="counter" id="cIntro">0</span></label><textarea class="ta" id="fIntro" rows="3" placeholder="상세 에디토리얼 문단"></textarea></div>` +
    `<div class="pick-head" style="margin-top:4px"><span class="lab">손픽 스팟 · 상세 그리드</span><span class="pc" id="pickCount">0 / 8</span></div>` +
    `<div class="picklist" id="pickList"></div>` +
    `<button class="add-pick" data-open-picker="handpick"><svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>스팟 추가</button>` +
    `<div class="hint" style="margin-top:10px">비우면 <b>품질 랭킹</b>으로 자동 채움 (미리보기에 실제 반영)</div>` +
    `</div>` +

    editGroupHTML(it)
  );
}
function railInspectorHTML(it) {
  return (
    `<div class="fgroup">` +
    `<div class="fg-label"><svg viewBox="0 0 24 24" stroke-linejoin="round"><path d="M4 5h16v4H4zM7 13h10M7 17h6"/></svg>레일 헤더</div>` +
    `<div class="field"><label>섹션 제목 <span class="counter" id="cTitle">0</span></label><input class="inp title" id="fTitle" placeholder="예) 바다 보러 갈까요" /><div class="hint">홈에 굵게 노출되는 섹션 타이틀</div></div>` +
    `<div class="field"><label>부제 <span class="counter" id="cSub">0</span></label><input class="inp" id="fSub" placeholder="섹션 아래 회색 한 줄" /></div>` +
    `</div>` +

    `<div class="fgroup primary">` +
    `<div class="fg-label"><svg viewBox="0 0 24 24" stroke-linejoin="round"><rect x="3" y="4" width="6" height="16" rx="1.5"/><rect x="11" y="4" width="6" height="16" rx="1.5"/><path d="M20 4v16"/></svg>스팟 편성 <span class="tagn">주 편집</span></div>` +
    `<div class="pick-head"><span class="lab">레일에 노출되는 스팟 순서</span><span class="pc" id="pickCount">0 / 8</span></div>` +
    `<div class="picklist big" id="pickList"></div>` +
    `<button class="add-pick" data-open-picker="handpick"><svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>스팟 추가</button>` +
    `<div class="hint" style="margin-top:10px">비우면 무드 매칭 품질 랭킹으로 자동 편성 (미리보기에 실제 반영)</div>` +
    `</div>` +

    editGroupHTML(it)
  );
}

function renderPicks() {
  const it = current();
  const cnt = qs("pickCount"); if (cnt) cnt.textContent = `${it.picks.length} / 8`;
  const list = qs("pickList"); if (!list) return;
  if (!it.picks.length) {
    list.innerHTML = `<div class="empty-picks">${it.kind === "hero" ? "손픽이 비어 있어요.<br>품질 랭킹으로 자동 편성됩니다." : "스팟이 비어 있어요.<br>무드 매칭으로 자동 편성됩니다."}</div>`;
    return;
  }
  list.innerHTML = it.picks.map((p, i) =>
    `<div class="pick" data-i="${i}" draggable="true">` +
    `<span class="pgrip"><svg width="9" height="15" viewBox="0 0 9 15" fill="currentColor"><circle cx="2" cy="2" r="1.4"/><circle cx="7" cy="2" r="1.4"/><circle cx="2" cy="7.5" r="1.4"/><circle cx="7" cy="7.5" r="1.4"/><circle cx="2" cy="13" r="1.4"/><circle cx="7" cy="13" r="1.4"/></svg></span>` +
    `<span class="pnum">${i + 1}</span>${tmb("pimg", p.imageUrl)}` +
    `<div class="pmeta"><div class="pname">${esc(p.name)}</div><div class="pcat">${esc(p.cat)}</div></div>` +
    `<button class="px" data-rm="${i}"><svg viewBox="0 0 24 24" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>` +
    `</div>`).join("");
  list.querySelectorAll(".px").forEach((b) => b.addEventListener("click", (e) => {
    e.stopPropagation();
    it.picks.splice(+b.dataset.rm, 1);
    it.picksDirty = true; markDirty();
    renderPicks(); renderScreen(); renderLists();
  }));
  wirePickDrag(list, it);
}
function wirePickDrag(list, it) {
  let drag = null;
  list.querySelectorAll(".pick").forEach((el) => {
    el.addEventListener("dragstart", (e) => { drag = el; el.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; });
    el.addEventListener("dragend", () => { el.classList.remove("dragging"); list.querySelectorAll(".pick").forEach((p) => p.classList.remove("drag-over")); drag = null; });
    el.addEventListener("dragover", (e) => { e.preventDefault(); if (drag && drag !== el) el.classList.add("drag-over"); });
    el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
    el.addEventListener("drop", (e) => {
      e.preventDefault();
      if (!drag || drag === el) return;
      const from = +drag.dataset.i, to = +el.dataset.i;
      const [m] = it.picks.splice(from, 1); it.picks.splice(to, 0, m);
      it.picksDirty = true; markDirty();
      renderPicks(); renderScreen(); renderLists();
    });
  });
}

function bindInspector(it) {
  const map = { fTitle: "title", fSub: "subtitle", fLead: "lead", fIntro: "intro" };
  Object.keys(map).forEach((id) => {
    const el = qs(id); if (!el) return;
    el.value = it[map[id]] || "";
    el.addEventListener("input", (e) => { it[map[id]] = e.target.value; markDirty(); updateCounters(); renderScreen(); });
  });
  updateCounters();
  const up = qs("posUp"), down = qs("posDown");
  if (up) up.addEventListener("click", () => { it.position += 1; qs("posVal").textContent = it.position; markDirty(); });
  if (down) down.addEventListener("click", () => { it.position = Math.max(0, it.position - 1); qs("posVal").textContent = it.position; markDirty(); });
  const pd = qs("previewDetail"); if (pd) pd.addEventListener("click", () => setView("detail"));
}
function updateCounters() {
  [["fTitle", "cTitle"], ["fSub", "cSub"], ["fLead", "cLead"], ["fIntro", "cIntro"]].forEach(([a, b]) => {
    const ea = qs(a), eb = qs(b); if (ea && eb) eb.textContent = (ea.value || "").length;
  });
}

// ─── focus ring / scroll ─────────────────────────────────────────────────────
function scrollPreviewTo(kind, idx) {
  if (CU.view !== "home") return;
  const scroll = document.querySelector(".wcol-stage .wcol-b");
  if (!scroll) return;
  if (kind === "hero") {
    const track = qs("heroTrack"); const hero = track && track.children[idx];
    if (hero) track.scrollTo({ left: hero.offsetLeft, behavior: "smooth" });
    scroll.scrollTo({ top: 0, behavior: "smooth" });
  } else if (kind === "rail") {
    const sec = qs("railSections") && qs("railSections").children[idx];
    if (sec) scroll.scrollTo({ top: Math.max(0, sec.offsetTop + qs("phoneBody").offsetTop - 100), behavior: "smooth" });
  }
  setTimeout(positionFocusRing, 360);
}
function positionFocusRing() {
  const ring = qs("focusRing");
  if (CU.view !== "home") { ring.classList.remove("show"); return; }
  const phone = qs("phone"); if (!phone) { ring.classList.remove("show"); return; }
  const pr = phone.getBoundingClientRect();
  let top, bottom;
  if (CU.sel.kind === "hero") {
    const h = document.querySelector('.hero[data-idx="' + CU.sel.idx + '"]');
    if (!h) { ring.classList.remove("show"); return; }
    const r = h.getBoundingClientRect(); top = r.top - pr.top + 5; bottom = r.bottom - pr.top - 5;
  } else if (CU.sel.kind === "rail") {
    const sec = document.querySelector('.section[data-idx="' + CU.sel.idx + '"]');
    if (!sec) { ring.classList.remove("show"); return; }
    const t = sec.querySelector(".sec-title") || sec, rail = sec.querySelector(".rail") || sec;
    top = t.getBoundingClientRect().top - pr.top - 10; bottom = rail.getBoundingClientRect().bottom - pr.top + 10;
  } else { ring.classList.remove("show"); return; }
  if (top < 0) top = 0;
  if (bottom > pr.height) bottom = pr.height;
  const height = bottom - top;
  if (height < 24) { ring.classList.remove("show"); return; }
  ring.style.top = top + "px"; ring.style.height = height + "px";
  ring.querySelector(".rtag").textContent = CU.sel.kind === "hero" ? "편집 중 · 히어로" : "편집 중 · 레일";
  ring.classList.add("show");
}
document.querySelector(".wcol-stage .wcol-b") &&
  document.querySelector(".wcol-stage .wcol-b").addEventListener("scroll", positionFocusRing, { passive: true });
window.addEventListener("resize", positionFocusRing);

// ─── save ────────────────────────────────────────────────────────────────────
function nowLabel() {
  const d = new Date(); const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function setSaveState(kind, label) {
  const el = qs("saveState"); if (!el) return;
  el.classList.toggle("dirty", kind === "dirty");
  const t = el.querySelector(".txt");
  if (kind === "loading") t.textContent = "불러오는 중…";
  else if (kind === "dirty") t.textContent = "편집 중";
  else t.textContent = label || "저장됨";
}
function markDirty() { setSaveState("dirty"); }
function clearDirty(label) { setSaveState("saved", label); }
function setBusy(on) {
  CU.busy = on;
  ["tempSave", "pubToggleBtn", "revertBtn"].forEach((id) => { const b = qs(id); if (b) b.disabled = on; });
}
function clearFieldErrors() {
  document.querySelectorAll(".field-err").forEach((el) => el.remove());
  document.querySelectorAll(".field.has-err").forEach((el) => el.classList.remove("has-err"));
}
function showValidationErrors(err) {
  clearFieldErrors();
  const idMap = { title: "fTitle", subtitle: "fSub", lead: "fLead", intro: "fIntro" };
  (err.details || []).forEach((det) => {
    const key = (det.field || "").split(".").pop();
    const inputId = idMap[key];
    if (inputId && qs(inputId)) {
      const field = qs(inputId).closest(".field");
      if (field) {
        field.classList.add("has-err");
        const m = document.createElement("div"); m.className = "field-err";
        m.textContent = det.issue || det.message || "입력값을 확인하세요";
        field.appendChild(m);
      }
    } else if (key === "coverSpotId" || key === "spotIds") {
      wzToast((key === "coverSpotId" ? "표지 스팟" : "손픽 스팟") + " 오류", det.issue || det.message || "");
    }
  });
  wzToast("입력값을 확인하세요", err.message || "");
}
async function saveCuration(publishOverride, label) {
  const it = current();
  if (!it || CU.busy) return;
  setBusy(true); clearFieldErrors();
  try {
    const payload = {
      title: it.title || "", subtitle: it.subtitle || null, lead: it.lead || null, intro: it.intro || null,
      coverSpotId: it.cover.contentId || null,
      isPublished: publishOverride != null ? publishOverride : it.isPublished,
      position: it.position | 0,
    };
    const d = await adminFetchJSON(`/admin/api/curations/${it.id}`, "PUT", payload);
    applyDetail(it, d);
    if (it.picksDirty) {
      const ids = it.picks.map((p) => p.contentId).filter(Boolean);
      const res = await adminFetchJSON(`/admin/api/curations/${it.id}/spots`, "PUT", { spotIds: ids });
      if (res && res.handpicks) {
        it.picks = res.handpicks.map((h) => ({ contentId: h.contentId, name: h.name || "", cat: h.category || "스팟", imageUrl: h.imageUrl || null }));
      }
      it.picksDirty = false;
    }
    await refreshPreview(it); // auto-fill may have changed (cache invalidated on save)
    clearDirty(`${label} · ${nowLabel()}`);
    renderLists(); renderScreen(); renderInspector(); updateToggle();
    wzToast(label, it.title || "");
  } catch (err) {
    if (err.status === 422 || err.code === "ADMIN_VALIDATION") showValidationErrors(err);
    else if (err.status === 404 || err.code === "ADMIN_CURATION_NOT_FOUND") wzToast("큐레이션을 찾을 수 없습니다", err.message);
    else wzToast("저장 실패", err.message || "");
  } finally {
    setBusy(false);
  }
}
async function revertCurrent() {
  const it = current(); if (!it) return;
  try {
    await loadDetailInto(it); it.picksDirty = false; await refreshPreview(it);
    clearDirty("편집 취소됨"); renderLists(); renderScreen(); renderInspector();
    wzToast("서버 상태로 되돌림", "");
  } catch (err) { wzToast("되돌리기 실패", err.message || ""); }
}

// ─── spot picker modal (cover + handpick) ────────────────────────────────────
function pickedIds() { const it = current(); return new Set((it ? it.picks : []).map((p) => p.contentId)); }
function openPicker(mode) {
  CU.pickerMode = mode;
  const m = qs("pickermodal"); if (!m) return;
  const h3 = m.querySelector(".mh-titles h3"); const sub = m.querySelector(".mh-titles .mh-sub");
  if (h3) h3.textContent = mode === "cover" ? "표지 스팟 선택" : "스팟 추가";
  if (sub) sub.textContent = mode === "cover" ? "이 큐레이션의 표지로 쓸 관광지를 검색합니다" : "손픽 스팟에 넣을 관광지를 검색해 추가합니다";
  const results = m.querySelector(".results");
  if (results) results.innerHTML = `<div class="estate"><div class="d">검색어를 입력하세요.</div></div>`;
  m.classList.add("show");
  const inp = m.querySelector(".search input");
  if (inp) { inp.value = ""; setTimeout(() => inp.focus(), 60); }
}
function closePicker() { const m = qs("pickermodal"); if (m) m.classList.remove("show"); }

function activeRegionParam() {
  const chip = document.querySelector("#pickermodal .fchip.on");
  if (!chip) return "";
  const label = chip.textContent.trim();
  const regionChips = ["제주", "부산", "강원", "서울", "경기", "경주", "전주", "강릉", "여수"];
  return regionChips.includes(label) ? label : "";
}
function searchSkeleton() {
  return Array.from({ length: 6 }).map(() =>
    `<div class="rspot"><div class="thumb sk"></div><div class="meta"><div class="sk line"></div><div class="sk line" style="width:50%;margin-top:6px"></div></div></div>`).join("");
}
async function runSpotSearch(q) {
  const results = document.querySelector("#pickermodal .results"); if (!results) return;
  results.innerHTML = searchSkeleton();
  try {
    const region = activeRegionParam();
    const url = `/admin/api/spots/search?q=${encodeURIComponent(q)}` + (region ? `&region=${encodeURIComponent(region)}` : "");
    const data = await adminFetch(url);
    renderSearchResults(data.spots || []);
  } catch (err) {
    results.innerHTML = `<div class="estate"><div class="d">${esc(err.message)}</div></div>`;
  }
}
function renderSearchResults(spots) {
  const results = document.querySelector("#pickermodal .results"); if (!results) return;
  if (!spots.length) { results.innerHTML = `<div class="estate"><div class="d">검색 결과가 없습니다.</div></div>`; return; }
  const picked = pickedIds();
  results.innerHTML = spots.map((s) => {
    const region = s.regionName || s.regionCd || "";
    const already = CU.pickerMode === "handpick" && picked.has(s.contentId);
    const subParts = [region, s.category, `#${esc(s.contentId)}`].filter(Boolean);
    const img = s.imageUrl || "";
    return (
      `<div class="rspot${already ? " added" : ""}" data-content-id="${esc(s.contentId)}" data-name="${esc(s.name || "")}" data-img="${esc(img)}" data-region="${esc(region)}" data-cat="${esc(s.category || "")}">` +
      `<div class="thumb${img ? "" : " noimg"}"${bg(img)}>${img ? "" : `<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8"/></svg>`}</div>` +
      `<div class="meta"><div class="nm">${esc(s.name || "")}</div><div class="sub">${subParts.join(" · ")}</div></div>` +
      `<button class="btn ghost add" type="button">` + (already ? `<svg class="bi chk" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>추가됨` : "추가") + `</button>`
    );
  }).join("");
}

// ─── global wiring ───────────────────────────────────────────────────────────
let wzToastTimer;
function wzToast(msg, sub) {
  const t = qs("toast"); if (!t) { if (typeof toast === "function") toast(msg, sub || ""); return; }
  qs("toastMsg").textContent = sub ? `${msg} · ${sub}` : msg;
  t.classList.add("show"); clearTimeout(wzToastTimer);
  wzToastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

document.addEventListener("click", (e) => {
  const trig = e.target.closest("[data-open-picker]");
  if (trig) { e.preventDefault(); openPicker(trig.dataset.openPicker); return; }

  const addBtn = e.target.closest("#pickermodal .rspot .add");
  if (addBtn) {
    const row = addBtn.closest(".rspot");
    const contentId = row.dataset.contentId, name = row.dataset.name;
    const img = row.dataset.img || null, cat = row.dataset.cat || "스팟";
    const it = current();
    if (CU.pickerMode === "cover") {
      it.cover = { contentId, name, imageUrl: img }; markDirty();
      renderInspector(); renderScreen(); renderLists(); closePicker(); wzToast("표지 스팟 설정", name);
      return;
    }
    if (row.classList.contains("added")) return;
    if (it.picks.some((p) => p.contentId === contentId)) { wzToast("이미 추가된 스팟입니다", name); return; }
    if (it.picks.length >= 8) { wzToast("손픽은 최대 8개입니다", ""); return; }
    it.picks.push({ contentId, name, cat, imageUrl: img });
    it.picksDirty = true; markDirty();
    renderInspector(); renderScreen(); renderLists();
    row.classList.add("added");
    addBtn.innerHTML = `<svg class="bi chk" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>추가됨`;
    wzToast("스팟 추가", name);
    return;
  }
});

(function wirePicker() {
  const m = qs("pickermodal"); if (!m) return;
  m.addEventListener("click", (e) => { if (e.target === m) closePicker(); });
  m.querySelectorAll(".x").forEach((x) => x.addEventListener("click", closePicker));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePicker(); });
  const chips = m.querySelectorAll(".fchip");
  chips.forEach((c) => c.addEventListener("click", () => {
    chips.forEach((x) => x.classList.remove("on")); c.classList.add("on");
    const inp = m.querySelector(".search input"); if (inp && inp.value.trim()) runSpotSearch(inp.value.trim());
  }));
  const inp = m.querySelector(".search input");
  if (inp) inp.addEventListener("input", () => {
    clearTimeout(CU.searchTimer);
    const q = inp.value.trim();
    if (!q) { const r = m.querySelector(".results"); if (r) r.innerHTML = `<div class="estate"><div class="d">검색어를 입력하세요.</div></div>`; return; }
    CU.searchTimer = setTimeout(() => runSpotSearch(q), 250);
  });
})();

window.addEventListener("load", () => {
  if (!document.querySelector(".cu-page")) return;
  qs("tempSave").addEventListener("click", () => saveCuration(null, "임시저장됨"));
  qs("pubToggleBtn").addEventListener("click", () => {
    const it = current(); if (!it) return;
    saveCuration(!it.isPublished, it.isPublished ? "발행 취소됨" : "발행됨");
  });
  qs("revertBtn").addEventListener("click", revertCurrent);
  document.querySelectorAll("#viewToggle button").forEach((b) =>
    b.addEventListener("click", () => { if (b.classList.contains("disabled")) { wzToast("이 종류는 해당 화면이 없어요"); return; } setView(b.dataset.view); }));
  loadAll();
});
