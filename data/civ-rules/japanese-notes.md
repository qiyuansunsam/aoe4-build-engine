# Japanese rule pack: notes

Base Japanese (`catalogCiv: japanese`), installed 16.3.11308. The Sengoku Daimyo variant (`japanese_ha_sen`) is a separate civ and is not covered.

## Evidence conventions used in japanese.json

- `raw:<path>#<field>` without `.rgd` is a record under `decoded-all/attrib/` (record ebps/sbps/upgrade/racebps). Field paths use `/`. A `[n]` index counts repeated keys in record order.
- `raw:<path>.rgd#<field>` is a record that is not in `decoded-all`. These come from `installed-24231237/Attrib-raw/attrib/<path>.rgd` and were decoded with the Essence CLI:
  `dotnet C:/Users/Sam/projects/games/tools/aoe4-essence/AOEMods.Essence.CLI/bin/Release/net6.0/AOEMods.Essence.CLI.dll rgd-decode -f json <in.rgd> <out.json>`.
  Records used: `army/standard_mode/normal_japanese.rgd` (start state, codex trait ids and args), `abilities/always_on_abilities/japanese/*.rgd` (Daimyo aura, Bannerman auras), `abilities/modal_abilities/japanese/monk_shinto_deposit_sacred_object_jpn.rgd` (Yorishiro tooltip args), `statemodel_schema/buildings/civilizations/japanese/*.rgd`, `statemodel_schema/buildings/house.rgd` and `statemodel_schema/civs/japanese.rgd` (population, stockpile, caravan defaults).
- `locale:<id>` is the installed English UCS. Format arguments come from the record named in the same evidence string.

## Which codex text belongs to base Japanese

- `11257921` is the trait list that `normal_japanese` (army record of base Japanese) references. It is the one used.
- `11269892` is referenced by `normal_japanese_ha_sen`, so it is the Sengoku list (Matsuri, Yatai, Daimyo Estates).
- `11247704` is an older copy that no army record uses. It says "Fishing Boats are produced quicker" where current data has 25% cheaper.

## Landmark keys

The `landmarks` keys are the age a landmark advances to. The records are named by the age they are built in: `age1` landmarks (Kura Storehouse, Koka Township) are built in the Dark Age and lead to Feudal, so they sit under `"2"`. Each landmark's `requirement_ext` confirms this: the next age is absent and the current age is present.

## Not in the installed records

State trees are not in `Attrib.sga`. `Data.sga` unpacking with the old CLI fails (`Unknown storage type 18`), and the parts that did unpack hold no state trees. Every value that only a state tree applies is therefore either a schema default (population 10, stockpile 30 s/2, caravan 100/700/160) or a tooltip argument (Yorishiro, Silver Mining, Tawara line, Kura 50 s, Floating Gate 2 min). Those values are marked `partial` in mechanics and listed in `unresolved`.
