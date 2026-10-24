# AoE Build Crafter context

## Replacement and source

The starting point is `qiyuansunsam/aoe4-build-engine`, commit `fde6a76`, cloned into `C:/Users/Sam/projects/aoe4-build-crafter`. Work is on `feat/build-crafter`. The old `MathmaticallyCorrectAoe4` junction pointed to missing `C:/Users/Sam/projects/aoe4-data`; it is preserved as `MathmaticallyCorrectAoe4.previous-link`. The original path now points to this new checkout. The separate `mcaoe` application is an observational stats collector and is retained as a source, not mistaken for the simulation engine.

The replacement is a new interaction design over the remote engine, named AoE Build Crafter. The primary workflow compares two plans, scrubs a shared timeline, and opens unit/technology detail in context. The build library focuses on ranked 4v4, French cavalry, Mongol openings, Malian cow boom and Japanese two-TC play.

## Three distinct kinds of evidence

1. **Installed game attributes:** local reference XML and localization under `games/kb/aoe4/extract`. Normalize with original asset paths, source hashes, inheritance and explicit unresolved fields. These describe rules, not how popular a strategy is.
2. **Observed play:** `mcaoe/data/strategy/aggregate.json` and individual summaries. The discovered sample covers 143 matches / 756 appearances, September 29–October 4, patch 11308. Its per-build samples are exploratory; civilization win rates do not establish build popularity. Mongol starting TC placement must not be counted as a second TC.
3. **Theoretical simulation:** `site/engine.js`, with historical 16.2.10604 parameters and manually applied changes documented in `data/PATCH_STATUS.md`. Currently supports only Abbasid three-TC camel plans. New civilizations require actual plan and mechanic implementations, not a relabelled Abbasid run.

Never silently combine these rulesets. Show provenance where a player inspects a number.

## Model interpretation

- `simulate(params)` runs in the browser at one-second steps. State snapshots are minute-level; inspectors use the latest snapshot at or before the cursor.
- Internal population commitments reserve queued villagers and camels, but timeline events, snapshots, summaries and worker/army milestones report completed units. Trainees cannot gather. `armyValue` is the resource cost of completed camels, not combat strength. Training starts and completions are separate events with queue identity; exact event resource/worker state is available alongside minute snapshots.
- Technologies affect a cursor inspection only after their completion time. Administrative-wing bonuses apply only once that wing completes, not simply because it appears later in the plan.
- Distance, idle time, stacking and construction scaling remain model assumptions. Neither a successful build nor parameter arithmetic validates them against live games.
- The UI must support hovering, keyboard focus and touch/click for equivalent depth; explanations belong to the selected object.

## Scope boundaries

Game-file extraction is read-only. Raw proprietary extracts stay local and out of the repository. No game launch is required. Local redesign and verification are authorized; no remote deployment has been requested in this session.
