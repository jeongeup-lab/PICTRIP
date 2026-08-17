export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  url.pathname = "/about/index.html";
  url.search = "";
  const asset = await env.ASSETS.fetch(new Request(url, { headers: request.headers }));
  return new Response(asset.body, {
    status: asset.status,
    headers: asset.headers,
  });
}
