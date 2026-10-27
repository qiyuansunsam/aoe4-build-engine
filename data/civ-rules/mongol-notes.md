# Mongol rule pack notes (installed 16.3.11308)

`mongol.json` was generated from installed records only. Values that appear in a pack field were read from the
catalog or raw records at generation time, with a few exceptions: tooltip arguments, and the 90 s legacy string kept as a candidate.

## Evidence conventions used here

- `raw:<path>.json#<key>`: decoded-all record (`installed-24231237/decoded-all/attrib/<path>`), key = flattened
  `{key,value}` path joined with `/` (repeated keys indexed `[n]`), first segment is the variant (`default`, `campaign`, `xp3`).
- `raw:<path>.rgd#<key>`: a record that is not in decoded-all. It was decoded from
  `installed-24231237/Attrib-raw/attrib/<path>.rgd` with the AOEMods.Essence CLI (`rgd-decode -f json`, build at
  `C:/Users/Sam/projects/games/tools/aoe4-essence`). Records read this way: `army/standard_mode/normal_mongol.rgd` (start
  state), `normal_english.rgd` (comparison), `statemodel_schema/civs/mongols.rgd` and
  `statemodel_schema/buildings/civilizations/mongols/*.rgd` (Dark Age Ovoo rate, raid bounty, Silk Road, Yam, unpack
  times), `abilities/*/mongol/*.rgd`, `ebps/gaia/animals/gaia_herdable_sheep*.rgd` and
  `ebps/gameplay/resources/stone/resource_stone_deposit*.rgd`.
- `locale:<id>`: installed English UCS. For the civilization bonus list the pack uses the army record's live formatter
  `11227209` with arguments `[25,25,15,10,5,10,15,50,15]` from `normal_mongol.rgd ... global_traits_summary/trait[0]`.
  The codex list `11197943` is a historical copy and was not used for any value. It says +50 plunder and Early Lancers.

## Choices that matter to the engine

- Only the `default` record variant is used. Its Ovoo rates (1.167/1.67/2.34/2.84 stone/s) match the live tooltips
  (70/100/140/170 per minute). The `xp3` variant (Castle 2.0, Imperial 2.5) does not match, and neither do campaign variants.
- `technologies[]` lists only techs that a default-variant Mongol building can research. Records like Husbandry and the
  Castle/Imperial Improved eco techs exist, but no standard building lists them, so they are left out. They are noted in
  `mechanics.pasture` and `unresolved`.
- `*_moving_*` records are the packed form of the same building. `*_double_*` records are double-production items
  (the same entity, `number_to_spawn` 2, cost adjustment). Neither becomes a separate building or unit.
- Horseman train time 18 s already contains the +25% civ bonus.
