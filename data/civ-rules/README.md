# Civilization rule packs for the theoretical engine

One file per civilization (`french.json`, `mongol.json`, `malian.json`, `japanese.json`). Each pack holds the
installed **16.3.11308** rules the multi-civilization engine (`site/engine-civs.js`) needs: start state,
villager gather rates, buildings, Town Center behaviour, landmark options, technologies, the army lines a
build uses, and civilization mechanics. Every value carries evidence; nothing is copied from recorded games
or guides.

## Evidence strings

- `catalog:<units|buildings|technologies>/<id>#<field>` — data/game-catalog.json (installed 16.3 normalized)
- `raw:<path under decoded-all/attrib>#<field path>` — decoded installed Attrib records
  (`C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237/decoded-all/attrib/...`)
- `locale:<id>` — installed English locale (`LocaleEnglish/en/cardinal.en.ucs`), with any format arguments
  filled from the record's `descriptionArguments`
- `jeando17:<record>` — datamined 17.0 record, only where the 17.0 notes list no change to that value
- `aoe4world16.1:<file>#<id>` — last resort; always flagged in `unresolved`

## Schema

```
{
  civ, catalogCiv, patch: "16.3.11308",
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

## Preview civilizations (Vikings, Scots)

`vikings.json` and `scots.json` target `patch: "17.0-preview"` (Update 17.0 ships 2026-10-29). Their evidence strings are
`jeando17:<record id>#<field>` (datamined 17.0 records, `data/upcoming-civs/raw/jeando/`), `checklist:<civ>/<kind>/<name>#<field>`
(`data/upcoming-civs/checklist.json`, every source quote) and `frame:<videoId>@<mm:ss>`; ids are the 17.0 record ids, which the
compiled rules use in place of installed pbgids. Their compile glue is `scripts/civ_glue/<civ>.py`, their engine mechanics
`site/civ-mech/<civ>.js`, their plans `scripts/theory-plans/<civ>.cjs`. Re-derive both packs from the installed files once
17.0 is extracted (`data/INSTALLED_DATA.md`).
