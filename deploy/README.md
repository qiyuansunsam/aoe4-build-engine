# Public deployment

Two pieces, both read-only for visitors:

- **Cloudflare Worker `mcaoe4`** (`deploy/cloudflare/`) serves the app as static assets and proxies
  `GET /api/*` to Fly. Static asset requests are free; only `/api/*` calls count as Worker requests
  (free plan: 100,000 a day).
- **Fly app `mcaoe4-api`** (`deploy/fly/`, region `syd`) runs `server/app.py --public` on one
  shared-cpu-1x 512 MB machine that stops when idle, so it bills only while serving (about $3 a
  month if it never stopped). It answers only requests carrying `X-Aoe-Proxy-Secret`, which the
  Worker adds, so nobody can hit the machine directly.

Public mode serves the game library, saved match summaries and AoE4 World player search (official
API v0). Timeline downloads (AoE4 World game-summary pages, which they restrict for bots) and AI
drafting (local CLI proxy) stay in the local workspace and return `403 local_only`. Player-search
additions to the game library live on the machine's disk and reset when it restarts from the image.

## Redeploy

```bash
# front end: the 31 MB single page is split into data/*.js files (Cloudflare caps a file at 25 MiB)
python -X utf8 site/build.py --split-data --out deploy/cloudflare/dist
cd deploy/cloudflare && npx wrangler deploy

# API: stage server + game library + every summary the library references, then deploy
python -X utf8 deploy/stage_fly.py
cd deploy/fly/build && flyctl deploy -a mcaoe4-api --remote-only --ha=false
```

Rotate the shared secret by setting the same new value in both places:
`flyctl secrets set AOE_PROXY_SECRET=… -a mcaoe4-api` and `npx wrangler secret put API_SECRET`
(run from `deploy/cloudflare`).

Logs: `npx wrangler tail mcaoe4` and `flyctl logs -a mcaoe4-api`.
