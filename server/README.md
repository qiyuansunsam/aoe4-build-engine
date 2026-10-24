# Local API and AI drafting

`python -X utf8 server/app.py --port 8765` serves `site/dist` and the API on **127.0.0.1 only**. `start.ps1` builds the page and starts this server.

- `GET /api/games`: four downloaded historical match perspectives and recorded resource series. Reproduce with `python -X utf8 scripts/export_game_library.py`.
- `GET /api/ai/status`: checks the configured CLIProxyAPI `/v1/models` endpoint; no completion is sent. Returns `configured`, `reachable`, `mode`, selected `model`, `message` and optionally `modelCount`.
- `POST /api/ai/generate`: JSON `{prompt, civilization?, mode?, context?}`. Returns `{draft:{id,title,text,createdAt,status:"unvalidated"},model}`. Draft text is a proposal, not an executable or validated build. The adapter exposes no tools, file edits or shell commands.

Existing client configuration is read server-side from `C:/Users/Sam/projects/jobpilot/.local/proxy/config.yaml`. The adapter reads only the client key and port, never provider OAuth files. Override with environment variables `AOE_PROXY_CONFIG`, `AOE_PROXY_BASE_URL`, `AOE_PROXY_API_KEY`, and `AOE_PROXY_MODEL`. The base URL must remain loopback HTTP. Secrets must never be placed in frontend code. No provider credentials are migrated or rewritten.

Existing proxy startup, if it is not already running:

```powershell
Start-Process -FilePath 'C:/Users/Sam/projects/jobpilot/.local/proxy/release-v8.0.34/cli-proxy-api.exe' -ArgumentList '-config','C:/Users/Sam/projects/jobpilot/.local/proxy/config.yaml' -WorkingDirectory 'C:/Users/Sam/projects/jobpilot/.local/proxy' -WindowStyle Hidden
```

The configured proxy binds to 127.0.0.1:8318. Reachability and a listed model do not prove generation entitlement; provider errors remain explicit. The app does not start or alter the shared proxy automatically.

Requests have a 32 KiB body limit; prompts are limited to 6,000 characters; one generation may run at a time, with a 90-second provider timeout and bounded output. Origin and Host checks prevent a foreign browser origin from using the local generation endpoint. All keys stay in the server process, provider error bodies are not forwarded, and prompts are not logged.

`python -X utf8 -m unittest discover -s server -p 'test_*.py'` tests request validation, proxy text mapping, connection failures, host/origin checks and static path confinement with local fixtures. It sends no paid generation request.

## Historical resource interpretation

The downloaded `resources.foodGathered` and equivalent fields are misleadingly named: 14 of16 resource endpoints exactly equal `totalResourcesSpent`; the Malian food/gold series stop60/180 resources before final spending (last sample1620s, match duration1689s). They are exposed as **inferred spending** with per-resource endpoint evidence, never as gathered. Banked resources and reported income/minute are preserved directly. Per-time gathered resources, population, army value, worker splits and action starts are not recorded. The app derives labelled estimates from the recorded series and installed catalog facts (`site/observed-derived.js`): gathered = bank + cumulative spending - starting bank; population = unit balances x installed population cost; army value = military balances x base cost; worker split = villager balance shared by income per resource; start = completion - installed base duration. The official end-of-game gathered total remains available as an endpoint check (the four curated perspectives land within about 3% of it). Unit completion/loss balances exclude unclassified transformations; do not call them exact standing armies.

## On-demand match timelines

`POST /api/games/download` accepts a catalog `matchId` and optional numeric `profileId` from that match. It retrieves only the fixed AoE4World public summary endpoint, normalizes recorded completions and resource snapshots, and atomically persists the collection index plus timeline sidecars. Metadata-only or unavailable provider data is never filled with simulated worker assignments. The response is `{match, perspectives, cached}`. Requests are serialized; repeated available timelines reuse local data. New timeline files are copied directly into `site/dist/game-perspectives`, so no rebuild is needed for the new download. The browser should refresh `/api/games` on its Games view to discover persisted runtime downloads.
