# Malian rule pack: provenance notes

`malian.json` holds installed **16.3.11308** values only. No numbers come from matches, guides, wikis or memory.

## Records outside `decoded-all`

`raw:` evidence under these paths is **not** in `decoded-all/attrib`. It was decoded from the same installation's
`Attrib-raw/attrib/<path>.rgd` with AOEMods.Essence CLI `rgd-decode -f json`:

- `statemodel_schema/civs/malian` holds the Malian rate constants: `gold_rate_small_mal`/`gold_rate_large_mal` 36,
  `open_pit_influence_rate_mod_mal` 0.25, `pit_mine_limit_mal` 1, `cattle_ranch_food_rate` 12 + `cattle_ranch_food_amount` 5,
  `cattle_landmark_food_rate_mal` 10 + `cattle_landmark_food_amount_mal` 3, `gold_rate_landmark_mal` 75, `festival_duration_mal` 90,
  `trade_outpost_max_tax_count_mal` 5 and `book_trade_value_mal` 1.
- `statemodel_schema/buildings/civilizations/malian/{house_mal,pit_mine_mal,ranch_mal,landmark_pit_mine_mal,...}`,
  `statemodel_schema/units/civilizations/malian/{cattle_mal,trade_cart_mal,...}`, `statemodel_schema/buildings/{town_center,town_center_capital,house}`
- `army/standard_mode/normal_malian`: start units, start resources, start building, pop/vehicle caps, civ trait text ids
- `abilities/{always_on,timed,toggle}_abilities/malian/*`: Corral range 25, taxation aura, Griot Bara festivals, quarry toggles
- `player_slot_starting_conditions/dark_age_start`

Reproduce (Git Bash, `DOTNET_ROLL_FORWARD=Major`):

```
dotnet C:/Users/Sam/projects/games/tools/aoe4-essence/AOEMods.Essence.CLI/bin/Release/net6.0/AOEMods.Essence.CLI.dll \
  rgd-decode -f json <installed-24231237>/Attrib-raw/attrib/statemodel_schema/civs/malian.rgd out.json
```

## Reading the statemodel constants

The schema defaults are raw numbers. Their meaning comes from property names and matching tooltips:

- `cattle_ranch_food_rate` 12 and `cattle_ranch_food_amount` 5 read as 5 food per 12 s = 25/min. That equals the Ranch
  tooltip (locale 11222100, argument 25).
- `cattle_landmark_food_rate_mal` 10 and `..._amount_mal` 3 read as 3 food per 10 s = 18/min. That equals the Corral tooltip
  (11231847, argument 18). The official 17.0 note's before-value (18 → 16) agrees.
- `gold_rate_*_mal` 36 equals the Pit Mine tooltip (11215109, argument 36, "per minute"). `open_pit_influence_rate_mod_mal`
  0.25 equals 11221856 ("+25% for each House or Mining Camp").

The executing logic lives in compiled state trees, in `Data.sga` → `statetrees/simulation/statetree.bin`. That binary
contains the names (`open_pit_mine_influence_mal`, `MalRanchFoodProduction`, `pit_mine_limit_mal`,
`cattle_ranch_festival_buff`, …) but was not decoded. Stacking, caps and depletion therefore stay `partial` or
`unresolved` in the pack.

## Tooltip text versions

The current records reference **11221856** (+25% per House **or Mining Camp**, argument 25). Records that reference it:
the Pit Mine `ui_extra_info`, House, Mining Camp, and the `open_pit_mine_influence_gen_mal` ability. Ids 11215155 (0.5% per
House) and 11221859 (+25% per House or Mine) are older strings that none of these records reference.

## Key conventions

- Building keys are kebab-case like `site/engine.js` (`lumber-camp`, `mining-camp`, `cattle-ranch`, `pit-mine`).
- A landmark sits under the age it **advances to**: `"2"` holds the Dark-Age options for reaching Feudal.
- Each landmark has a `key`. Techs from Farimba Garrison use the building value `landmark:farimba-garrison`.
- `start.units` excludes villagers, which are counted in `start.villagers`.
