// PicTrip ADMIN — 홈 큐레이션 편집기 (live fetch wiring, ADM-017)
//
// Replaces the former demo data layer with real calls to the five
// /admin/api/curation* endpoints while preserving the mockup markup/CSS.
// Shared helpers (escapeHtml, toast, adminFetch) come from admin.js, which is
// loaded first. adminFetch handles GET; PUTs go through adminFetchJSON below.

// ─── PUT helper (JSend, same-origin Basic-auth carried by the browser) ───────
// Mirrors admin.js's adminFetch but with a method + JSON body. Surfaces
// JSend error.code/message; attaches error.details for 422 field-level handling.
async function adminFetchJSON(path, method, body) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let json = null;
  try {
    json = await res.json();
  } catch (_) {
    /* non-JSON error body */
  }
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

// ─── module state ────────────────────────────────────────────────────────────
const CU = {
  list: { heroes: [], rails: [], editorial: [] }, // GET /curations grouped
  loadedId: null, // currently-open curation id
  detail: null, // working copy (edited in place)
  original: null, // pristine snapshot from server (for 되돌리기 / dirty diff)
  dirty: false,
  handpicksDirty: false,
  busy: false, // request in flight → disable saves
  pickerMode: null, // 'cover' | 'handpick'
  searchTimer: null,
};

// ─── small DOM helpers ───────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// Set a thumbnail-style element to a real KTO image URL (reference only — no
// download/store) or leave the placeholder pattern when null.
function setThumbImage(el, url) {
  if (!el) return;
  if (url) {
    el.style.backgroundImage = `url("${encodeURI(url)}")`;
    el.style.backgroundSize = "cover";
    el.style.backgroundPosition = "center";
    el.innerHTML = ""; // drop placeholder svg
  } else {
    el.style.backgroundImage = "";
  }
}

// ─── dirty tracking ──────────────────────────────────────────────────────────
function markDirty() {
  CU.dirty = true;
  const scope = $("[data-editor]");
  if (!scope) return;
  const d = scope.querySelector("[data-dirty]");
  const s = scope.querySelector("[data-saved]");
  if (d) d.style.display = "flex";
  if (s) s.style.display = "none";
}

function clearDirty(savedLabel) {
  CU.dirty = false;
  CU.handpicksDirty = false;
  const scope = $("[data-editor]");
  if (!scope) return;
  const d = scope.querySelector("[data-dirty]");
  const s = scope.querySelector("[data-saved]");
  if (d) d.style.display = "none";
  if (s) {
    s.style.display = "";
    if (savedLabel) s.textContent = savedLabel;
  }
}

// disable/enable the save-related buttons while a request is in flight
function setBusy(on) {
  CU.busy = on;
  const scope = $("[data-editor]");
  if (!scope) return;
  $$(".editor-foot button, .pub", scope).forEach((b) => {
    if (on) b.setAttribute("aria-disabled", "true");
    else b.removeAttribute("aria-disabled");
    if (b.tagName === "BUTTON") b.disabled = on;
  });
}

// ─── preview render (GET /admin/api/curations) ───────────────────────────────
function heroCardHtml(it) {
  const titleHtml = escapeHtml(it.title || "").replace(/\n/g, "<br>");
  const draft = !it.isPublished;
  return (
    `<div class="pv-hero${draft ? " is-draft" : ""}" data-item data-id="${escapeHtml(it.id)}" tabindex="0">` +
    `<div class="img">` +
    `<div class="scrim"></div>` +
    (draft ? `<span class="draft">초안</span>` : "") +
    `<span class="pubdot ${draft ? "off" : "on"}" title="${draft ? "초안" : "발행"}"></span>` +
    `<div class="ttl">${titleHtml}</div>` +
    `</div>` +
    `<div class="ft"><span class="slot-no">${escapeHtml(it.position)}</span>` +
    `<span class="rg">${escapeHtml(it.subtitle || it.slug || "")}</span></div>` +
    `</div>`
  );
}

function railCardHtml(it) {
  const draft = !it.isPublished;
  return (
    `<div class="pv-rail${draft ? " is-draft" : ""}" data-item data-id="${escapeHtml(it.id)}" tabindex="0">` +
    `<div class="rh"><span class="nm">${escapeHtml(it.title || "")}</span>` +
    `<span class="pubdot ${draft ? "off" : "on"}" title="${draft ? "초안" : "발행"}"></span></div>` +
    `<div class="cards"><div class="more auto">${escapeHtml(it.subtitle || "무드 레일")}</div></div>` +
    `</div>`
  );
}

function renderPreview() {
  const heroesWrap = $(".pv-heroes");
  const railsWrap = $(".pv-rails");
  const indWrap = $(".pv-ind");
  if (heroesWrap) {
    heroesWrap.innerHTML = CU.list.heroes.map(heroCardHtml).join("");
    if (indWrap) {
      indWrap.innerHTML = CU.list.heroes
        .map((_, i) => (i === 0 ? `<i class="on"></i>` : `<i></i>`))
        .join("");
    }
  }
  if (railsWrap) {
    railsWrap.innerHTML = CU.list.rails.map(railCardHtml).join("");
  }
  // header counts
  const hcount = $(".pv-wrap .hcount");
  if (hcount) {
    hcount.innerHTML = `히어로 <b>${CU.list.heroes.length}</b> · 레일 <b>${CU.list.rails.length}</b>`;
  }
  wirePreviewSelection();
  highlightActive();
}

function showPreviewLoading() {
  const heroesWrap = $(".pv-heroes");
  if (heroesWrap) {
    heroesWrap.innerHTML = Array.from({ length: 6 })
      .map(
        () =>
          `<div class="pv-hero"><div class="img"></div><div class="ft"><span class="sk line sm"></span></div></div>`,
      )
      .join("");
  }
  const railsWrap = $(".pv-rails");
  if (railsWrap) {
    railsWrap.innerHTML = Array.from({ length: 3 })
      .map(() => `<div class="pv-rail"><div class="rh"><span class="sk line"></span></div></div>`)
      .join("");
  }
}

function showPreviewError(msg) {
  const body = $(".pv-wrap .card-b");
  if (!body) return;
  body.innerHTML =
    `<div class="estate">` +
    `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><circle cx="12" cy="16" r=".6" fill="currentColor" stroke="none"/></svg>` +
    `<div class="t">불러오지 못했습니다</div>` +
    `<div class="d">${escapeHtml(msg)}</div>` +
    `<button class="btn ghost sm" type="button" id="cu-retry" style="margin-top:14px">다시 시도</button>` +
    `</div>`;
  const r = $("#cu-retry");
  if (r) r.addEventListener("click", loadCurationList);
}

async function loadCurationList() {
  showPreviewLoading();
  try {
    const data = await adminFetch("/admin/api/curations");
    CU.list = {
      heroes: data.heroes || [],
      rails: data.rails || [],
      editorial: data.editorial || [],
    };
    renderPreview();
    // auto-open the first hero (or first rail) so the editor isn't empty
    const first = CU.list.heroes[0] || CU.list.rails[0] || CU.list.editorial[0];
    if (first) loadDetail(first.id);
    else showEditorEmpty();
  } catch (err) {
    showPreviewError(err.message);
  }
}

// ─── preview selection ───────────────────────────────────────────────────────
function wirePreviewSelection() {
  const group = $(".pv-wrap[data-selectable]");
  if (!group) return;
  $$("[data-item]", group).forEach((it) => {
    it.addEventListener("click", () => {
      const id = it.dataset.id;
      if (id != null) loadDetail(Number(id));
    });
    it.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        it.click();
      }
    });
  });
}

function highlightActive() {
  const group = $(".pv-wrap[data-selectable]");
  if (!group) return;
  $$("[data-item]", group).forEach((x) => x.classList.remove("active"));
  if (CU.loadedId == null) return;
  const el = group.querySelector(`[data-item][data-id="${CU.loadedId}"]`);
  if (el) el.classList.add("active");
}

// ─── editor: detail load + populate (GET /admin/api/curations/{id}) ──────────
function showEditorEmpty() {
  const body = $(".editor-card .card-b");
  if (!body) return;
  body.innerHTML =
    `<div class="estate">` +
    `<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="11" height="6" rx="1.5"/></svg>` +
    `<div class="t">편집할 큐레이션이 없습니다</div>` +
    `<div class="d">위 미리보기에서 카드를 선택하세요.</div>` +
    `</div>`;
}

async function loadDetail(id) {
  CU.loadedId = id;
  highlightActive();
  const titleH = $(".editor-card .card-h h2");
  if (titleH) titleH.textContent = "불러오는 중…";
  try {
    const data = await adminFetch(`/admin/api/curations/${id}`);
    CU.detail = data;
    CU.original = JSON.parse(JSON.stringify(data));
    populateEditor(data);
    clearDirty("불러옴");
  } catch (err) {
    if (err.message && /404/.test(err.message)) {
      if (titleH) titleH.textContent = "찾을 수 없음";
      toast("상세를 불러오지 못했습니다", err.message);
      return;
    }
    if (titleH) titleH.textContent = "편집";
    toast("상세를 불러오지 못했습니다", err.message);
  }
}

const TYPE_LABEL = { region: "지역 히어로", mood: "무드 레일", editorial: "에디토리얼" };

function populateEditor(d) {
  const card = $(".editor-card");
  if (!card) return;
  card.setAttribute("data-id", d.id);

  // title in header + type/scope badge (read-only)
  const titleH = card.querySelector(".card-h h2");
  if (titleH) titleH.textContent = `편집 · ${d.title || d.slug || ""}`;
  const badge = card.querySelector(".tbadge");
  if (badge) {
    badge.textContent = `${TYPE_LABEL[d.type] || d.type} · 슬롯 ${d.position}`;
  }

  // publish switch
  const pub = card.querySelector(".pub");
  if (pub) {
    pub.classList.toggle("on", !!d.isPublished);
    pub.setAttribute("aria-checked", d.isPublished ? "true" : "false");
    pub.dataset.cu = d.title || d.slug || "";
    const lbl = pub.querySelector(".lbl");
    if (lbl) lbl.textContent = d.isPublished ? "발행" : "초안";
  }

  // copy fields (textContent / value — never innerHTML for user input)
  const titleTa = card.querySelector("textarea.ta.title");
  if (titleTa) titleTa.value = d.title || "";
  // subtitle/lead share the .inp class — resolve each by its <label> text.
  const subtitleInp = findInpByLabel(card, "부제");
  if (subtitleInp) subtitleInp.value = d.subtitle || "";
  const leadInp = findInpByLabel(card, "리드문");
  if (leadInp) leadInp.value = d.lead || "";
  const introTa = card.querySelector('textarea.ta[data-count="cc-intro"]');
  if (introTa) introTa.value = d.intro || "";

  // cover spot
  renderCover(d.coverSpot);

  // position
  const posInp = card.querySelector(".orderfield .inp");
  if (posInp) posInp.value = d.position;

  // handpicks
  renderHandpicks(d.handpicks || []);

  // refresh char counters
  updateCounters();
}

// find a .field's .inp by its <label> text (subtitle/lead share the .inp class)
function findInpByLabel(card, labelText) {
  const fields = $$(".ecol .field", card);
  for (const f of fields) {
    const lab = f.querySelector("label");
    if (lab && lab.textContent.trim().startsWith(labelText)) {
      return f.querySelector(".inp");
    }
  }
  return null;
}

function renderCover(cover) {
  const card = $(".editor-card");
  if (!card) return;
  const pspot = card.querySelector(".pspot:not(.draggable)"); // the cover pspot
  if (!pspot) return;
  const thumb = pspot.querySelector(".thumb.cover");
  const nm = pspot.querySelector(".meta .nm");
  const sub = pspot.querySelector(".meta .sub");
  if (cover) {
    if (thumb) setThumbImage(thumb, cover.imageUrl);
    if (nm) nm.textContent = cover.name || "";
    if (sub) sub.textContent = `contentId ${cover.contentId}`;
    pspot.dataset.contentId = cover.contentId;
  } else {
    if (thumb) setThumbImage(thumb, null);
    if (nm) nm.textContent = "표지 미지정";
    if (sub) sub.textContent = "표지 스팟을 선택하세요";
    delete pspot.dataset.contentId;
  }
}

function handpickRowHtml(h, idx) {
  return (
    `<div class="pspot draggable" data-content-id="${escapeHtml(h.contentId)}">` +
    `<span class="handle" aria-label="순서 이동"><svg viewBox="0 0 24 24"><circle cx="9" cy="6" r="1.3"/><circle cx="15" cy="6" r="1.3"/><circle cx="9" cy="12" r="1.3"/><circle cx="15" cy="12" r="1.3"/><circle cx="9" cy="18" r="1.3"/><circle cx="15" cy="18" r="1.3"/></svg></span>` +
    `<span class="slot-no">${idx + 1}</span>` +
    `<span class="thumb" style="width:38px;height:38px"><svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8"/></svg></span>` +
    `<span class="meta"><span class="nm">${escapeHtml(h.name || "")}</span>` +
    `<span class="sub">${escapeHtml(h.category || "스팟")} · contentId ${escapeHtml(h.contentId)}</span></span>` +
    `<button class="rm" type="button" aria-label="제거"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>` +
    `</div>`
  );
}

function renderHandpicks(handpicks) {
  const list = $(".picklist[data-sortable]");
  if (!list) return;
  list.innerHTML = handpicks.map((h, i) => handpickRowHtml(h, i)).join("");
  // apply thumbnail images after injecting (background-image, not innerHTML)
  $$(".pspot.draggable", list).forEach((row, i) => {
    const url = handpicks[i] && handpicks[i].imageUrl;
    if (url) setThumbImage(row.querySelector(".thumb"), url);
  });
  wireHandpickRows();
  updateHandpickCount();
}

function updateHandpickCount() {
  const list = $(".picklist[data-sortable]");
  const countEl = $(".ecol .elabel .count");
  if (list && countEl) {
    const n = $$(".pspot.draggable", list).length;
    countEl.textContent = `${n} / 8`;
  }
}

function renumber(list) {
  if (!list) return;
  $$(".slot-no", list).forEach((s, i) => {
    s.textContent = i + 1;
  });
}

// current handpick contentIds in DOM order
function currentSpotIds() {
  const list = $(".picklist[data-sortable]");
  if (!list) return [];
  return $$(".pspot.draggable", list).map((r) => r.dataset.contentId);
}

// ─── handpick row wiring (remove + drag reorder) ─────────────────────────────
function wireHandpickRows() {
  const list = $(".picklist[data-sortable]");
  if (!list) return;
  let dragEl = null;
  $$(".pspot.draggable", list).forEach((row) => {
    const handle = row.querySelector(".handle");
    if (handle) {
      handle.addEventListener("mousedown", () => row.setAttribute("draggable", "true"));
    }
    row.addEventListener("dragstart", () => {
      dragEl = row;
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => {
      row.classList.remove("dragging");
      row.removeAttribute("draggable");
      dragEl = null;
      renumber(list);
      CU.handpicksDirty = true;
      markDirty();
    });
    row.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (!dragEl || dragEl === row) return;
      const rect = row.getBoundingClientRect();
      const after = e.clientY > rect.top + rect.height / 2;
      list.insertBefore(dragEl, after ? row.nextSibling : row);
    });
  });
}

// remove handpick (delegated)
document.addEventListener("click", (e) => {
  const rm = e.target.closest(".picklist .pspot .rm");
  if (!rm) return;
  const row = rm.closest(".pspot");
  const list = row.closest("[data-sortable]");
  row.style.transition = "opacity .15s, transform .15s";
  row.style.opacity = "0";
  row.style.transform = "translateX(-8px)";
  setTimeout(() => {
    row.remove();
    renumber(list);
    updateHandpickCount();
    CU.handpicksDirty = true;
    markDirty();
  }, 160);
});

// ─── publish toggle (click + keyboard) ───────────────────────────────────────
function togglePub(t) {
  if (CU.busy) return;
  t.classList.toggle("on");
  const on = t.classList.contains("on");
  t.setAttribute("aria-checked", on ? "true" : "false");
  const lbl = t.querySelector(".lbl");
  if (lbl) lbl.textContent = on ? "발행" : "초안";
  if (CU.detail) CU.detail.isPublished = on;
  markDirty();
  if (window.toast) toast(on ? "발행 상태로 전환" : "초안으로 전환", t.dataset.cu || "");
}
document.addEventListener("click", (e) => {
  const t = e.target.closest(".pub");
  if (t) togglePub(t);
});
document.addEventListener("keydown", (e) => {
  if ((e.key === " " || e.key === "Enter") && e.target.classList?.contains("pub")) {
    e.preventDefault();
    togglePub(e.target);
  }
});

// ─── char counters ───────────────────────────────────────────────────────────
function updateCounters() {
  $$("[data-count]").forEach((ta) => {
    const out = document.querySelector(`#${ta.dataset.count}`);
    if (out) out.textContent = `${(ta.value || "").length}자`;
  });
}

// ─── position up/down ────────────────────────────────────────────────────────
(function wirePosition() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".orderfield .iconbtn");
    if (!btn) return;
    const inp = $(".orderfield .inp");
    if (!inp) return;
    const up = btn.getAttribute("aria-label") === "앞으로";
    let v = parseInt(inp.value, 10);
    if (isNaN(v)) v = 0;
    v = up ? Math.max(0, v - 1) : v + 1;
    inp.value = v;
    markDirty();
  });
})();

// ─── generic input → dirty + counters ────────────────────────────────────────
document.addEventListener("input", (e) => {
  const scope = e.target.closest("[data-editor]");
  if (!scope) return;
  if (e.target.matches("input, textarea")) {
    markDirty();
    if (e.target.hasAttribute("data-count")) updateCounters();
  }
});

// ─── read current editor copy back into a payload ────────────────────────────
function collectUpdatePayload(overrides) {
  const card = $(".editor-card");
  const titleTa = card.querySelector("textarea.ta.title");
  const introTa = card.querySelector('textarea.ta[data-count="cc-intro"]');
  const subtitleInp = findInpByLabel(card, "부제");
  const leadInp = findInpByLabel(card, "리드문");
  const posInp = card.querySelector(".orderfield .inp");
  const pub = card.querySelector(".pub");
  const coverPspot = card.querySelector(".pspot:not(.draggable)");
  const coverId = coverPspot ? coverPspot.dataset.contentId || null : null;
  let pos = parseInt(posInp ? posInp.value : "0", 10);
  if (isNaN(pos)) pos = CU.detail ? CU.detail.position : 0;
  const payload = {
    title: titleTa ? titleTa.value : "",
    subtitle: subtitleInp ? subtitleInp.value || null : null,
    lead: leadInp ? leadInp.value || null : null,
    intro: introTa ? introTa.value || null : null,
    coverSpotId: coverId,
    isPublished: pub ? pub.classList.contains("on") : false,
    position: pos,
  };
  return Object.assign(payload, overrides || {});
}

// clear any prior field-level error markers
function clearFieldErrors() {
  $$(".field .field-err").forEach((el) => el.remove());
  $$(".field.has-err").forEach((el) => el.classList.remove("has-err"));
}

// surface 422 ADMIN_VALIDATION details next to fields (best-effort) + toast
function showValidationErrors(err) {
  clearFieldErrors();
  const details = err.details || [];
  const fieldMap = {
    title: "제목",
    subtitle: "부제",
    lead: "리드문",
    intro: "소개",
    position: "노출 순서",
  };
  // Fields that have no dedicated DOM label but need a clear toast message.
  const toastOnlyMap = {
    coverSpotId: "표지 스팟",
    spotIds: "손픽 스팟",
  };
  let surfaced = 0;
  details.forEach((det) => {
    const fieldKey = (det.field || "").split(".").pop();
    const labelText = fieldMap[fieldKey];
    if (labelText) {
      const card = $(".editor-card");
      const lab = $$(".ecol .field label", card).find((l) =>
        l.textContent.trim().startsWith(labelText),
      );
      if (lab) {
        const field = lab.closest(".field");
        field.classList.add("has-err");
        const msg = document.createElement("div");
        msg.className = "charcount field-err";
        msg.style.color = "var(--bad, #c0392b)";
        msg.textContent = escapeHtml(det.issue || det.message || "입력값을 확인하세요");
        field.appendChild(msg);
        surfaced++;
      }
    } else if (toastOnlyMap[fieldKey]) {
      // coverSpotId / spotIds — show a named toast so the user knows which field failed.
      toast(
        `${toastOnlyMap[fieldKey]} 오류`,
        det.issue || det.message || "입력값을 확인하세요",
      );
      surfaced++;
    }
  });
  toast(
    surfaced ? "입력값을 확인하세요" : "검증 오류",
    err.message || "ADMIN_VALIDATION",
  );
}

// ─── save flows ──────────────────────────────────────────────────────────────
// Sends PUT /curations/{id} (copy/cover/position/publish) then, if handpicks
// changed, PUT /curations/{id}/spots. Returns the refreshed detail.
async function saveCuration(overrides, savedLabel) {
  if (CU.busy || CU.loadedId == null) return;
  clearFieldErrors();
  setBusy(true);
  const id = CU.loadedId;
  try {
    const payload = collectUpdatePayload(overrides);
    let detail = await adminFetchJSON(`/admin/api/curations/${id}`, "PUT", payload);

    if (CU.handpicksDirty) {
      const spotIds = currentSpotIds();
      const res = await adminFetchJSON(`/admin/api/curations/${id}/spots`, "PUT", {
        spotIds,
      });
      // /spots returns { handpicks: [...] } — merge into the detail we render
      if (res && res.handpicks) detail.handpicks = res.handpicks;
    }

    CU.detail = detail;
    CU.original = JSON.parse(JSON.stringify(detail));
    populateEditor(detail);
    clearDirty(savedLabel);
    // reflect publish/position/title changes back into the preview list
    syncListItem(detail);
    renderPreview();
    const stamp = `${savedLabel} · ${nowLabel()}`;
    const savedEl = $(".editor-card [data-saved]");
    if (savedEl) savedEl.textContent = stamp;
    const globalSaved = $(".page-head-row [data-saved]");
    if (globalSaved && detail.isPublished) globalSaved.textContent = `마지막 발행 · ${nowLabel()}`;
    toast(savedLabel, detail.title || "");
  } catch (err) {
    if (err.status === 422 || err.code === "ADMIN_VALIDATION") {
      showValidationErrors(err);
    } else if (err.status === 404 || err.code === "ADMIN_CURATION_NOT_FOUND") {
      toast("큐레이션을 찾을 수 없습니다", err.message);
    } else {
      toast("저장 실패", err.message || "");
    }
  } finally {
    setBusy(false);
  }
}

function nowLabel() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

// keep the in-memory list (and thus preview) in sync after a save
function syncListItem(detail) {
  const groups = [CU.list.heroes, CU.list.rails, CU.list.editorial];
  for (const g of groups) {
    const it = g.find((x) => x.id === detail.id);
    if (it) {
      it.title = detail.title;
      it.subtitle = detail.subtitle;
      it.isPublished = detail.isPublished;
      it.position = detail.position;
    }
  }
}

// 임시저장 — save with whatever publish state is currently set
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-save]")) {
    e.preventDefault();
    saveCuration(null, "임시저장됨");
  }
});

// editor-foot buttons: "초안으로" (unpublish) + "저장 후 발행" (publish)
(function wireFootButtons() {
  const card = $(".editor-card");
  if (!card) return;
  const foot = card.querySelector(".editor-foot");
  if (!foot) return;
  foot.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn || btn.hasAttribute("data-save")) return;
    const label = btn.textContent.trim();
    if (label.startsWith("초안으로")) {
      saveCuration({ isPublished: false }, "초안으로 전환됨");
    } else if (label.startsWith("저장 후 발행")) {
      saveCuration({ isPublished: true }, "저장 후 발행됨");
    }
  });
})();

// ─── savebar (page-level): 되돌리기 + 이 큐레이션 발행 ──────────────────────────
(function wireSavebar() {
  const bar = $(".page-head-row .savebar");
  if (!bar) return;
  bar.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    const label = btn.textContent.trim();
    if (label.startsWith("되돌리기")) {
      // discard local edits — reload the open curation from the server
      if (CU.loadedId != null) {
        loadDetail(CU.loadedId);
        toast("서버 상태로 되돌림", "");
      }
    } else if (label.startsWith("이 큐레이션 발행")) {
      publishAll();
    }
  });
})();

// 전체 발행 — publishes the currently-loaded/edited curation only.
// A true "publish everything" would PUT every curation; that risks clobbering
// other rows' copy with stale list-only data (the list endpoint lacks lead/intro/
// cover), so we honestly scope this to the open editor: save it published.
async function publishAll() {
  if (CU.loadedId == null) {
    toast("발행할 큐레이션이 없습니다", "");
    return;
  }
  if (!window.confirm("현재 편집 중인 큐레이션을 발행합니다. 계속할까요?")) return;
  await saveCuration({ isPublished: true }, "발행됨");
}

// ─── spot picker modal (cover + handpick modes) ──────────────────────────────
function openPicker(mode) {
  CU.pickerMode = mode;
  const bg = $("#pickermodal");
  if (!bg) return;
  // adjust modal title for the mode
  const h3 = bg.querySelector(".mh-titles h3");
  const sub = bg.querySelector(".mh-titles .mh-sub");
  if (h3) h3.textContent = mode === "cover" ? "표지 스팟 선택" : "스팟 추가";
  if (sub) {
    sub.textContent =
      mode === "cover" ? "이 큐레이션의 표지로 쓸 관광지를 검색합니다" : "손픽 스팟에 넣을 관광지를 검색해 추가합니다";
  }
  // reset search results to a hint
  const results = bg.querySelector(".results");
  if (results) {
    results.innerHTML = `<div class="estate"><div class="d">검색어를 입력하세요.</div></div>`;
  }
  bg.classList.add("show");
  const inp = bg.querySelector(".search input");
  if (inp) {
    inp.value = "";
    setTimeout(() => inp.focus(), 60);
  }
}
function closePicker() {
  const bg = $("#pickermodal");
  if (bg) bg.classList.remove("show");
}

// decide picker mode from which trigger was clicked
document.addEventListener("click", (e) => {
  const trigger = e.target.closest("[data-open-picker]");
  if (!trigger) return;
  e.preventDefault();
  const mode = trigger.classList.contains("addspot") ? "handpick" : "cover";
  openPicker(mode);
});

(function wirePickerModal() {
  const bg = $("#pickermodal");
  if (!bg) return;
  bg.addEventListener("click", (e) => {
    if (e.target === bg) closePicker();
  });
  bg.querySelectorAll(".x").forEach((x) => x.addEventListener("click", closePicker));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePicker();
  });

  // region filter chips → re-run search with region scope
  const chips = bg.querySelectorAll(".fchip");
  chips.forEach((c) =>
    c.addEventListener("click", () => {
      chips.forEach((x) => x.classList.remove("on"));
      c.classList.add("on");
      const inp = bg.querySelector(".search input");
      if (inp && inp.value.trim()) runSpotSearch(inp.value.trim());
    }),
  );

  // debounced search on typing
  const inp = bg.querySelector(".search input");
  if (inp) {
    inp.addEventListener("input", () => {
      clearTimeout(CU.searchTimer);
      const q = inp.value.trim();
      if (!q) {
        const results = bg.querySelector(".results");
        if (results)
          results.innerHTML = `<div class="estate"><div class="d">검색어를 입력하세요.</div></div>`;
        return;
      }
      CU.searchTimer = setTimeout(() => runSpotSearch(q), 250);
    });
  }
})();

// the active region filter chip's label maps to a region query param (best-effort)
function activeRegionParam() {
  const chip = $("#pickermodal .fchip.on");
  if (!chip) return "";
  const label = chip.textContent.trim();
  // "전체" and category-like chips ("자연","해변","카페") aren't regions → skip
  const regionChips = ["제주", "부산", "강원", "서울", "경기", "경주", "전주", "강릉", "여수"];
  return regionChips.includes(label) ? label : "";
}

async function runSpotSearch(q) {
  const bg = $("#pickermodal");
  const results = bg ? bg.querySelector(".results") : null;
  if (!results) return;
  results.innerHTML = `<div class="estate"><div class="d">검색 중…</div></div>`;
  try {
    const region = activeRegionParam();
    const url =
      `/admin/api/spots/search?q=${encodeURIComponent(q)}` +
      (region ? `&region=${encodeURIComponent(region)}` : "");
    const data = await adminFetch(url);
    renderSearchResults(data.spots || []);
  } catch (err) {
    results.innerHTML = `<div class="estate"><div class="d">${escapeHtml(err.message)}</div></div>`;
  }
}

function renderSearchResults(spots) {
  const bg = $("#pickermodal");
  const results = bg ? bg.querySelector(".results") : null;
  if (!results) return;
  if (!spots.length) {
    results.innerHTML = `<div class="estate"><div class="d">검색 결과가 없습니다.</div></div>`;
    return;
  }
  // which contentIds are already picked (handpick mode) → mark as added
  const picked = new Set(currentSpotIds());
  results.innerHTML = spots
    .map((s) => {
      const region = s.regionName || s.regionCd || "";
      const already = CU.pickerMode === "handpick" && picked.has(s.contentId);
      const subParts = [region, `contentId ${escapeHtml(s.contentId)}`].filter(Boolean);
      return (
        `<div class="rspot${already ? " added" : ""}" data-content-id="${escapeHtml(s.contentId)}" data-name="${escapeHtml(s.name || "")}" data-img="${escapeHtml(s.imageUrl || "")}" data-region="${escapeHtml(region)}">` +
        `<span class="thumb"><svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8"/></svg></span>` +
        `<span class="meta"><span class="nm">${escapeHtml(s.name || "")}</span>` +
        `<span class="sub">${subParts.join(" · ")}</span></span>` +
        `<button class="btn ghost add" type="button">` +
        (already ? `<svg class="bi chk" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>추가됨` : "추가") +
        `</button>`
      );
    })
    .join("");
  // apply real thumbnails
  $$(".rspot", results).forEach((row) => {
    const img = row.dataset.img;
    if (img) setThumbImage(row.querySelector(".thumb"), img);
  });
}

// pick a result → cover-set or handpick-append depending on mode
document.addEventListener("click", (e) => {
  const addBtn = e.target.closest("#pickermodal .rspot .add");
  if (!addBtn) return;
  const row = addBtn.closest(".rspot");
  const contentId = row.dataset.contentId;
  const name = row.dataset.name;
  const img = row.dataset.img || null;
  const region = row.dataset.region || "";

  if (CU.pickerMode === "cover") {
    renderCover({ contentId, name, imageUrl: img });
    markDirty();
    toast("표지 스팟 설정", name);
    closePicker();
    return;
  }

  // handpick mode
  if (row.classList.contains("added")) return;
  const list = $(".picklist[data-sortable]");
  const ids = currentSpotIds();
  if (ids.includes(contentId)) {
    toast("이미 추가된 스팟입니다", name);
    return;
  }
  if (ids.length >= 8) {
    toast("손픽은 최대 8개입니다", "");
    return;
  }
  const idx = ids.length;
  list.insertAdjacentHTML(
    "beforeend",
    handpickRowHtml({ contentId, name, category: null }, idx),
  );
  const newRow = list.lastElementChild;
  if (img) setThumbImage(newRow.querySelector(".thumb"), img);
  wireHandpickRows();
  renumber(list);
  updateHandpickCount();
  CU.handpicksDirty = true;
  markDirty();
  // mark this result row as added
  row.classList.add("added");
  addBtn.innerHTML = `<svg class="bi chk" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>추가됨`;
  toast("손픽 스팟에 추가", name);
});

// ─── page init ───────────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  if ($(".cu-page")) {
    loadCurationList();
  }
});
