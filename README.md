# aoe4-build-engine

A theoretical Age of Empires IV economy engine (no game simulation: cost, rate and time arithmetic at 1 s steps) and a dashboard that compares two build paths minute by minute. Current patch target: 16.2.10604. Current civ: Abbasid Dynasty (3 TC camel build). Scots arrive with Update 17.0 on 2026-10-29 and are the next target.

## Layout

| path | what |
|---|---|
| `MODEL.md` | the model: gather rate with walking, node depletion, farm and drop-off payback, TC-capped growth, army metric, acceptance rule for every number |
| `PARAMS.md` | every parameter with source and confidence, calibration against the only published measurements |
| `engine/eco.py`, `engine/sim.py` | Python reference engine (grid searches, calibration); `engine/calibrate.py`, `engine/params_report.py`, `engine/summarize_grid.py` |
| `engine/export_timeline.py` | Python run with full event logging (legacy JSON export) |
| `site/engine.js` | JavaScript port of the engine; runs in the browser, `simulate(params)` returns the run object below |
| `site/index.template.html` | current dashboard (single file after `python site/build.py` -> `site/dist/index.html`) |
| `site/wrangler.jsonc` | Cloudflare Workers static-assets deploy config |
| `data/` | game data dumps (aoe4world JSON, patch 16.1), fandom wikitext, forum measurements, `PATCH_STATUS.md` (what is stale and what was applied by hand) |
| `RESULTS_abbasid_wings.md`, `results_wings_grid.csv` | wing-order grid results |

Run locally: `python site/build.py && cd site/dist && python -m http.server 8765`. Engine parity test: `node -e "const E=require('./site/engine.js');console.log(E.simulate({}).milestones)"`.

## Run object (the contract a new UI builds against)

`simulate(params)` returns:

```
{
  params,                       // resolved parameters (wings, vilTarget, stables, blacksmiths, map, idle, stacking ...)
  milestones: {age2, tc2, tc3, age3, age4, first_camel, golden1..5, <tech-name>, all_camel_techs, pop200, DONE},  // seconds
  done,                         // seconds to target
  events: [{t, kind, cat, label, trigger, effect, cost{food,wood,gold,stone}, stock, vil, camels, pop, age}],
          // kind: build | done | tech | age | farm | golden | vil | army ; cat: building | economy | wing | blacksmith | camel | university | age | golden | production
  minutes: [{t, vil, camels, pop, farms, houses, age, golden, tcs, stables, blacksmiths, builders,
             split{food,wood,gold,stone,builders}, sources{sheep,berries,deer,farBerries,farm}, stockLeft{...},
             income{food,wood,gold,stone}, algebra{...}, stock{...}, spent{...},
             spentCat{villagers,units,buildings_eco,buildings_prod,techs_eco,techs_mil,ages},
             perVil{farm,berries,sheep,wood,gold}, gatherMult, techs, produced, unitsProduced, armyValue, partial?}],
  techs: [{name, cat, building, age, baseCost, planned, available, start, end, duration, paid, costPaid, payback, gain, saved, gainAt{minute: res}}],
  summary: {villagers, camels, farms, houses, buildings{...}, spent, spentCat, banked, freeUnits}
}
```

A comparison page takes two such runs (any civ once the engine has that civ's plan and tech table) and a `UNIT` table for the unit cards.

## UI/UX overhaul brief (next)

The current page is a working instrument, not a product. Known problems, in the owner's words: everything is first level and depth is not used; too much content and too many words; nothing to hover on the overview (techs per unit, units); hard to use. It must be impressive.

Direction for the rebuild:

1. One screen first. Header with the two finish times, the event timeline as the master control, one dominant chart. Everything else is depth: hover a unit to see its stats and the techs that shaped it; hover a tech to see start, cost and what it has earned back at the cursor; click to pin.
2. Comparison, not dashboards. Two paths on the same axes everywhere; difference readouts rather than two numbers. Generalise the scenario card to any civilization: the plan builder, wing/landmark choice and unique techs come from a per-civ table, the comparison UI does not know about Abbasid.
3. Word budget. Labels of three words or fewer; the explanation of the model lives in one "how it works" sheet, not on the surface. Numbers are shown where they change a decision.
4. Depth map: overview (finish, timeline, growth) -> at-a-minute (state, income, split, units) -> per object (unit card, tech card, building card) -> model (parameters, assumptions, sources).
5. Keep the engine in the browser; every control re-simulates live.

## Model caveats carried

Map distances are estimates (editable), builder formula 3/(n+2) unverified, stacking walk penalty and idle fraction are parameters, no raids beyond the far-food escort rule. See `PARAMS.md` and `data/PATCH_STATUS.md`.
