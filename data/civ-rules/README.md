# Civilization rule packs for the theoretical engine

One file per civilization (`french.json`, `mongol.json`, `malian.json`, `japanese.json`, `scots.json`, `vikings.json`). Each pack holds the
installed **17.0.12260** rules the multi-civilization engine (`site/engine-civs.js`) needs: start state,
villager gather rates, buildings, Town Center behaviour, landmark options, technologies, the army lines a
build uses, and civilization mechanics. Every value carries evidence; nothing is copied from recorded games
or guides.

## Evidence strings

- `catalog:<units|buildings|technologies>/<id>#<field>` — data/game-catalog.json (installed 17.0.12260 normalized)
- `raw:<path under decoded-all/attrib>#<field path>` — decoded installed Attrib records
  (`C:/Users/Sam/projects/games/kb/aoe4/extract/installed-26400362/decoded-all/attrib/...`; records the extractor does not decode,
  such as `statemodel_schema`, `abilities` and `army`, are read from the raw unpack `installed-26400362/Attrib-raw/attrib/...rgd`)
- `locale:<id>` — installed English locale (`LocaleEnglish/en/cardinal.en.ucs`), with any format arguments
  filled from the record's `descriptionArguments`
- `jeando17:<record>` — datamined 17.0 record, only where the 17.0 notes list no change to that value
- `aoe4world16.1:<file>#<id>` — last resort; always flagged in `unresolved`

## Schema

```
{
  civ, catalogCiv, patch: "17.0.12260",
  start: { villagers, resources{food,wood,gold,stone}, popCap, units[{id,name,count}], buildings[{id,name,count}], evidence[] },
  villager: { id, cost{}, trainSeconds, speedEngineUnits, gather: { <source>: { rate /*res per s*/, carry, evidence[] } }, evidence[] },
      sources: sheep, berries, deer, boar, farm, wood, gold, stone, plus civ-specific keys (cattle, pasture_sheep, ...)
  townCenter: { id, extraId, cost{}, buildSeconds, popProvided, villagerProductionMultiplierByAge{"1".."4"}, notes, evidence[] },
  buildings: { <key>: { id, name, cost{}, buildSeconds, age, popProvided, dropoff[resources], limit, notes, evidence[] } },
  landmarks: { "2": [ { id, name, cost{}, buildSeconds, effects[effect], evidence[] } ], "3": [...], "4": [...] },
  technologies: [ { id, name, age, building, cost{}, researchSeconds, category, effects[effect], evidence[] } ],
      category: economy | military | unit-tier | landmark | civ-economy | other
  army: { lines: [ { key, name, producers[buildingKey], tiers[{ id, name, age, cost{}, trainSeconds, pop, hp }],
                     tierUpgrades[techId], applicableTechs[techId], evidence[] } ] },
  mechanics: [ { key, summary, params{}, status: resolved | partial | unresolved, evidence[] } ],
  unresolved: [ { item, why, fallback } ]
}
effect = { kind, target, op: mul | add | set, value, notes }
   kind: gather_rate | carry | speed | production_speed | research_speed | build_speed | cost | passive_income | pop | unlock | other
```

Ages are 1 Dark, 2 Feudal, 3 Castle, 4 Imperial. Costs use food/wood/gold/stone keys (other resources by
their catalog key). Time in seconds, rates in resource per second unless a field name says otherwise.

## Patch 17.0.12260 re-check (2026-11-06)

The four standard packs were written on 16.3.11308 and the Vikings and Scots packs before release from datamined 17.0 records.
`python -X utf8 scripts/verify_rule_packs_17.py` resolves every `catalog:`, `raw:` and `locale:` reference in both patches, compares
every pack object that carries an installed record id (cost, build / train / research seconds, health, population, speed) with the
installed 17.0.12260 record, and compares the villager gather table and start state with the installed villager and army records.
The result is `patch-17-recheck.json`: per pack the references checked, unchanged and changed (old and new value), the pack values
compared, and under `applied` every value the re-check changed. After the changes no pack value differs from its installed record.

Changed values: extra Town Center build time 150 -> 165 s (all four standard packs), Mongol packed Town Center speed 3 -> 3.6,
Grand Fulani Corral 3 food per 10 s -> 4 food per 15 s per nearby cattle, Smithy / Pasture and Loom automatic research 270 -> 300 s,
Kongens Dør tithe 10 -> 12.5 gold per Longhouse, the trained Tacksman is the installed `unit_handcannon_4_sco`.

## Vikings and Scots

`vikings.json` and `scots.json` keep their pre-release evidence strings beside the installed ones: `jeando17:<record id>#<field>`
(datamined 17.0 records, `data/upcoming-civs/raw/jeando/`), `checklist:<civ>/<kind>/<name>#<field>` (`data/upcoming-civs/checklist.json`,
every source quote) and `frame:<videoId>@<mm:ss>`. Ids ending in `__scots` / `__vikings` stand in for the shared standard technology of
the same name; the compiled rules carry the installed pbgid of every record (the shared record's for a stand-in). Values no installed
record in the decoded scope gives (saga goals, Mustering Hall tiers, map and placement assumptions) are listed under `notCompared` in
`patch-17-recheck.json`. Their compile glue is `scripts/civ_glue/<civ>.py`, their engine mechanics `site/civ-mech/<civ>.js`, their
plans `scripts/theory-plans/<civ>.cjs`.
