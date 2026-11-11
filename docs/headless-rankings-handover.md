# Production-source handover, November 10, 2026

## Baseline correction

The first implementation incorrectly used the stale replay-handover checkout.
This package instead starts at production source `9beea99` on
`origin/feat/build-crafter`. A headless live-site check confirmed the deployed
29,478-match Diamond+ civilization snapshot and installed 17.0.12260 catalog.
The existing civilization snapshot is preserved unchanged. Its Update 17.0
sample spans builds 12182 and 12260; the new replay tables use build 12260 only.

## Implemented

- Added Units, Technologies and Landmarks within the existing Win rates page.
  Existing civilization boards, maps and navigation remain intact.
- Replaced the generic Choice table with actual names and installed icons.
  Units show average production share in wins, average share in losses, their
  difference, overall mean, use rate, win rate when used and sample counts.
  Zero-use games contribute zero to means; games with no military orders do not.
  Composition bands are optional expandable details. Filters include civilization,
  ranked mode and rating. Existing themes and Chinese translation are supported.
- Official match history and replay files are collected headlessly. There is no
  local game playback, recorder, or AoE4 World dependency. All 280 replays checked
  in the first corrected snapshot were absent from the existing Games library.
- Identities come entirely from the installed 17.0.12260 catalog: 4,926 mappings
  across 25 civilizations. Previously missing Fishpond, Sacred Grove and Hirdman
  upgrade IDs are resolved.
- Parser version 4 includes player-level upgrade command 0x82, used by Ottoman
  Vizier choices, and fixes extended command lengths above 255 bytes. The latter
  was checked against 77 real commands and recovered siege construction and a
  landmark. Field-built siege joins the same families as workshop production.
- Public data is aggregate-only. Raw player identities, match IDs, commands,
  replay files and source responses stay in ignored local stores.

## Shipped snapshot and collection limits

The current grouped snapshot contains 890 build-12260 matches and 5,408
player-games. There are 365 cached replay files, 354 usable parsed matches and
11 parser or player-join failures. Category coverage is 1,858 unit player-games,
1,882 technology player-games and 1,882 landmark player-games.

Usable replay matches by mode: 81 ranked 1v1, 78 ranked 2v2, 76 ranked 3v3 and
119 ranked 4v4. These counts are not the civilization tab's 29,478-match sample.

The earlier 240-replay limit was an implementation choice, not a need to use
pre-analysed games. The corrected collector defaults to all discovered matches.
The expanded 890-match attempt stopped at an official HTTP 429 after 334
attempts. The cache is preserved. Do not describe this as a finished full cohort.

A separate larger official crawl identified 12,116 active Diamond+ seed players.
It was stopped at the user's handover request: 300 profiles checkpointed and
3,334 raw match rows retained, with no completed run. This partial refresh has
not replaced the production civilization aggregate. No collection process is
intentionally left running by this handover.

## Known limits and next work

Orders are intent, not completed production. Cancellations, free units, army
bundles and game survival affect interpretation. Shared teams and repeated players
are correlated. The statistics do not estimate causal unit strength.

Nine remaining nonzero unknown training IDs are absent from the installed
catalog's extracted squad records. Seven correspond to Wynguard or Lancaster
army bundles; two correspond to Lancaster ships. Their names appear in building
trainable lists, but that does not establish bundle quantities or current squad
identity. Keep affected unit shares excluded until the installed extraction is
extended. Do not count a bundle as one ordinary unit.

After the official service cooldown, resume the cached collection at a lower
request rate. For a fresh checkout, omit `--resume` on the first discovery run:

```powershell
python -X utf8 scripts/build_tier_catalog.py
python -X utf8 scripts/collect_tierlists.py --resume --max-replays 0 --workers 2 --delay 2 --build-site
```

The large official crawler can save replay references for later import:

```powershell
python -X utf8 scripts/collect_relic_matches.py --max-profiles 4000 --workers 4 --save-replay-metadata
python -X utf8 scripts/collect_tierlists.py --resume --import-history --max-replays 3000 --workers 2 --delay 2 --build-site
```

Respect HTTP 429; the current implementation stops rather than bypassing limits.
Only replace the civilization aggregate after validating the larger refresh and
its coverage. The raw caches are not in Git. On this workstation they are in
`C:/innomate/aoe4-rankings/.cache/rankings/` and `data/winrates/`.

## Validation and publication

Focused checks cover mapping identity, production denominators and zero shares,
patch/mode isolation, raw-identifier exclusion, player-level upgrades, long payload
lengths, the preserved civilization view, per-civ filters, icons, Chinese, themes
and mobile layout. Commands are in `headless-rankings.md`.

This handover is a source push. A Cloudflare deployment is a separate operation;
do not infer that the live site changed from a successful Git push. Use the
existing `deploy/README.md` workflow when publishing the verified source.
