// Shared helpers for deep-link fallback pages (CF Pages Functions).
// Files prefixed with _ are not routed.

const API_BASE = "https://api.pictrip.org/v1";
const APP_STORE = "https://apps.apple.com/app/id6778157312";
const PLAY_STORE = "https://play.google.com/store/apps/details?id=com.jeongeup.pictrip";

export function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Collapse whitespace/newlines and truncate for meta descriptions.
export function summarize(text, max = 160) {
  if (!text) return "";
  const flat = String(text).replace(/\s+/g, " ").trim();
  return flat.length > max ? flat.slice(0, max - 1).trimEnd() + "…" : flat;
}

// Fetch a JSend endpoint; return its `data` or null on any failure.
export async function fetchData(path) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { accept: "application/json" },
    });
    if (!res.ok) return null;
    const body = await res.json();
    return body?.data ?? null;
  } catch {
    return null;
  }
}

// Full HTML document with Open Graph / Twitter / smart-banner meta.
export function renderPage({ url, title, description, image, bodyHtml }) {
  const t = escapeHtml(title);
  const d = escapeHtml(description);
  const ogImage = image
    ? `\n  <meta property="og:image" content="${escapeHtml(image)}" />\n  <meta name="twitter:card" content="summary_large_image" />`
    : `\n  <meta name="twitter:card" content="summary" />`;
  return `<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${t} · PicTrip</title>
  <meta name="description" content="${d}" />
  <link rel="canonical" href="${escapeHtml(url)}" />
  <meta name="apple-itunes-app" content="app-id=6778157312, app-argument=${escapeHtml(url)}" />
  <meta property="og:site_name" content="PicTrip" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="${t}" />
  <meta property="og:description" content="${d}" />
  <meta property="og:url" content="${escapeHtml(url)}" />${ogImage}
  <style>
    *{box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",system-ui,sans-serif;
      color:#111;background:#fff;max-width:560px;margin:0 auto;padding:24px;line-height:1.7;
      word-break:keep-all}
    .brand{font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:#666}
    .cover{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:12px;background:#f2f2f2;margin:12px 0}
    h1{font-size:22px;margin:8px 0 2px}
    .sub{color:#666;font-size:14px;margin:0 0 12px}
    p.body{font-size:15px;color:#222}
    .cta{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 8px}
    .cta a{flex:1;min-width:140px;text-align:center;text-decoration:none;border:1px solid #111;
      color:#111;padding:12px 14px;border-radius:10px;font-size:14px}
    .cta a.primary{background:#111;color:#fff}
    footer{margin-top:28px;padding-top:14px;border-top:1px solid #e5e5e5;font-size:12px;color:#666}
    footer a{color:#666}
  </style>
</head>
<body>
  <div class="brand">PicTrip</div>
${bodyHtml}
  <div class="cta">
    <a class="primary" href="${APP_STORE}">App Store에서 받기</a>
    <a href="${PLAY_STORE}">Google Play에서 받기</a>
  </div>
  <footer>
    관광정보·이미지 출처: 한국관광공사 (공공누리 제1·3유형) ·
    <a href="https://pictrip.org/legal/data-sources">데이터 출처 고지</a>
  </footer>
</body>
</html>`;
}

export function htmlResponse(html, status = 200) {
  return new Response(html, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      // Short edge cache; deep-link previews don't need to be real-time.
      "cache-control": "public, max-age=300",
    },
  });
}

export function pageUrl(request) {
  const u = new URL(request.url);
  return `${u.origin}${u.pathname}`;
}
