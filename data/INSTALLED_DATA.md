# Installed game data

The catalog is populated from the installed game's `cardinal/archives/Attrib.sga`, not the existing AoE4 World mirror. Steam build **24231237**, game-save data version **3637877**. The installed `RelicCardinal.exe` ProductVersion is **16.3.11308.0**. The official release notes contain a matching **16.3.11308** hotfix section; Steam build ID and game version remain distinct identifiers. The historical Abbasid 16.2 simulation retains its own ruleset.

Raw records stay in the gitignored knowledge base at `C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237/`. `decoded/extraction-manifest.json` records each selected asset's SHA-256. `data/game-catalog.json` holds normalized facts, source PBG IDs, archive/locale fingerprints and individual source hashes.

## Reproduce

```powershell
dotnet build tools/game-extract/GameExtract.csproj -c Release
dotnet tools/game-extract/bin/Release/net8.0/GameExtract.dll 'C:/Program Files (x86)/Steam/steamapps/common/Age of Empires IV/cardinal/archives/Attrib.sga' C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237/decoded-all
python scripts/populate_game_catalog.py --decoded C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237/decoded-all --locale C:/Users/Sam/projects/games/kb/aoe4/extract/installed-24231237/LocaleEnglish/en/cardinal.en.ucs --archive 'C:/Program Files (x86)/Steam/steamapps/common/Age of Empires IV/cardinal/archives/Attrib.sga' --steam-build 24231237 --executable-version 16.3.11308.0
python -X utf8 scripts/test_game_catalog.py
python -X utf8 scripts/build_patch_audit.py
```

The English UCS is freshly unpacked from the same installation's `LocaleEnglish.sga` with AOEMods.Essence CLI `sga-unpack`. The CLI is built at `C:/Users/Sam/projects/games/tools/aoe4-essence`, upstream commit `2bb952f292ac9c2a1a1c84019d97b406018f7938`. Build with `dotnet build AOEMods.Essence.CLI/AOEMods.Essence.CLI.csproj -c Release -p:NoWarn=CA2252`; the old upstream library marks APIs as preview. The project extractor pins NuGet `AOEMods.Essence` **0.6.0**.

Extraction decodes **8,330 of 28,059 archive records**, covering every race's squads/entities, shared upgrades/weapons, race metadata and data-version records. The catalog includes all **23 visible playable civilizations and variants** found in root race definitions: **1,291 unit forms, 795 buildings and 1,269 technologies**. Civilization names are localized from installed files. Nonplayable campaign/rogue records, dummy bundles and scenario objects without usable costs/stat fields are excluded. These are definition variants, not unique unit families.

The database is comprehensive for these catalog categories, not every game asset: ability execution graphs, complete state-tree logic, graphics, maps and campaign scripts are not represented as playable stats. Units are linked to their resolved entity; there are no unresolved entity references in the exported scope.

## Semantics

- Unit names and entity references come from squads. HP, armor, costs and training times come from their resolved entity's `health_ext` and `cost_ext`. No unresolved entity references remain in this scope.
- “Base” means the resolved entity definition, which may already bake in civilization changes (for example Chinese extra-TC build time is 75 seconds). Do not apply a generic civilization multiplier again. Runtime buffs and research require their own rule trace.
- `age` comes only from explicit positive age requirements; it stays null when the definition does not specify one. It is not guessed from an ID suffix.
- Repeated RGD keys are preserved as arrays. Collapsing them into an ordinary dictionary would silently discard weapon slots, requirements and modifier properties.
- All referenced weapons are retained as variants. They are not simultaneous attacks. Damage type/min/max, bonuses, wind-up, wind-down and cooldown are raw fields. No DPS or total attack period is invented.
- Movement and range use raw engine units. No unverified tile/metre conversion is applied.
- Malian cattle include their raw resource deposit (500, subtype cattle), 90-gold cost and 15-second train time. Cattle Ranch includes three garrison slots and the named cattle-load action. Passive food income still requires tracing that action's state tree; it is not inferred from a tooltip.
- Costs preserve every nonzero raw resource, including Olive Oil/Silver (`merc_byz`), militia and internal action counters. `displayCost` contains only game-defined production costs; `costLabels` resolves civilization-specific labels from resource definitions. In particular, the same `merc_byz` key displays as Olive Oil for Byzantines and Silver for Macedonian Dynasty. Internal action counters remain in raw `cost` but are not falsely presented as a normal purchase price.
- Requirements preserve positive and negative checks. `present: false` means exclusion, not a required upgrade.
- Technology costs, research times, raw scalar properties, target filters and state-tree references are populated. Scalar properties are not automatically additive/multiplicative modifiers: complete trigger/state-tree execution is unresolved. Do not apply every referenced tech to every unit.
- Localized descriptions are source text. Descriptions using format arguments retain their template and arguments separately.
- Game definitions establish mechanics, not ladder popularity. Observed build completion events remain in `data/build-library.json` with their independent historical patch/sample provenance.

## Patch audit

[Official released notes](https://www.ageofempires.com/news/age-of-empires-iv-patch-16-2-10884/) append 16.3.11214 and **16.3.11308** to the June 18 article. No separate hotfix date is supplied. The latest hotfix lists a console startup fix, not new balance values. [17.0 notes](https://www.ageofempires.com/news/age-of-empires-iv-update-17-0/) were published October 22 as a **preview for October 29**, so these changes are not applied on the October 23 audit date.

`data/patch-audit.json` is the machine-readable ledger. Five selected future changes are cross-checked against installed values (Town Center build time, regular/Gilded Landsknecht food costs, Teardrop Shields food/gold costs); the installed values agree with the preview's before-values. This is not a full transcription of every future change. `scripts/build_patch_audit.py` recreates the ledger after normalization; its reviewed source/date claims must be refreshed when the game updates.

Twelve evidence tests compare **every exported** unit HP/cost/time/armor/speed/population, building HP/armor/cost/time, technology cost/time/scalars/targeting and referenced weapon damage/type/bonus/range/timing fields against independently traversed raw JSON. They also verify all visible civs, repeated keys, source IDs, cattle/ranch records, every referenced extracted binary fingerprint, special-resource costs and the installed archive fingerprint. Equality to source is not an assertion that runtime effects are fully evaluated. No game process was launched or modified.

## Library browse metadata

`scripts/enrich_catalog.py` builds `data/catalog-enrichment.json` from catalog classes, building production/research lists and explicit tier entity transitions. `available` means a unit has a recorded producer, directly or inherited through its tier family; it is not a general assertion that spawned, mercenary or scripted units cannot exist. Cannon and Bombard definitions for Abbasid exist in the archive, but the installed Siege Workshop's production list contains Culverin rather than either definition. The normal Library roster uses the production-backed subset.

Upgrade groups retain the exact same-civilization research building. Tier upgrades use explicit transitions; other relationships require compatible `apply_to_unit_classes` and AI include/exclude filters. The ranged-damage condition is matched using its explicit ranged-infantry/cavalry-archer AI classes and gunpowder/siege exclusions; composite classes are derived from ranged+infantry/cavalry tags. These are browse relationships, not an evaluation of state-tree runtime effects. Archived research buildings (including Arsenal) are preserved when their links exist; no unsupported runtime availability claim is made.

Icons use metadata `iconKey` pointers to one content-hashed asset key in `game-icons.json`, keeping record IDs separate from image bytes. Installed UIArt PNGs are preferred, then exact named/tier local AoE4 World artwork cache files. SHA-256, origin and source paths remain in `game-icons-provenance.json`. Unresolved art stays unavailable rather than borrowing unrelated portraits. Run `python -X utf8 scripts/test_catalog_enrichment.py` to verify all image signatures/hashes/dimensions and key roster/family/research relationships.
