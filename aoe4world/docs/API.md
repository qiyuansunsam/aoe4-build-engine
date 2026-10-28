# Local API

Run `node server/index.mjs`. The default address is `http://127.0.0.1:3001`.
The server uses Node built-ins and also serves `dist/` when a frontend build exists.
Environment settings: `PORT`, `HOST`, `AOE4_USER_AGENT`, `AOE4_CACHE_DIR`.

Successful requests return `{ data, meta: { source, fetchedAt, cached, stale } }`.
`fetchedAt` is when this app obtained the response, not the upstream aggregation time.
Stale fallback adds `warning` and, when available, `retryAfter` (seconds).
Errors return `{ error, retryAfter? }` with an appropriate HTTP status.

## Routes

| Method and path | Data |
| --- | --- |
| `GET /api/health` | Server status |
| `GET /api/filters` | Modes, ranks, patch choices from the current live balance period, supported filter capabilities |
| `GET /api/meta` | Upstream civilization statistics envelope, whose `data` contains rows |
| `GET /api/maps` | Upstream maps envelope; selecting a map returns that map's civilization rows |
| `GET /api/matchups` | Upstream 1v1 matchup envelope |
| `GET /api/teams` | Upstream 2v2 composition envelope; rows without exactly two civs are excluded and counted in `meta.excludedRows` |
| `GET /api/player/:id?page=1&mode=all` | `{ profile, games }`, both upstream objects, including pagination in `games` |
| `GET /api/search?q=Zamia` | Upstream search object containing `players` |
| `POST /api/match` | Body `{ "url": "https://aoe4world.com/players/ID-NAME/games/ID?sig=..." }`; returns raw camelCase summary |
| `GET /api/match/:id` | Previously cached summary; never downloads by ID alone |
| `POST /api/import` | Raw camelCase summary JSON, `{summary: ...}`, or this API's `{data: ...}` export |
| `GET /api/engine` | Local `data/engine/aggregates.json`, or HTTP 404 if no model exists |
| `GET /api/strategy` | Local `data/strategy/aggregate.json`: coverage, methodology and civilization/mode/patch cohorts with builds, army production and timings; HTTP 503 until initialized |
| `GET /api/collection` | Worker heartbeat/PID, counters, budgets, queue/cooldown, pagination cursor, pause state and population backfill status |
| `POST /api/collection` | `{ "paused": true }` or `{ "paused": false }`; writes persistent worker control, requires an already running collector |

The catalog is served as static `/assets/manifest.json` with local flags, unit definitions, PBG-ID mappings and artwork. `GET /api/match/:id` also reads collected summaries from `data/strategy/summaries/`. Successful match downloads and imports enqueue their summaries for aggregation without an extra upstream fetch.

Statistics filters: `mode=rm_solo|rm_2v2|rm_3v3|rm_4v4`, `rank=all|bronze|silver|gold|platinum|diamond|conqueror` (also selected `≥` bands), `patch=current|any|11308` or a comma-separated patch list, and `map=all|MAP_ID`.
The default is ranked 1v1, all ranks, current balance period, all maps. Teams defaults to ranked 2v2.
Patch choices are read from AoE4 World's current response, so `current` can cover multiple patches.
Map filtering for civilization statistics uses the upstream map detail endpoint.
Upstream does not publish map-filtered matchups or team compositions; those combinations return 422.
Matchups are 1v1 only, and team compositions are 2v2 only; unsupported modes return 422.

## Data interpretation

All published statistics retain upstream fields and units. `win_rate` and `pick_rate` are percentages. Durations are seconds.
`games_count` and `player_games_count` are different upstream counts; do not substitute one for another.
Map-specific civilization rows omit some fields such as `pick_rate` and `win_count`; show those as unavailable.
Published statistics are observed win rates, not skill-adjusted estimates.
The local engine's provenance and sample coverage must accompany any adjusted rates.

Player data retains snake_case. Match summaries retain camelCase, including `gameId`, `duration`, `mapName`, `players[].profileId`, `buildOrder`, and `resources`.
`resources` is an object of arrays with a shared `timestamps` array in seconds.
Buildings primarily use `constructed`; units use `finished` production. `destroyed` records observed losses, without opponent kill attribution. Strategy rates and shares are percentages (0–100); timings are seconds. Distinct match counts differ from player appearances. Sparse opening groups are exploratory; all opening win rates are unadjusted.

## Cache and upstream behavior

Responses are stored as JSON under `data/cache/`, keyed by SHA-256 of the canonical upstream URL (or `match:GAME_ID`).
Published aggregate statistics cache for one hour; profiles and searches for five minutes; match lists for two minutes.
Completed imported/downloaded summaries are retained indefinitely.
Identical in-flight requests are deduplicated; upstream concurrency is limited to two requests.
Requests send a descriptive app User-Agent and use Node's direct HTTP client, as verified on this machine.
There is no browser identity spoofing. The separate Python worker makes bounded, serialized summary requests and persists results under `data/strategy/`; it does not exhaustively crawl summaries.
On HTTP 429 the server honors `Retry-After`, makes no automatic retry, and serves a previous cached response with an explicit stale warning when one exists.
Summary and public API cooldowns are tracked separately in memory.
Requests time out after 25 seconds, redirects are refused, JSON bodies/responses are bounded at 10 MB, and match URLs must use exactly `https://aoe4world.com`.
The sample is the real cached match 254412239 supplied from the earlier successful local download.

## Background collection

The worker runs separately from Node (`python -m engine.collection --daemon`). It resumes at most four recent metadata pages per five-minute cycle, with a persistent `updated_since` window and next-page cursor. The rolling summary cap is 24 attempts/hour: up to 20 fresh matches selected across modes/civilizations and four tracked-history matches. All worker request starts are at least 15 seconds apart. Explicit URLs share the global cap. Imported JSON is processed locally and deduplicated.

Worker HTTP 429 honors `Retry-After`; temporary failures back off and persist cooldowns across restarts. Node's on-demand cache and the worker are separate processes. Pausing stops new worker requests after any active request returns; it does not disable on-demand API operations. Check `running` together with heartbeat freshness. No automatic machine-login service is installed.

`data/strategy/status.json` exposes `downloaded` (distinct IDs), `queued`, `failed`, `skipped`, `feedGames`, `populationGames`, `summaryBudgets`, `summaryRequestsLastHour`, `summaryNextRun`, `feedCursor`, `rateLimitedUntil`, `paused`, `phase`, `coverageGaps`, and `backfill`. Coverage remains incomplete. [Worker operation and interpretation](COLLECTION.md).

Source API documentation: https://aoe4world.com/api/

## Replay Lab

- `GET /api/replays` serves `data/replays/index.json` as the standard envelope; an uninitialized library returns an empty match list.
- `GET /api/replays/:id` serves a local report from `data/replays/reports/`. IDs are bounded alphanumeric, underscore or hyphen identifiers. Missing reports return 404.

Reports expose source hashes, file-date caveats, parser revision, capabilities and observed event coordinates. They do not infer ranked game IDs, patches, continuous unit tracks or worker allocation. `python -m engine.replay --watch --interval 30` updates the library from local statistics files; no replay files are uploaded.
