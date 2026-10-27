# Replay analytics experiment

Runnable research scripts and evidence for the proposed replay analytics feature. This is not a production service or a finished player-rating model. Read [the handover](../../docs/replay-analytics-handover.md) first.

## Run

Requires Python 3.10+ and Node.js 22.20+ with TypeScript stripping. Commands below run from this directory.

```powershell
python -m unittest test_tactical_probe.py
python prepare_sources.py
python collect_latest10.py
python analyze_latest10.py
```

`prepare_sources.py` downloads pinned parser source into ignored `data/`, copies the committed October 27 match manifest and research technology data, and does not launch anything. Review the parser's reuse terms before distributing it; no license file was identified in the inspected upstream tree. The TypeScript probe is our adapter; upstream parser implementation is not committed here.

`collect_latest10.py` collects the **frozen manifest**, not the latest games as of each invocation. It caches summaries, downloads available replays and parses them. It pauses the batch on a summary HTTP 429; unavailable records remain errors. Results and logs belong in ignored `data/`. Incremental discovery and scheduled execution are future work.

`analyze_latest10.py` joins the cached summaries and command streams, enforcing each player's exact manifest membership. It deliberately emits null for enemy villager kills and all radar scores: these need game-state telemetry and score calibration.

`fetch_replays.py` also has a three-match standalone smoke-test entry point; the batch collector calls its `fetch(game, profile)` function for the full manifest.

## Reuse this session's cache

On the original workstation, the existing cache is at `C:/innomate/scratchpad/mcaoe4-exploration`. Copy these files into `data/` to avoid downloading again:

- `latest10-manifest.json`, `metric-tech-data.json`
- `summary-*.txt`
- `replay-*.rec`, `replay-*.download`, `replay-*.parsed.json`, `replay-*.probe.json`, `replay-*.metadata.json`

Do not commit replay data, parsed chat/commands or the cache. `evidence/` contains small public match metadata and aggregate findings only.

## Tactical telemetry sample

`tactical_probe.py` includes a separate proof of concept for the upstream showcase recording. Its standalone entry point expects `data/tactical-recordings_aoe4_245598603.rlog` and the three original summaries/replays. It emits `data/tactical-findings.json`. That sample is May versus Beasty, not any of the four tracked players.

The tested extractor reads queues, positions, visibility and hostile hits. Villager kill credit requires a confirmed villager death and a nearby hostile lethal hit. Unit classification and attribution tolerance remain experimental. The synthetic unit test checks the attacker receives credit, friendly damage is excluded, and TC lifetime integration handles removal.

## In-game recorder

```powershell
python prepare_sources.py --recorder
```

This stages the pinned upstream recorder sources only. The source uses Windows, Steam AoE4, Python `psutil` and in-game developer-console automation. It needs an installed game build compatible with the replay. Review upstream setup before running; this package has not been validated as a complete recorder installation. No game client was launched during this experiment.

Full raw logs and third-party example assets remain outside Git. Source provenance is in `sources.json`; the recorder's MIT license is downloaded alongside its code.
