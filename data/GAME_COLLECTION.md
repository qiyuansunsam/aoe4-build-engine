# Restored game collection

`scripts/restore_game_collection.py` reads the retained `../mcaoe` collection without changing it. The earlier `export_game_library.py` selected only the four curated build examples; it did not import the complete collection.

The restored index contains:

- 5,780 online match metadata records from `data/strategy/metadata.jsonl` (also present in the collection SQLite database).
- 32 additional matches from the 40-record `data/engine/feed/feed.sqlite3` cache; the other eight were duplicates by game ID.
- 143 downloaded match summaries, containing 756 distinct player perspectives.
- 10 local stats/replay reports containing 60 player perspectives. Local file dates are not presented as match start dates, and unknown patches remain unknown.

`game-library.json` separates unique `matches` from player-perspective `games`. The four curated perspective records retain their original events, snapshots and accounting interpretation. The other 812 perspectives load from `game-perspectives/<id>.json`; the index contains counts and identity metadata only. The build copies those sidecars to the same relative URL under `site/dist`.

For newly imported online perspectives, resource snapshots use original source values at original timestamps sampled at least one minute apart, plus the final sample. No income-derived worker counts are created. Per-time gathered resources, population, army value and worker splits are not recorded; the app derives labelled estimates at view time (see DESIGN.md and `site/observed-derived.js`). Completion rows preserve the source's full produced, constructed, destroyed and transformed timestamps; summary events identify the first recorded completion of each object. These are observed completions, not a decoded command stream or a validated executable build.

Run `python -X utf8 scripts/restore_game_collection.py` to refresh the index and sidecars. Run `python -X utf8 scripts/test_restored_games.py` to verify match identity, perspective links, sidecar counts and resource samples against their source files. No network download is performed by this importer.
