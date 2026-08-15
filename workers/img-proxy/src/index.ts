import { verifyT1Signature } from "./sign";
import { ktoFallbackUpstream, resolveT1, resolveUpstream } from "./upstream";

const PROXY_UA = "PicTrip/1.0 (https://pictrip.org)";
const CACHE_TTL_SECONDS = 2_592_000;

interface Env {
  T1_SECRET?: string;
}

function upstreamInit(width?: number): RequestInit {
  if (!width) return { headers: { "User-Agent": PROXY_UA } };
  return {
    headers: { "User-Agent": PROXY_UA },
    cf: { image: { width, fit: "scale-down", quality: 82, format: "webp" } },
  };
}

export default {
  async fetch(request, env, ctx): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("method not allowed", { status: 405 });
    }
    const url = new URL(request.url);
    let upstream = resolveUpstream(url);
    let width: number | undefined;
    if (!upstream) {
      const t1 = resolveT1(url);
      if (!t1) {
        return new Response("not found", { status: 404 });
      }
      if (!env.T1_SECRET || !(await verifyT1Signature(env.T1_SECRET, t1.payload, t1.sig))) {
        return new Response("forbidden", { status: 403 });
      }
      upstream = t1.upstream;
      width = t1.width;
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

    let origin = await fetch(upstream, upstreamInit(width));
    if (origin.status === 404) {
      const fallback = ktoFallbackUpstream(upstream);
      if (fallback) {
        const mid = await fetch(fallback, upstreamInit(width));
        if (mid.ok) origin = mid;
      }
    }
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
} satisfies ExportedHandler<Env>;
