/**
 * KTO `homepage` is often raw HTML, e.g. `<a href="http://visitjeju.net">방문</a>`
 * or an entity-escaped URL. `cleanHomepage` extracts a working link + a readable
 * host label so the detail screen never renders an `<a href ...>` tag.
 */

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

// Strip HTML tags to a fixpoint. A single `<[^>]*>` pass can leave a
// reconstructable tag behind (e.g. "<<a>a href>"), so repeat until the string
// stops changing — complete, bypass-proof sanitization.
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

/** Readable host: drop scheme, path/query, leading www. e.g. `visitjeju.net`. */
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

  // <a href="URL">TEXT</a> — the href is the canonical link.
  const anchor = trimmed.match(/<a\b[^>]*\bhref\s*=\s*["']?([^"'\s>]+)["']?[^>]*>([\s\S]*?)<\/a>/i);
  if (anchor) {
    const url = ensureScheme(unescapeEntities(anchor[1].trim()));
    return { label: hostLabel(url), url };
  }

  // Plain text / entity-escaped URL: strip tags, unescape, pick the first URL token.
  const text = unescapeEntities(stripTags(trimmed)).trim();
  if (!text) return null;
  const token = text.match(/https?:\/\/[^\s"'<>]+/i);
  const url = ensureScheme((token ? token[0] : text).trim());
  return { label: hostLabel(url), url };
}
