# Mathmatically Correct AoE 4

A local strategy workspace rebuilt from `aoe4-build-engine`: compare theoretical plans, explore upgrades at a selected time, and study sourced historical 4v4 openings. The original local path `C:/Users/Sam/projects/MathmaticallyCorrectAoe4` now links to this checkout. See [context](CONTEXT.md) and [design](DESIGN.md).

```powershell
./start.ps1
# Open http://127.0.0.1:8765
```

Build only: `python -X utf8 site/build.py`. Browser verification after starting: `node site/verify.cjs` and `node site/verify-interactions.cjs`; screenshots, interaction recordings and machine-readable reports are written to `site/shots/`. These checks use the existing Playwright tools in `codex-setup/browser-tools`. `site/crafter.css` and `site/crafter.js` are embedded by the builder; edit these source files rather than generated HTML.

The three data sources stay distinct: installed game rules, downloaded historical match completions, and a theoretical Abbasid simulation. The French, Mongol, Malian and Japanese examples are study references, not simulated plans or current ladder rankings. `data/build-library.json` preserves their provenance. The reusable research workflow is installed at `C:/Users/Sam/.codex/skills/aoe-build-crafter`.

The installed database covers **23 civilizations/variants, 1,291 unit forms, 795 buildings and 1,269 technologies**, decoded directly from Steam build **24231237**, executable patch **16.3.11308**. These are variants, not unique unit families. [Reproduction and source evidence](data/INSTALLED_DATA.md) explain extraction, validation and unresolved dynamic effects. [Patch audit](data/patch-audit.json) separates released rules from the upcoming 17.0 preview. Run `python -X utf8 scripts/test_game_catalog.py` to verify normalized values against decoded records and archive hashes.

The neutral glass interfaces, in white and VS Code dark, have Comparison, Builds, a unified Library (Games and Units & civilizations), Crafter and Guide pages. Build plans apply to either comparison slot and open an independent single-build timeline. Build and game filters normalize patch versions; civilization flags cover all23 installed civilizations and variants. Recorded games preserve missing metrics instead of being resimulated as Abbasid. The tracking rail supports configurable metrics and chart previews on hover. Entire tracked rows can be dragged onto the timeline graph to chart them or into the detail area to inspect them; click and keyboard selection remain available. Individual resource income and cumulative spending are chartable. Events live inside the main graph, with expandable clusters and a compact fixed-height graph and event timeline. Units, resources, research, and spending are selected from comparison rows and sit directly below the graph in an independent left column; authentic game icons and hypothetical upgrade toggles show supported stat changes without changing the build timeline. Custom dropdowns support keyboard navigation. Unsupported model effects are labelled explicitly.

Public deployment (Cloudflare + Fly, read-only): [deploy/README.md](deploy/README.md).

The [local API](server/README.md) serves the app and proxies AI text drafting to the existing loopback CLI proxy. Credentials remain server-side. AI proposals stay unvalidated and are saved only when the user chooses. Backend fixture tests: `python -X utf8 -m unittest discover -s server -p 'test_*.py'`.

## Original engine context

A theoretical Age of Empires IV economy engine (cost, rate and time arithmetic at 1 s steps) compares two build paths minute by minute. Its historical baseline remains 16.2.10604 and its implemented civilization is Abbasid Dynasty (3 TC camel build). This baseline is distinct from the installed database; future patch previews are not applied to either automatically.

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

Run locally with `./start.ps1` so AI/API routes are available. Static-only hosting does not provide those routes. Engine smoke test: `node -e "const E=require('./site/engine.js');console.log(E.simulate({}).milestones)"`.

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

Starting parameters and Reset are compact, non-draggable sidebar controls. Scheduled parameter changes are not implemented; their simulation semantics remain a separate scope decision.

The Library separates installed patch records from the limited audited upcoming-patch changes. Blueprint IDs remain in evidence rather than the record listing. Games carry analyzed/reference tags, while Builds retains reusable plans.

### Comparison and build review

Simulation constraints sit above the comparison tracker: idle fraction, one-way resource distances, handling delay and optional timed worker attrition. Build details prioritize ordered actions and worker splits; Expected outcome holds the secondary graph. Games and Library are separate destinations. Craft build creates a browser-local pending reference draft in Builds; Accept build makes it available to Comparison. Build comments and draft acceptance persist only in the current browser. Recorded matches never carry worker splits or action starts; the app shows an income-share worker estimate and inferred starts (completion minus installed base duration), both labelled as estimates. Population, army value and gathered resources for recorded matches are likewise labelled estimates derived in `site/observed-derived.js`, so every comparison metric, tracker row and detail panel works across civilizations and for future reference builds crafted from Games.

The Games collection now restores 5,812 online matches and10 local replay reports from the previous app. There are816 player perspectives across153 matches with timeline data; other records retain match metadata. Timeline sidecars load on demand. Rebuild after `python scripts/restore_game_collection.py` to copy the sidecars into `site/dist/game-perspectives`.
