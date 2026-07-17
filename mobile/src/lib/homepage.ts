const NAMED_ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&apos;": "'",
  "&#39;": "'",
  "&nbsp;": " ",
};

function unescapeEntities(s: string): string {
  return s
    .replace(/&#(\d+);/g, (_, d: string) => String.fromCharCode(Number(d)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h: string) => String.fromCharCode(parseInt(h, 16)))
    .replace(/&(?:amp|lt|gt|quot|apos|#39|nbsp);/g, (m) => NAMED_ENTITIES[m] ?? m);
}

function stripTags(s: string): string {
  let text = s;
  let prev: string;
  do {
    prev = text;
    text = text.replace(/<[^>]*>/g, "");
  } while (text !== prev);
  return text;
}

function ensureScheme(url: string): string {
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(url) ? url : `https://${url}`;
}

function hostLabel(url: string): string {
  const host = url
    .replace(/^[a-z][a-z0-9+.-]*:\/\//i, "")
    .split(/[/?#]/)[0]
    .replace(/^www\./i, "");
  return host || url;
}

export function cleanHomepage(raw: string | null): { label: string; url: string } | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;

  const anchor = trimmed.match(/<a\b[^>]*\bhref\s*=\s*["']?([^"'\s>]+)["']?[^>]*>([\s\S]*?)<\/a>/i);
  if (anchor) {
    const url = ensureScheme(unescapeEntities(anchor[1].trim()));
    return { label: hostLabel(url), url };
  }

  const text = unescapeEntities(stripTags(trimmed)).trim();
  if (!text) return null;
  const token = text.match(/https?:\/\/[^\s"'<>]+/i);
  const url = ensureScheme((token ? token[0] : text).trim());
  return { label: hostLabel(url), url };
}
