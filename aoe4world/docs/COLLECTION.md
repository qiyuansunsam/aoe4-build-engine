# Local collection and strategy data

The application now has three separate sources: published civilization statistics, sanctioned seasonal population dumps, and an expanding detailed match sample. Summary observations never stand in for the multi-million-game population.

## Background worker

Run from the project root:

```powershell
python -m engine.collection --daemon
```

The running Windows instance was launched with `Start-Process -WindowStyle Hidden`. Its PID and heartbeat are in `data/strategy/status.json`; logs are `worker.log` and `worker-error.log` in that folder. No login task, Windows service or scheduled task is installed: restart the worker after a machine reboot. An OS file lock prevents duplicate workers.

To launch it hidden from the project root:

```powershell
New-Item data/strategy -ItemType Directory -Force | Out-Null
Start-Process python -ArgumentList '-u','-m','engine.collection','--daemon' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -RedirectStandardOutput 'data/strategy/worker.log' -RedirectStandardError 'data/strategy/worker-error.log'
```

Stop gracefully by creating `data/strategy/STOP`; it is removed on exit. Pause/resume collection by writing `{"paused":true}` / `{"paused":false}` to `data/strategy/control.json`, also exposed by the local collection API. The worker finishes an already-started request before pausing. Local imports still process while paused.

```powershell
New-Item data/strategy/STOP -ItemType File -Force
python -m engine.collection --enqueue 'https://aoe4world.com/players/7999822/games/254412239?sig=...'
```

URLs may also be placed as `{"url":"..."}` in a uniquely named JSON file under `data/strategy/queue/`; full camelCase summaries in that directory import without a network request. URLs are restricted to the exact AoE4 World HTTPS host and player/game path. Explicit share signatures are preserved locally and never guessed. Imported or fetched summaries are stored once per game ID under `data/strategy/summaries/`. The existing user sample is included and deduplicated.

The worker seeds a queue from the latest 20 match records for tracked profile **7999822** and checks for up to four new records hourly. It also reads up to four pages of the recent `updated_since` metadata feed every five minutes. Every page persists the window and next-page cursor, so a four-page boundary resumes on the next cycle instead of discarding the rest of the window. The cursor advances with a 60-second overlap only after exhausting the window. Live pagination can still shift; provider 20-page boundaries and windows older than two hours are recorded explicitly in `coverageGaps`.

Each hour it selects up to **20 fresh completed matches** from the feed, distributing choices across the four ranked modes and preferring less represented civilizations within each mode. A stable game-ID hash breaks ties; outcomes never influence selection. The summary request quota reserves up to 20 attempts per rolling hour for fresh feed matches and four for tracked history, with **24 attempts per rolling hour globally**. Explicit URLs share the global limit. Existing, queued and unavailable game IDs are excluded from fresh selection. This extends the sample beyond the tracked player's teammates and opponents while preventing either source from consuming the other's allocation. It sends one honest identifying User-Agent, serializes all worker requests and spaces request starts by at least 15 seconds. This is a bounded convenience sample, not a representative population or an exhaustive crawl.

Request timeout is 30 seconds; responses are limited to 10 MB. HTTP 429 respects `Retry-After` seconds or HTTP dates; other temporary errors use exponential cooldowns. Cooldown, queue state, request budget and timestamps survive a restart. HTTP 401/403/404/410/422 entries are marked unavailable rather than retried through another identity. A 403 also cools the worker for one hour. There are no proxies, agent impersonation or authentication workarounds.

## Population backfill

```powershell
python -m engine.background
```

This separate one-time job downloads the four ranked Season 12 archives from fresh sanctioned `/dumps` links, appends valid 2026 games to the existing Season 13 parquet lake, then exports models once with the existing 50,000-row limit per model. `data/strategy/backfill.json` reports download/ingest/model stages and errors. Do not run two population backfills or pipeline writers together. Downloads promote `.partial` files only after success. Existing parquet and aggregate JSON remain available until their replacement files are complete.

The summary worker maintains recent match metadata in `data/strategy/collection.sqlite3` and exports `metadata.jsonl`. This is available for a later serialized pipeline append; it does not refit millions of population rows every five minutes. Season 14 has no published seasonal dump as of the October 4 inspection. Neither backfill nor recent feed can claim every 2026 match.

## Strategy contract

`python -m engine.strategy` refreshes `data/strategy/aggregate.json` entirely from local summaries. The collector does this after every successful download/import. Root routes serve that file as `/api/strategy` and worker status as `/api/collection`.

Each cohort has exact `civilization`, `mode`, `patch`, distinct match `samples`/`games`, `playerSamples`, `wins`, `winRate`, `interval`, `builds`, `army`, and age `timings`. Patch comes from summary patch or `_recentGameHash.patch.app_version`, not from the current calendar. Rates and shares use 0–100 percentage points. Match and player sample counts are different when a civilization appears twice in one game.

Opening groups are explicit observed signatures: Feudal landmark, an additional town center by 12:00, and first military building. They are not learned optimal-build clusters. Games shorter than 12 minutes do not enter build groups. Building events use `constructed`, with `finished` only as a fallback. The representative is a real member nearest the group's median Feudal timing. Its event lane contains first completion times and counts within the first 12 minutes. Age quartiles use linear interpolation; unobserved ages have null timing and zero sample count.

Army production counts strictly positive `finished` unit events. Starting armies, villagers, trade/economic units and construction-only unpacked siege forms are excluded. Units stay separated by recorded PBG ID, including technology tiers. Recorded destruction counts are shown separately; they are not opponent-attributed kills or surviving population. Unit win rates describe appearances in which that unit was produced, so game length, player decisions and repeated players confound any comparison.

Build rates and 95% Wilson intervals are descriptive and unadjusted, computed over player appearances. Distinct match counts accompany them. Teammates and repeated players are not independent observations; the interval does not correct for that correlation. Groups under 30 distinct matches are marked `exploratory`; larger groups are `observed`, never certified best builds.

Verification: `python -m unittest engine.test_strategy engine.test_engine` covers source field semantics, deduplication, cohort separation, short-game exclusions, production events, URL validation, retry parsing, four-page cursor resume, source quotas and mode-balanced sampling.

Sources: [API and collection guidance](https://aoe4world.com/api), [sanctioned seasonal dumps](https://aoe4world.com/dumps).
