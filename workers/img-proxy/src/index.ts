import { resolveUpstream } from "./upstream";

const WIKIMEDIA_UA = "PicTrip/1.0 (https://pictrip.org)";
const CACHE_TTL_SECONDS = 2_592_000;

export default {
  async fetch(request, _env, ctx): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("method not allowed", { status: 405 });
    }
    const url = new URL(request.url);
    const upstream = resolveUpstream(url);
    if (!upstream) {
      return new Response("not found", { status: 404 });
    }

    const headOnly = request.method === "HEAD";
    const cache = caches.default;
    const cacheKey = new Request(url.toString());
    const cached = await cache.match(cacheKey);
    if (cached) {
      const hit = new Response(headOnly ? null : cached.body, cached);
      hit.headers.set("x-img-proxy", "hit");
      return hit;
    }

    const origin = await fetch(upstream, { headers: { "User-Agent": WIKIMEDIA_UA } });
    if (!origin.ok) {
      return new Response(headOnly ? null : origin.body, {
        status: origin.status,
        statusText: origin.statusText,
      });
    }

    const miss = new Response(origin.body, origin);
    miss.headers.set("Cache-Control", `public, max-age=${CACHE_TTL_SECONDS}, immutable`);
    miss.headers.set("x-img-proxy", "miss");
    miss.headers.delete("Set-Cookie");
    if (headOnly) {
      ctx.waitUntil(cache.put(cacheKey, miss));
      return new Response(null, { status: miss.status, headers: miss.headers });
    }
    ctx.waitUntil(cache.put(cacheKey, miss.clone()));
    return miss;
  },
} satisfies ExportedHandler;
