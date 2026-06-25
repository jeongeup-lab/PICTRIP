// PicTrip ADMIN — 홈 큐레이션 편집기 (demo behavior, low-fi)

// publish toggle
document.addEventListener("click", (e) => {
  const t = e.target.closest(".pub");
  if (t) {
    t.classList.toggle("on");
    const on = t.classList.contains("on");
    t.querySelector(".lbl").textContent = on ? "발행" : "초안";
    if (window.toast) toast(on ? "발행 상태로 전환" : "초안으로 전환", t.dataset.cu || "");
  }
});

// spot picker modal open/close
function openPicker() {
  const bg = document.getElementById("pickermodal");
  if (bg) bg.classList.add("show");
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
  const x = bg.querySelector(".x");
  if (x) x.addEventListener("click", closePicker);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePicker(); });
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

// remove picked spot
document.addEventListener("click", (e) => {
  const rm = e.target.closest(".pspot .rm");
  if (rm) {
    const row = rm.closest(".pspot");
    row.style.transition = "opacity .15s, transform .15s";
    row.style.opacity = "0"; row.style.transform = "translateX(-8px)";
    setTimeout(() => row.remove(), 160);
  }
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
    if (window.toast) toast("저장됨", "draft");
  });
});

// slide-over (variant C)
function openSlide() { const b = document.getElementById("slideover"); const bg = document.getElementById("slideover-bg");
  if (b) b.classList.add("show"); if (bg) bg.classList.add("show"); }
function closeSlide() { const b = document.getElementById("slideover"); const bg = document.getElementById("slideover-bg");
  if (b) b.classList.remove("show"); if (bg) bg.classList.remove("show"); }
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-open-slide]")) { e.preventDefault(); openSlide(); }
  if (e.target.closest("[data-close-slide]")) { e.preventDefault(); closeSlide(); }
  if (e.target.id === "slideover-bg") closeSlide();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSlide(); });

// list/card selection highlight (A & C & B previews)
document.querySelectorAll("[data-selectable]").forEach((group) => {
  group.querySelectorAll("[data-item]").forEach((it) => {
    it.addEventListener("click", () => {
      group.querySelectorAll("[data-item]").forEach((x) => x.classList.remove("active"));
      it.classList.add("active");
    });
  });
});
