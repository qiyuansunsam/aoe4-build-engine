# Timeline engine correction — 2026-10-23

The historical Abbasid 16.2 simulator now distinguishes actions started, completed production, and expected worker/resource state. This does not upgrade its balance tables to installed patch 16.3.

## Drop-off evidence and map assumptions

Inspected the installed Steam build 24231237 decoded game files at `C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237/decoded-all/attrib/ebps/`:

- `races/abbasid/buildings/building_town_center_capital_abb.json`, `resource_drop_off_ext.accepted_resources` (line 2366 onward): food, wood, gold and stone are accepted.
- `races/core/buildings/building_econ_food.json`: food accepted, other standard resources rejected.
- `races/core/buildings/building_econ_wood.json`: wood accepted.
- `races/core/buildings/building_econ_mining_camp.json`: gold and stone accepted.

A separate mill or mining camp is therefore **not a universal game prerequisite**. The simulator models resources at specific sites: sheep at the starting Town Center, a mill at nearby berries, a lumber camp at wood, separate camps at gold and stone, and a mill at deer. Remote berry clusters each receive a mill. Separate sites are a map assumption; one mining camp may serve both deposits in a different real layout.

Only completed sites provide the model's short-distance gathering rates. An explicit `map.tcDistances` override, for example `{ gold: 8, wood: 6 }`, permits those sources to use the existing Town Center before their camp completes, at the supplied one-way travel distance. Defaults only declare sheep at the TC. The model conservatively leaves unserved assignments idle; it does not simulate a villager collecting a partial load while waiting for a building. Farms now consume builder time and only produce after completion. Remote mills no longer appear instantly; orchard food additions occur at mill completion.

The model remains aggregate: it approximates continuous resource deliveries, reassigns workers according to resource targets, and does not simulate individual walking paths, collision or actual carried loads. Worker reassignments are predictions, not instructions observed from a match.

## Events and counts

Existing `kind`, `cat`, `cost`, and `stock` remain. Every event now supplies `phase`, `stockBefore`, `split` (including builders and idle), and `sources`. Resource-site construction retains the canonical building in `entity`, with `source` identifying its location.

- `train`, `cat: unit`, `phase: start`: Villager/Camel Rider queue commitment, producer, queue index, count, duration, readyAt and paid cost.
- `done`, `cat: unit`, `phase: complete`: actual available unit, producer and queue index.
- `assign`, `phase: allocation`: changed expected worker allocation.
- Existing build/tech/age starts and done completions remain separate. Farm plots use build/done too.

Queued units reserve population and target capacity but do not gather or count as completed army/villagers. Snapshots and milestones report completed units. Completion waits for the full duration after a construction/research/age start (the earlier loop decremented newly started work immediately). The final result waits for the population's queued units to complete.

## Verification and baseline change

`node scripts/test_engine_timeline.cjs` checks completed drop-offs before source allocation, separate mining sites, worker conservation for every event/snapshot, no gathering by trainees, exact queue completion times, farm construction, cost balances, explicit TC fallback, attrition and input purity. Default completion is 1128 seconds with 1096 events in this revision.

`test_villager_attrition.cjs` now checks exact default-versus-explicit-zero-loss parity for all three original configurations. Its former frozen whole-result hashes described the pre-correction model and were deliberately replaced, rather than refreshed from current output. Existing input purity, actual losses, replacement spending, severe-pressure and validation assertions remain and pass. The model correction intentionally changes timings and event shapes.
