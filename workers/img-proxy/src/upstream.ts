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
