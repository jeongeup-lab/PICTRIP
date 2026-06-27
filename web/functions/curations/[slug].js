// Deep-link fallback for /curations/{slug} — server-renders the curation with
// Open Graph meta so shared links unfurl, and offers app/store CTAs.
import { escapeHtml, summarize, fetchData, renderPage, htmlResponse, pageUrl } from "../_lib.js";

export async function onRequestGet(context) {
  const { params, request } = context;
  const url = pageUrl(request);
  const cur = await fetchData(`/curations/${encodeURIComponent(params.slug)}`);

  if (!cur || !cur.title) {
    const body = `  <h1>PicTrip</h1>
  <p class="sub">사진으로 찾는 국내 여행지</p>
  <p class="body">요청하신 큐레이션을 찾을 수 없어요. 앱에서 둘러보세요.</p>`;
    return htmlResponse(
      renderPage({ url, title: "PicTrip", description: "사진으로 찾는 국내 여행지 추천", image: null, bodyHtml: body }),
      404,
    );
  }

  const title = String(cur.title).replace(/\s+/g, " ").trim();
  const count = Array.isArray(cur.spots) ? cur.spots.length : 0;
  const sub = count ? `관광지 ${count}곳` : "PicTrip 큐레이션";
  const description = summarize(cur.lead || cur.intro || `${title} — ${sub}`);
  const image = cur.coverUrl || (cur.spots?.[0]?.firstImageUrl ?? null);

  const list = (cur.spots || [])
    .slice(0, 8)
    .map((s) => `<li>${escapeHtml(s.title)}</li>`)
    .join("");

  const body = `${image ? `  <img class="cover" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" />\n` : ""}  <h1>${escapeHtml(title)}</h1>
  <p class="sub">${escapeHtml(sub)}</p>
${cur.lead ? `  <p class="body">${escapeHtml(summarize(cur.lead, 300))}</p>\n` : ""}${list ? `  <ul>${list}</ul>` : ""}`;

  return htmlResponse(renderPage({ url, title, description, image, bodyHtml: body }));
}
