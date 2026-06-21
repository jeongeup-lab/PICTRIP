// PicTrip ADMIN — shared demo behavior

// live clock
(function () {
  const el = document.getElementById("clock");
  if (!el) return;
  const p = (n) => String(n).padStart(2, "0");
  function tick() {
    const d = new Date();
    el.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} KST`;
  }
  tick();
  setInterval(tick, 1000);
})();

// animate coverage bars
window.addEventListener("load", () => {
  document.querySelectorAll(".bar i[data-w]").forEach((el, i) => {
    setTimeout(() => { el.style.width = el.dataset.w + "%"; }, 200 + i * 80);
  });
  // animate chart segments
  document.querySelectorAll(".chart .col").forEach((col, i) => {
    setTimeout(() => {
      col.querySelectorAll(".seg[data-h]").forEach((s) => { s.style.height = s.dataset.h + "px"; });
    }, 220 + i * 45);
  });
});

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

// trigger RUN buttons -> queue then route to jobs page
document.querySelectorAll("[data-job]").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    const job = btn.dataset.job;
    const orig = btn.textContent;
    btn.textContent = "QUEUED…";
    btn.disabled = true;
    toast(`수집 잡 큐 등록 →`, job);
    setTimeout(() => {
      // demo: navigate to collection history with the new run highlighted
      window.location.href = `history.html?started=${encodeURIComponent(job)}`;
    }, 1100);
  });
});

// log modal (수집 이력 → 상세 로그)
const SAMPLE_LOGS = {
  ok: `<span class="dim2">$ pictrip-data sync-daily --mode incremental</span>
<span class="dim2">[04:03:31]</span> watermark = 20260617041100
<span class="dim2">[04:03:32]</span> fetching areaBasedSyncList2 (국문 관광정보 서비스)
<span class="dim2">[04:05:10]</span> page 1..22 · 2,140 items
<span class="ok2">[04:08:40]</span> upsert: <span class="ok2">+184 inserted</span> · 1,902 updated · <span class="warn2">12 hidden</span>
<span class="ok2">[04:12:13]</span> done in 8m 41s · run #0481 <span class="ok2">SUCCESS</span>`,
  fail: `<span class="dim2">$ pictrip-data sync-daily --mode incremental</span>
<span class="dim2">[04:09:02]</span> watermark = 20260615041100
<span class="dim2">[04:09:03]</span> fetching areaBasedSyncList2 (국문 관광정보 서비스)
<span class="dim2">[04:10:18]</span> page 1..6 · 512 items
<span class="bad2">[04:10:20]</span> ERROR: TourAPI timeout after 30s (page 7)
<span class="bad2">[04:10:20]</span> retry 1/3 ... timeout
<span class="bad2">[04:10:20]</span> run #0479 <span class="bad2">FAILED</span> · rolled back, watermark unchanged`,
};
function openLog(kind, title) {
  let bg = document.getElementById("logmodal");
  if (!bg) return;
  bg.querySelector("[data-title]").textContent = title || "수집 로그";
  bg.querySelector(".log").innerHTML = SAMPLE_LOGS[kind] || SAMPLE_LOGS.ok;
  bg.classList.add("show");
}
function closeLog() {
  const bg = document.getElementById("logmodal");
  if (bg) bg.classList.remove("show");
}
document.querySelectorAll("[data-log]").forEach((row) => {
  row.addEventListener("click", () => openLog(row.dataset.log, row.dataset.title));
});
(function () {
  const bg = document.getElementById("logmodal");
  if (!bg) return;
  bg.addEventListener("click", (e) => { if (e.target === bg) closeLog(); });
  bg.querySelector(".x").addEventListener("click", closeLog);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeLog(); });
})();

// highlight a freshly-started job on jobs page
(function () {
  const params = new URLSearchParams(window.location.search);
  const started = params.get("started");
  if (!started) return;
  const row = document.querySelector(`tr[data-job="${started}"]`);
  if (row) {
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    row.style.transition = "background 1.4s";
    row.style.background = "var(--accent-soft)";
    setTimeout(() => (row.style.background = ""), 1800);
  }
  toast("새 수집 잡 시작됨 →", started);
})();
