// PicTrip ADMIN — 홈 큐레이션 편집기 (demo behavior, hi-fi)

// publish toggle (click + keyboard, aria-checked sync)
function togglePub(t) {
  t.classList.toggle("on");
  const on = t.classList.contains("on");
  t.setAttribute("aria-checked", on ? "true" : "false");
  const lbl = t.querySelector(".lbl");
  if (lbl) lbl.textContent = on ? "발행" : "초안";
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

// spot picker modal open/close
function openPicker() {
  const bg = document.getElementById("pickermodal");
  if (bg) {
    bg.classList.add("show");
    const inp = bg.querySelector(".search input");
    if (inp) setTimeout(() => inp.focus(), 60);
  }
}
function closePicker() {
  const bg = document.getElementById("pickermodal");
  if (bg) bg.classList.remove("show");
}
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-open-picker]")) { e.preventDefault(); openPicker(); }
});
(function () {
  const bg = document.getElementById("pickermodal");
  if (!bg) return;
  bg.addEventListener("click", (e) => { if (e.target === bg) closePicker(); });
  bg.querySelectorAll(".x").forEach((x) => x.addEventListener("click", closePicker));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePicker(); });
  // filter chips
  const chips = bg.querySelectorAll(".fchip");
  chips.forEach((c) => c.addEventListener("click", () => {
    chips.forEach((x) => x.classList.remove("on"));
    c.classList.add("on");
  }));
  // add-to-list demo
  bg.querySelectorAll(".rspot .add").forEach((b) => {
    b.addEventListener("click", () => {
      const row = b.closest(".rspot");
      if (row.classList.contains("added")) return;
      row.classList.add("added");
      b.textContent = "추가됨";
      if (window.toast) toast("손픽 스팟에 추가", row.querySelector(".nm")?.textContent || "");
    });
  });
})();

// renumber slot indices in a pick list
function renumber(list) {
  if (!list) return;
  list.querySelectorAll(".slot-no").forEach((s, i) => { s.textContent = i + 1; });
}

// remove picked spot
document.addEventListener("click", (e) => {
  const rm = e.target.closest(".pspot .rm");
  if (rm) {
    const row = rm.closest(".pspot");
    const list = row.closest("[data-sortable]");
    row.style.transition = "opacity .15s, transform .15s";
    row.style.opacity = "0"; row.style.transform = "translateX(-8px)";
    setTimeout(() => { row.remove(); renumber(list); }, 160);
  }
});

// drag-handle reorder affordance (HTML5 DnD demo within each sortable list)
document.querySelectorAll("[data-sortable]").forEach((list) => {
  let dragEl = null;
  list.querySelectorAll(".pspot.draggable").forEach((row) => {
    const handle = row.querySelector(".handle");
    if (handle) handle.addEventListener("mousedown", () => { row.setAttribute("draggable", "true"); });
    row.addEventListener("dragstart", () => { dragEl = row; row.classList.add("dragging"); });
    row.addEventListener("dragend", () => {
      row.classList.remove("dragging"); row.removeAttribute("draggable"); dragEl = null; renumber(list);
    });
    row.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (!dragEl || dragEl === row) return;
      const rect = row.getBoundingClientRect();
      const after = e.clientY > rect.top + rect.height / 2;
      list.insertBefore(dragEl, after ? row.nextSibling : row);
    });
  });
});

// char counters
document.querySelectorAll("[data-count]").forEach((ta) => {
  const out = document.querySelector(`#${ta.dataset.count}`);
  const upd = () => { if (out) out.textContent = `${ta.value.length}자`; };
  ta.addEventListener("input", upd); upd();
});

// dirty-state demo: mark editor dirty on any input
document.querySelectorAll("[data-editor]").forEach((scope) => {
  const dirty = scope.querySelector("[data-dirty]");
  const saved = scope.querySelector("[data-saved]");
  scope.querySelectorAll("input, textarea").forEach((el) => {
    el.addEventListener("input", () => {
      if (dirty) dirty.style.display = "flex";
      if (saved) saved.style.display = "none";
    });
  });
  const saveBtn = scope.querySelector("[data-save]");
  if (saveBtn) saveBtn.addEventListener("click", () => {
    if (dirty) dirty.style.display = "none";
    if (saved) { saved.style.display = ""; saved.textContent = "방금 저장됨"; }
    if (window.toast) toast("임시저장됨", "draft");
  });
});

// preview-card selection highlight (heroes + rails)
document.querySelectorAll("[data-selectable]").forEach((group) => {
  group.querySelectorAll("[data-item]").forEach((it) => {
    it.setAttribute("tabindex", "0");
    it.addEventListener("click", () => {
      group.querySelectorAll("[data-item]").forEach((x) => x.classList.remove("active"));
      it.classList.add("active");
    });
    it.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); it.click(); }
    });
  });
});
