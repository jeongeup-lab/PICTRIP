const T1_PREFIX = "https://img.pictrip.org/t1/";

interface T1Parts {
  width: number;
  target: string;
}

function parseT1(url: string | null | undefined): T1Parts | null {
  if (!url || !url.startsWith(T1_PREFIX)) return null;
  const rest = url.slice(T1_PREFIX.length);
  const widthEnd = rest.indexOf("/");
  if (widthEnd <= 0) return null;
  const width = Number(rest.slice(0, widthEnd));
  if (!Number.isInteger(width) || width <= 0) return null;
  const afterWidth = rest.slice(widthEnd + 1);
  const sigEnd = afterWidth.indexOf("/");
  if (sigEnd <= 0) return null;
  return { width, target: afterWidth.slice(sigEnd + 1) };
}

export function preferredSeedImageUrl(
  seedUrl: string,
  serverUrl: string | null | undefined,
): string {
  const seed = parseT1(seedUrl);
  if (!seed) return seedUrl;
  const server = parseT1(serverUrl);
  if (!server) {
    if (!serverUrl || serverUrl.startsWith(T1_PREFIX)) return seedUrl;
    return serverUrl;
  }
  if (seed.target === server.target && server.width > seed.width) return serverUrl as string;
  return seedUrl;
}
