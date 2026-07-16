const ALLOWED_HOSTS = new Set(["upload.wikimedia.org", "commons.wikimedia.org"]);

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
