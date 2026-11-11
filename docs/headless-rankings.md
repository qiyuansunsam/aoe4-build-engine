# Headless win-rate tables

This implementation extends the existing `#winrates` page on production source
`9beea99`, fetched from `origin/feat/build-crafter` on November 10, 2026.
The live production page was independently checked in headless Chrome: it has
29,478 Diamond+ matches, generated November 6, and the installed 17.0.12260 catalog.
The earlier handover checkout was stale and is not this feature's baseline.

## Views and denominators

The civilization tab retains `data/winrates.json`, its large sample, and its
existing mode, map and civilization navigation. Its Update 17.0 snapshot includes
builds 12182 and 12260. Unit, technology and landmark tables use replay build
12260 and display their own patch and coverage.

Unit tables compare average military production-order shares in wins and losses.
Each player-game has equal weight. Not ordering a unit contributes zero share
in an otherwise eligible game. Games with no military orders or unresolved
potential unit orders are excluded. The table also shows overall mean share,
use rate, wins and games when used. Composition bands are expandable details,
with lower-exclusive and upper-inclusive boundaries.

Production orders include training and field construction of siege. Age tiers
share a family; economic units are excluded. Technology and landmark selections
count once per player-game, including Ottoman Vizier choices and House of Wisdom
wings. Orders do not prove completion: cancelled or unpaid orders remain, and
automatic units are not counted. Unknown army bundles are excluded rather than
counted as one ordinary unit. These are observational associations, not causal
strength; teammates, repeated players and late-game survival affect the sample.

## Independent sources and privacy

Match results, pre-match ratings, patch evidence and replay files come from the
official World's Edge / Age of Empires endpoints. No game playback, desktop
recording, AoE4 World summaries or AoE4 World static data are required.
`build_tier_catalog.py` builds identities offline from installed 17.0.12260
`data/game-catalog.json`. See `tier-catalog.md` for mappings and omissions.

The MIT parser is under `scripts/vendor`. Local fixes decode extended payload
lengths; parser version 4 invalidates older parse caches. Replay URL build IDs
are checked against binary headers. Ambiguous joins and unknown choices fail
closed. Player-level upgrade command 0x82 is included.

Public `data/tierlists.json` contains only grouped counts and share sums by mode,
civilization and rating band. It publishes no individual player names, profile
IDs or game IDs. Raw responses, replays, commands and observations stay under
ignored `.cache/rankings/`. The civ crawler's raw store is ignored `data/winrates/`.

## Run and resume

```powershell
python -X utf8 scripts/build_tier_catalog.py
python -X utf8 scripts/collect_tierlists.py --resume --max-replays 0 --workers 2 --delay 2 --build-site
```

Zero processes every current-build match in the manifest. Without `--resume`,
discovery covers ranked 1v1 through 4v4. A positive budget selects a deterministic
sample balanced across modes. Existing bytes are reused. Concurrent downloads
still have globally spaced request starts. HTTP 429 stops collection and preserves
progress; respect the cooldown before resuming. `--export-only --build-site`
reparses cached files and rebuilds without network requests.

The larger production ladder crawl can retain replay metadata:

```powershell
python -X utf8 scripts/collect_relic_matches.py --max-profiles 4000 --workers 4 --save-replay-metadata
python -X utf8 scripts/collect_tierlists.py --resume --import-history --max-replays 3000 --workers 2 --delay 2 --build-site
```

The first command retains the production crawler's active Diamond+ policy. The
second imports official results and replay references without requiring any
pre-existing analysed game. Run only one replay collector per cache. Consult
`collection-status.json` for attempted, downloaded, failed and rate-limited states.
A stopped run is not a completed cohort. Do not replace the production civ
aggregate with a partially refreshed smaller crawl.

## Verification

```powershell
python -X utf8 -m unittest discover -s scripts -p "test_tier*.py"
python -X utf8 -m unittest discover -s scripts -p test_recfile_lengths.py
python -X utf8 site/build.py
node site/verify-winrate-items.cjs site/dist/index.html
```

Checks cover patch isolation, player joins, zero-share means, raw-identifier
exclusion, field siege, unknown choices, extended payload lengths, preserved
civilization filters, item icons, Chinese, both themes and mobile layout.
