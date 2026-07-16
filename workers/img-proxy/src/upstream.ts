const ALLOWED_HOSTS = new Set([
  "upload.wikimedia.org",
  "commons.wikimedia.org",
  "tong.visitkorea.or.kr",
]);

const KTO_HOST = "tong.visitkorea.or.kr";
const KTO_HIRES = "_image1_1";
const KTO_MID = "_image2_1";

export function resolveUpstream(url: URL): string | null {
  const path = url.pathname;
  const slash = path.indexOf("/", 1);
  if (slash === -1) return null;
  const host = path.slice(1, slash);
  const rest = path.slice(slash);
  if (!ALLOWED_HOSTS.has(host)) return null;
  if (rest.length <= 1) return null;
  return `https://${host}${rest}${url.search}`;
}

export function ktoFallbackUpstream(upstream: string): string | null {
  const url = new URL(upstream);
  if (url.hostname !== KTO_HOST || !url.pathname.includes(KTO_HIRES)) return null;
  return upstream.replace(KTO_HIRES, KTO_MID);
}

const T1_PATTERN = /^\/t1\/(\d+)\/([0-9a-f]{64})(\/.+)$/;
const T1_MIN_WIDTH = 16;
const T1_MAX_WIDTH = 1620;

export interface T1Upstream {
  upstream: string;
  width: number;
  sig: string;
  payload: string;
}

export function resolveT1(url: URL): T1Upstream | null {
  const m = T1_PATTERN.exec(url.pathname);
  if (!m) return null;
  const width = Number(m[1]);
  if (width < T1_MIN_WIDTH || width > T1_MAX_WIDTH) return null;
  const upstream = resolveUpstream(new URL(`${url.origin}${m[3]}${url.search}`));
  if (!upstream) return null;
  const u = new URL(upstream);
  if (u.hostname !== KTO_HOST) return null;
  return { upstream, width, sig: m[2], payload: `${width}/${u.hostname}${u.pathname}${u.search}` };
}
