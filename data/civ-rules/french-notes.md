# French rule pack: notes

Source: installed 16.3.11308 records only (catalog, decoded-all, Attrib-raw decoded with the Essence CLI `rgd-decode`, installed English UCS). No match data, guides or wikis.

## Conventions beyond the README

- `raw:Attrib-raw/<path>.rgd#<variant>/<field>`: a record that is not in decoded-all (abilities, buff_info, army, statemodel_schema). It was decoded from `installed-24231237/Attrib-raw/attrib/` with `AOEMods.Essence.CLI rgd-decode -f json`, which uses the same `GameDataJsonUtil` as `tools/game-extract`.
- Evidence strings may carry ` | <gloss>` after the token, giving the filled locale text or a short note.
- Extra keys: `baseCost` (cost before the French or Royal Institute discount), `alsoAt` (other buildings that research the tech), `notes`, and `townCenter.villagerProductionMultiplierByAgeAlternative`.
- Gather-effect `target` is an array of `villager.gather` keys. Other targets are strings.
- `landmarks["N"]` lists the landmarks that advance to age N. Record ids keep their old age labels: `age3_le_grande_university` is the Castle landmark and `age2_la_chateau_rouge` is the Imperial one. This was checked against their requirements and `ageN_landmarkM` unit types.

## Where the values stop

Every runtime effect runs through state trees: TC bonus, discounts, School of Cavalry, free Blacksmith techs, Guild Hall and influence. None of the installed archives contain state-tree data; Attrib, ReferenceAttributes (an XML mirror of Attrib) and Data were all checked. Values therefore come from raw upgrade floats where they exist, and otherwise from the record's own tooltip formatter arguments. Each case is listed in `unresolved`.

The TC bonus conflict is the main open item. The current army record's civ-summary formatter gives `[50, 35, 15, 15, 20, 25]`. The first two values match raw data: drop-offs cost 25 wood against 50 for other civs, and the trait multiplier is 0.65. The TC's own passive abilities show 10/15/20 and have no Imperial record. Those numbers match codex copy 11197894, which also states a stale 30% tech discount. The pack uses 15/15/20/25 and keeps 10/15/20/20 as the alternative.
