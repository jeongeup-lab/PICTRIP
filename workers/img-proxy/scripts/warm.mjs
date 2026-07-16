const API = "https://api.pictrip.org/v1/explore";
const CHANNELS_API = "https://api.pictrip.org/v1/home/channels";
const PROXY = "https://img.pictrip.org";
const WIDTHS = [330, 500, 960, 1280];
const CHANNEL_KEYS = ["hot", "hidden", "festa", "pets", "snap"];
const KTO_HOST = "tong.visitkorea.or.kr";
const CONCURRENCY = 4;
const RETRY_DELAYS_MS = [3000, 8000, 20000];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchWithBackoff(url) {
  for (const delay of [...RETRY_DELAYS_MS, null]) {
    const res = await fetch(url);
    await res.arrayBuffer();
    if (res.status !== 429 || delay === null) return res.status;
    await sleep(delay);
  }
}

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

async function collectChannelImageUrls() {
  const urls = [];
  try {
    const res = await fetch(CHANNELS_API);
    const { data } = await res.json();
    urls.push(...(data?.channels ?? []).map((c) => c.thumbnailUrl));
  } catch (e) {
    console.log("channel metas skipped:", e.message);
  }
  for (const key of CHANNEL_KEYS) {
    try {
      const res = await fetch(`${CHANNELS_API}/${key}`);
      const { data } = await res.json();
      urls.push(...(data?.cards ?? []).map((c) => c.imageUrl));
    } catch (e) {
      console.log(`channel ${key} skipped:`, e.message);
    }
  }
  return urls.filter(Boolean);
}

function variants(url) {
  const m = /^(.*)\/(\d+)px-([^/]+)$/.exec(url);
  if (!m) return [url];
  return WIDTHS.map((w) => `${m[1]}/${w}px-${m[3]}`);
}

function toProxy(url) {
  return url.replace(/^https?:\/\//, `${PROXY}/`);
}

function channelTargets(url) {
  if (url.startsWith(`${PROXY}/`)) return [url];
  if (!url.includes(`//${KTO_HOST}/`)) return [];
  const targets = [toProxy(url)];
  if (url.includes("_image1_1")) targets.push(toProxy(url.replace("_image1_1", "_image2_1")));
  return targets;
}

const exploreUrls = await collectImageUrls();
const channelUrls = await collectChannelImageUrls();
const targets = [
  ...new Set([
    ...exploreUrls.flatMap(variants).map(toProxy),
    ...channelUrls.flatMap(channelTargets),
  ]),
];
console.log(
  `warming ${targets.length} urls from ${exploreUrls.length} explore + ${channelUrls.length} channel images`,
);

const counts = {};
let done = 0;
const queue = [...targets];
await Promise.all(
  Array.from({ length: CONCURRENCY }, async () => {
    for (let url = queue.shift(); url; url = queue.shift()) {
      try {
        const status = await fetchWithBackoff(url);
        counts[status] = (counts[status] ?? 0) + 1;
      } catch {
        counts.error = (counts.error ?? 0) + 1;
      }
      done += 1;
      if (done % 500 === 0) console.log(`${done}/${targets.length}`, counts);
    }
  }),
);
console.log("done", counts);
