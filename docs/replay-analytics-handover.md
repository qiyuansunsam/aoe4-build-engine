# AoE4 player-skill analytics: requirements, findings and handover

Status: exploratory prototype and data collection, 2026-10-27. Tactical capture of the user's games, automated recurring sync, scoring and radar charts are not complete. No game client was launched. Do not present sample telemetry as user performance.

## Repository and integration context

The deployed `https://mcaoe4.qiyuansunsam.workers.dev/` site belongs to **qiyuansunsam/aoe4-build-engine**, on the `feat/build-crafter` line of development. Base commit for this handover is `053360a`. Worker identity is established by `deploy/cloudflare/wrangler.jsonc` (`name: mcaoe4`); `deploy/README.md` documents the Cloudflare front end and Fly API. `mcaoe4` is the deployed Worker name, not the GitHub repository name. The deployed page also contains build paths under `C:/Users/Sam/projects/aoe4-build-crafter` and the same application title. Cloudflare account-side deployment metadata was not retrieved because local Wrangler authentication had expired.

Integration should extend the existing recorded-game system, not the theoretical Abbasid simulation:

- `server/timeline_download.py` and `server/app.py`: existing serialized on-demand summary download and cache routes. Consult these before introducing a second ingestion service.
- `scripts/export_game_library.py`, `data/game-library.json` and timeline sidecars: existing recorded-game catalog and perspectives.
- `site/observed-derived.js`: estimates derived from observed summaries. Keep measured telemetry and estimates distinct.
- `data/INSTALLED_DATA.md` and the installed catalog: this branch documents extraction of executable patch 16.3.11308, matching the requested games' numeric patch. Reuse and validate those rules before relying on the experiment's unpinned current-web technology values.
- `server/README.md`: explicitly warns that historical resource fields labelled gathered can actually represent spending. Validate source semantics before using them for upgrade payoff or economic efficiency.
- `deploy/README.md`: production summary downloading is currently local-only. A scheduled recorder requires a separate Windows game host; it cannot run inside the existing Worker or small Fly Python service.

The other workstation's paths and installed-game evidence do not mean AoE4 is installed on the workstation used for this experiment. This feature branch changes documentation and isolated experiments only; it does not deploy or alter public app behaviour.

## Objective and confirmed scope

Build a repeatable analysis of the latest 10 completed games **per player**, deduplicating matches shared by players. Keep each player's own ten-game membership when aggregating; a match in one player's ten can be outside another's. Do not replace unavailable matches with older ones silently.

| Profile ID | Observed player name |
| --- | --- |
| 7195780 | epsilon |
| 1588970 | inn |
| 7999822 | Zamia Slayer |
| 18518902 | LTYSWLP |

The initially duplicated 1588970 URL was corrected to 18518902. The project belongs in the user's personal Git repository.

The user wants actionable skill analysis, especially multitasking, reaction, choosing to fight or disengage when countered/outnumbered, combat efficiency, early contribution and sustained map occupation. Economic metrics remain in scope. The final presentation should include a radar chart per player with drill-down evidence.

The user explicitly clarified that **villager kills means enemy villagers killed by that player**, not the player's own villagers lost. Own losses are a separate defensive measure. Never attribute all enemy villager losses to every member of a team.

## Proposed radar axes

| Axis | Evidence and component measures |
| --- | --- |
| Fighting efficiency | Local trades, effective damage participation, target selection, reinforcements; show fight-selection quality separately from trade outcome |
| Aggression | First useful pressure, pressure duration, participation in team engagements; do not reward pointless attacking |
| Map control | Military presence through time, contested positions, resource/objective access; separate scouting, presence, influence and control |
| Growth | TC utilisation and villager production, expansion and economic development |
| Harassment | Enemy villagers killed by the player, first-kill timing, kills per raid, raiding-force losses and damage to economy; assists separate |
| Timing | Research requests/completions, attacks, reinforcements and relevant technology opportunities |
| Multitasking | Response coverage at multiple fronts while maintaining production; compare combat windows with appropriate quiet windows |
| Reaction | Relevant commands after new visible threats or first damage; distinguish the two triggers and report unanswered opportunities |

Do not convert missing data into zero. Do not invent 0-100 ratings or use raw APM as a skill score. Define reference populations or transparent thresholds first, conditioned where appropriate on civilization, mode, map, phase and team role. Show raw metrics, sample counts and confidence beside normalized values. No benchmark population or calibrated axis weighting has been acquired yet. Four friends alone are a poor universal skill baseline.

## Economic requirements

TC production metrics stop at the player's last observed villager birth, excluding time after production ceased. This is an observable cutoff, not evidence that the player deliberately stopped. Keep resumed replacement production if it occurs later. Optionally expose phase-specific and per-TC cutoffs as separate views; do not change the agreed default silently.

- Sum operational TC-seconds, counting a TC only after construction and while operational.
- Exclude Knights Templar age-up occupancy on the researching TC, not all TCs.
- Villagers per eligible TC-minute = trained villager count * 60 / eligible TC-seconds.
- For uniform 20-second training, the residual non-villager capacity seconds per TC-minute is `60 - 20 * production_rate`.
- That residual is **not exact empty-queue time**. Other research, scout production, unfinished units, cancellations and production-speed modifiers matter.
- Exclude starting and free/gifted villagers from trained counts. Handle Ayyubid gifts, civilization bonuses, landmarks and patch-specific changes explicitly.
- Reconstruct queue-empty intervals from telemetry where available. Do not infer lost completed TCs from every summary destruction: foundation losses exist.
- Resource float should be time-weighted, split by resource, and associated with actual production/technology opportunities. Saving for an age-up or strategic investment is not automatically waste.
- Distinguish a research request from its execution and completion. Nominal affordability alone does not establish an upgrade opportunity.
- Economic payback is a scenario estimate requiring affected worker allocation, effective rates, walking/drop-off costs, prerequisites, modifiers and competing priorities. Horticulture does not apply to hunted meat; Wheelbarrow is not a flat gather-rate multiplier.

## Tactical definitions and safeguards

### Enemy villager kills and harassment

Require an actual villager death and hostile killer attribution. The prototype joins an entity-killed event to a lethal damage event within a narrow tolerance, credits the attacker owner's player, and excludes same-team damage. Track unattributed deaths explicitly. A future production version should validate capture ordering, buildings/projectiles, conversions, mixed-player damage and assists. Credit lethal kills and damage assists separately to avoid duplicate team kill counts.

Useful outputs: total kills, first kill, kills before 10/15 minutes, raid clusters, kill timing, own raiding-army value lost, and forced idle time. Compare different game lengths and roles thoughtfully; kills per minute alone can penalize useful economic support play.

### Reaction and multitasking

An attack/move command can be issued before a threat begins, can target the wrong units, or can be irrelevant. Match responses to the affected squad or nearby defenders. Split first-visible-threat latency from first-damage latency. Visibility is not evidence of human attention. Exclude already responding units; record no-response cases as censored/failed opportunities rather than zero seconds. Report median, tail latency, opportunity count and successful saves.

Group spatially separated, temporally overlapping threats into fronts. Relate defensive response and losses to ongoing production. Command co-occurrence in 30-second windows is only an exploration aid: movement may involve villagers or scouts and is not a demonstrated multitasking score.

### Fight selection and efficiency

Use local units at commitment, health, composition/counters, upgrades, reinforcements, defensive structures, visibility, terrain and objectives. A global army-count advantage is not local fight superiority. Evaluate decisions using information available at the time, not hindsight. A losing trade can secure an objective or protect an ally. Keep actual trade efficiency distinct from model-predicted outcome and any micro rating.

### Map occupation and contribution

Use actual positions over time, not click locations. Separate scouts from fighting units. Measure first non-scout military arrival, first combat participation, per-minute presence and cell-seconds, contested areas, and sustained access to resources/objectives. A grid visit is not ownership. The sample implementation uses a 16x16 grid and distance to starting bases as an enemy-half proxy; it is not a map-control score and needs terrain/pathability/team extensions.

## Collected dataset and verified findings

The frozen manifest contains 40 player-match memberships across **19 unique matches**, all reporting API patch 11308. The first three matches were exploratory; later collection expanded to the full latest-ten request.

| Player | Replay coverage | Summary plus replay analysis coverage |
| --- | --- | --- |
| epsilon | 10/10 | 10/10 |
| inn | 9/10 | 8/10 |
| Zamia Slayer | 10/10 | 9/10 |
| LTYSWLP | 10/10 | 9/10 |

- 18 replay files downloaded and parsed; 17 summaries available.
- Match 256052058 (Cliffside, 137 seconds): both replay and summary requests returned HTTP 404.
- Match 255400269: replay downloaded and parsed; summary returned HTTP 404.
- Requests used the participating profile recorded in the manifest. These failures describe the observed requests, not proof of permanent global unavailability.
- No full game-state telemetry was captured for these 18 user replays. Enemy villager kills and all radar scores remain null.
- The 18 available matches total about 483.2 minutes by API durations. These durations are suitable for rough runtime budgeting, not clock alignment.
- Match 255410440 (Flankwoods, October 11) is the latest match shared by all four. It is not each player's latest individual game.

### Timing investigation

The shared replay parser reports 892.25 seconds while the summary reports 933 seconds. Do not scale or shift all event times to force the two durations to match. Eight Wheelbarrow request/completion pairs across the original three matches have elapsed times from 89 to 89.75 seconds, consistent with the current 90-second technology duration and summary timestamp rounding. This supports local alignment of those anchors only; the cause of the overall duration discrepancy remains unconfirmed.

Example: LTYSWLP requested Wheelbarrow at 490.25 seconds and completed at summary time 580 seconds. The research time is not player reaction delay.

### Summary pitfalls observed

- inn's October 25 summary lists an extra-TC destruction at 369 seconds before extra-TC completion at 411 and 480 seconds. Treating every destruction as loss of an operational TC yields a false denominator; a lost/cancelled foundation is a plausible explanation, not yet proven by game-state playback.
- Births are not always trained villagers. Zamia's Ayyubid game needs gift and production-speed handling.
- Summary resource samples do not necessarily reach match end. For October 25, the last sample is 1480 seconds but API duration is 1524 seconds. Do not label the last bank as an exact end-of-game leftover.
- Grouped loss episodes are review aids, not established raid boundaries or attacker attribution.

## Sources and implementation choices

### Command replay parser

[ailrk/aoe4-replay-viewer](https://github.com/ailrk/aoe4-replay-viewer) provides a TypeScript parser and the observed replay download method:

```text
https://api.ageofempires.com/api/GameStats/AgeIV/GetMatchReplay/?matchId=255410440&profileId=18518902
```

This returned HTTP 200 without login for the shared match. The server labelled the payload `application/zip`, but the magic bytes identify gzip. Decompression yielded a valid `AOE4_RE` header. The downloaded file was 466,023 bytes and decompressed to 1,828,729 bytes. Record IDs and all eight profiles matched the requested game.

The parser exposes queue-unit, research, cancel, move, attack-move, seek-shelter and other commands, with unknown command types retained. The first shared match had 31,334 command records including periodic/wrapper records; this is not APM. Two message records were unsupported. A successful parse does not establish complete event semantics.

No license file was identified in the inspected parser tree. Its implementation is not vendored into this feature. `prepare_sources.py` fetches the pinned research dependency into an ignored cache. Confirm reuse terms before distributing derivative code.

[exoque/aoe4replayanalyzer](https://github.com/exoque/aoe4replayanalyzer) provides desktop releases; the inspected main tree contained README and gitignore, not implementation source. Do not assume its code can be extended from that repository. AoE4 World's inspected [full replay parser](https://github.com/aoe4world/replays-api/blob/master/AoE4WorldReplaysParser/ReplayFullParser.cs) throws `NotImplementedException` in `Parse()`.

### Rich game-state recorder

[BigManJohn000/aoe4-replay-viewer](https://github.com/BigManJohn000/aoe4-replay-viewer) is MIT-licensed. Its recorder runs the replay through the actual game client and samples state. Pinned provenance is in `sources.json`.

Inspected `recorder.lua` supports positions/HP, owners, visibility masks, attack targets, hit/projectile events, killed entities, resource credits, produced squads, research queue/cancel/completion, foundations, production queues, idle transitions, population cap and strategic-point changes. Not all upstream converter/viewer calculations consume every recorded field. Extending extraction/analytics is still required.

The included **May versus Beasty** showcase, game 245598603, was downloaded and tested separately. It is not a user match. The version-6 recording contained 4,203 heartbeat lines with maximum 0.5-second spacing, queue and visibility events, and 15,361 resolved hostile damage events under the prototype's filters. There were 147 hit events with unresolved attacker/victim identity. The proof of concept attributed 69 and 23 enemy villager kills to the two sample player indices with zero villager deaths left without a matched hostile finisher. These are experimental extractor results, not independently validated official scores.

The prototype also calculates full-observation TC empty-queue seconds and military grid cell-seconds. The former includes intentional endgame stopping and is not the requested production-cutoff-normalized metric yet.

### Research basis for coaching

[Official AoE4 tips](https://www.ageofempires.com/news/age-of-empires-iv-tips-to-help-you-get-started/) emphasize rallying workers, scouting enemy production, counters, production buildings and queue management while controlling armies. [House of Titus's guide](https://aoe4.christitus.com/essential-tips/) prioritizes villager production, resource spending, scouting, upgrades and defence. These support metric categories, not validated numerical scoring weights or universal thresholds.

Technology reference examples: [Wheelbarrow](https://raw.githubusercontent.com/aoe4world/data/main/technologies/english/wheelbarrow-1.json), [Horticulture](https://raw.githubusercontent.com/aoe4world/data/main/technologies/english/horticulture-2.json). The cached reference data was fetched during this session and is not proven patch-pinned to 11308.

## Cost, installation and authorization

The rich recorder needs Windows, a Steam installation of AoE4 and a replay-compatible game build. It launches the client, injects Lua through the developer console, runs accelerated playback and writes telemetry. This is not a headless standalone simulator. After capture, analysis does not need the game client.

Upstream reports a 10-minute match recording in about 80 seconds; source comments report a separate 14-minute benchmark around 17-20x playback using 720p/lowest graphics. These are author measurements, not measurements on this workstation. At 7.5/15/20x, 483.2 game-minutes corresponds to about 64.4/32.2/24.2 simulation minutes, plus startup/loading/conversion. Team games may be slower. Benchmark one representative 4v4 before promising throughput. The supplied 35-minute telemetry file is about 15 MB; do not extrapolate that as a guaranteed 4v4 storage rate.

The user authorized running the recorder for the deduplicated latest ten games per player after being told that it launches AoE4, sends developer-console commands and temporarily changes graphics settings. Permission is not the blocker. AoE4 was not found in registered Steam libraries, the usual Xbox directory or matching installed Store packages. The user's installation path or a separate recording PC is still needed. Do not install/buy the game or modify an unrelated game installation without instruction.

No recurring job is currently installed. Source staging and all existing experiments were file/terminal work; no desktop control occurred.

## Recommended pipeline

1. Discover latest completed ten per player; persist exact membership and snapshot time. Preserve IDs rather than names as keys.
2. Deduplicate by game ID. Cache API responses and raw replays with provenance/checksums.
3. Fetch summaries responsibly. AoE4 World's [API guidance](https://aoe4world.com/api) requests identifying User-Agent headers, caching and incremental `updated_since` checks; summary analysis is expensive. Respect HTTP 429 and `Retry-After`, use bounded retries, and seek developer guidance before expanding automated summary volume.
4. Parse replay commands once per source/parser version. Report unknown records, not just success/failure.
5. Record each available compatible game once, sequentially. Verify full coverage, heartbeat gaps, recorder errors and game identity before publishing telemetry.
6. Join telemetry, commands and summary using validated clocks/entity identity. Store unmatched events and coverage diagnostics.
7. Calculate versioned metrics locally; changing scoring or charts should not require downloading or playing the game again unless the capture schema changed.
8. Aggregate per player's exact ten, retaining missing counts, role/civ/mode context and uncertainty.
9. Calibrate radar axes, render comparisons with drill-down event timelines, then schedule incremental discovery/capture if requested infrastructure is available.

## Prioritized next tasks and acceptance checks

1. Locate compatible AoE4 on the recording machine. Run one user 4v4 and measure real runtime. Verify the recorder captures through replay end and restores settings; do not mark completion from a file's existence alone.
2. Independently check a small set of villager deaths, killer owners, TC queue transitions, research starts/completions and damage/visibility moments against playback. Handle buildings and projectiles. Test team attribution and assists.
3. Implement TC cutoffs, Templar exclusions, free villagers, variable training speeds and lost foundations. Keep exact queue empty time separate from economic capacity estimates.
4. Implement raid/fight grouping and first useful response, with entity mapping and no-response handling. Add local army/counter snapshots and reinforcement participation before judging fight selection.
5. Add military position/time maps and objective access. Separate scout exploration from army presence and control.
6. Define benchmark/normalization methodology and metric coverage thresholds. Only then produce the eight-axis radar with raw evidence and confidence.
7. Harden collection: refreshable discovery, atomic writes, corruption detection, stable schema versions, bounded retries and resumable per-match statuses. Prototype scripts currently use simple cache existence checks and are not a production scheduler.

## Tests and artifacts

- `experiments/replay_analytics/test_tactical_probe.py`: synthetic TC lifetimes, queue integration, hostile damage filtering, attacker villager-kill credit and grid presence. Passed locally.
- Independently checked shared-match TC exposure by second-by-second integration during the initial experiment.
- Eight research timing anchors checked against 90-second Wheelbarrow duration within summary rounding.
- Latest-ten membership, per-player deduplication and null unavailable kill metrics checked after the 19-match batch.
- These checks do not validate tactical scoring, complete parser fidelity, production-grade ingestion or in-game capture on user matches.
- `evidence/findings.json`: coverage and clearly labelled sample results.
- `evidence/latest10-manifest.json`: frozen collection scope.
- `evidence/collection-status.json`: observed availability/errors.
- `metric-plan.json`: machine-readable metric requirements.
- Raw replays, parsed streams, summaries and downloaded source remain at the original local cache path recorded in the evidence; they are not committed.
