const API = "https://api.pictrip.org/v1/explore";
const PROXY = "https://img.pictrip.org";
const WIDTHS = [330, 500, 960, 1280];
const CONCURRENCY = 20;

async function collectImageUrls() {
  const urls = [];
  let cursor = null;
  for (let page = 0; page < 100; page += 1) {
    const qs = new URLSearchParams({ limit: "60", seed: "warm" });
    if (cursor) qs.set("cursor", cursor);
    const res = await fetch(`${API}?${qs}`);
    const { data } = await res.json();
    urls.push(...data.items.map((i) => i.imageUrl));
    if (!data.hasMore) break;
    cursor = data.nextCursor;
  }
  return urls;
}

function variants(url) {
  const m = /^(.*)\/(\d+)px-([^/]+)$/.exec(url);
  if (!m) return [url];
  return WIDTHS.map((w) => `${m[1]}/${w}px-${m[3]}`);
}

function toProxy(url) {
  return url.replace(/^https?:\/\//, `${PROXY}/`);
}

const urls = await collectImageUrls();
const targets = [...new Set(urls.flatMap(variants).map(toProxy))];
console.log(`warming ${targets.length} urls from ${urls.length} images`);

const counts = {};
let done = 0;
const queue = [...targets];
await Promise.all(
  Array.from({ length: CONCURRENCY }, async () => {
    for (let url = queue.shift(); url; url = queue.shift()) {
      try {
        const res = await fetch(url, { method: "GET" });
        await res.arrayBuffer();
        counts[res.status] = (counts[res.status] ?? 0) + 1;
      } catch {
        counts.error = (counts.error ?? 0) + 1;
      }
      done += 1;
      if (done % 500 === 0) console.log(`${done}/${targets.length}`, counts);
    }
  }),
);
console.log("done", counts);
