// Deep-link fallback for /spots/{contentId} — server-renders the spot with
// Open Graph meta so shared links unfurl, and offers app/store CTAs.
import { escapeHtml, summarize, fetchData, renderPage, htmlResponse, pageUrl } from "../_lib.js";

export async function onRequestGet(context) {
  const { params, request } = context;
  const url = pageUrl(request);
  const spot = await fetchData(`/spots/${encodeURIComponent(params.id)}`);

  if (!spot || !spot.title) {
    const body = `  <h1>PicTrip</h1>
  <p class="sub">사진으로 찾는 국내 여행지</p>
  <p class="body">요청하신 관광지를 찾을 수 없어요. 앱에서 둘러보세요.</p>`;
    return htmlResponse(
      renderPage({ url, title: "PicTrip", description: "사진으로 찾는 국내 여행지 추천", image: null, bodyHtml: body }),
      404,
    );
  }

  const region = [spot.regionName, spot.sigunguName].filter(Boolean).join(" · ");
  const sub = [spot.category, region].filter(Boolean).join(" · ");
  const description = summarize(spot.overview || spot.addr1 || sub);
  const image = spot.firstImageUrl || null;

  const body = `${image ? `  <img class="cover" src="${escapeHtml(image)}" alt="${escapeHtml(spot.title)}" />\n` : ""}  <h1>${escapeHtml(spot.title)}</h1>
  <p class="sub">${escapeHtml(sub)}</p>
${spot.addr1 ? `  <p class="sub">${escapeHtml(spot.addr1)}</p>\n` : ""}  <p class="body">${escapeHtml(summarize(spot.overview, 400))}</p>`;

  return htmlResponse(renderPage({ url, title: spot.title, description, image, bodyHtml: body }));
}
