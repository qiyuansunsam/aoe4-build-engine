// Public front door: static assets (built with site/build.py --split-data) and a read-only /api/*
// proxy to the Fly app. The Fly app rejects any request without API_SECRET, so only this Worker reaches it.
const LOCAL_ONLY = { error: 'local_only', message: 'Timeline downloads and AI drafts run in the local workspace only.' };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(request);
    if (request.method !== 'GET' && request.method !== 'HEAD') return Response.json(LOCAL_ONLY, { status: 403 });
    const upstream = await fetch(new URL(url.pathname + url.search, env.API_ORIGIN), {
      method: request.method,
      headers: { Accept: 'application/json', 'X-Aoe-Proxy-Secret': env.API_SECRET },
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('Content-Type') || 'application/json', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
    });
  },
};
