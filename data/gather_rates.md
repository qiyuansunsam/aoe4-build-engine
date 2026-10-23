# Villager gather rates (generic civ baseline), 2026-10-23

Sources: aoe4world/data (Season 13 patch 16.1.9737, May 2026; villager.json, tech_all.json), AoE4 fandom wiki Resource page (resource_api.json, gather table), Villager page (tech bonus rows). No Scots data exists anywhere yet: Raiders of the North releases 2026-10-29 with Update 17.0, full notes due then.

## Confirmed from game data (aoe4world villager.json)
- Villager: 50 food, 20 s (French 19, Golden Horde 37), speed 1.125 tiles/s, HP 50.
- Carry 10 all resources, 25 hunted meat (wiki Villager page).
- Wheelbarrow: +5 carry, +15% speed (Dark, 50w 150g, 90 s).
- Food techs (not hunt, not fish): Horticulture +10% (F), Fertilization +10% (C), Precision Cross-Breeding +10% (I).
- Hunt: Survival Techniques +15% (Dark).
- Wood: Double Broadax +15% (F), Lumber Preservation +15% (C), Crosscut Saw +15% and +5 carry (I).
- Gold/stone: Specialized Pick +15% (F), Shaft Mining +15% (C), Cupellation +15% drop-off (I).
- Stacking: multiplicative. Check: Mongol "improved" variants say +35% alone or +17% if base already researched; 1.15 x 1.17 = 1.3455, matches +35%. Same for +30%/+18% (1.1 x 1.18) and +25%/+9% (1.15 x 1.09). Additive stacking would have printed +20%, +20%, +10%.

## Raw rates (res/s, wiki table, generic civ)
sheep 0.75 (HoL 0.9), farm 0.75, berries 0.69 (Abbasid/Ayyubid/Delhi 0.8625), deer 0.825, boar 0.9, shoreline fish 1.0, wood 0.75 (Templar 0.6), gold 0.75 all vein sizes, stone: table cut off, assumed 0.75 (shares every gold tech), unconfirmed.
Node amounts: sheep 200, berry bush 250, deer 350, boar 2400, tree 150, gold 1600/4000/8000, stone 1200/2400.

## Model output (MODEL.md 2.1): r_eff = C / (C/r + 2d/v + t_turn), t_turn = 0.8 s
t_turn derived from one player's measured effective rates (farm 0.625 at d=1 gives 0.89 s, berries 0.66 at d=0 gives 0.66 s). Single observer, unconfirmed.

| res | raw | Dark eff | Feudal raw/eff | Castle raw/eff | Imperial raw/eff | d, C |
|---|---|---|---|---|---|---|
| sheep | 0.750 | 0.666 | 0.825/0.759 | 0.908/0.829 | 0.998/0.904 | 0.5, 10 |
| farm | 0.750 | 0.628 | 0.825/0.731 | 0.908/0.795 | 0.998/0.863 | 1, 10 |
| berries | 0.690 | 0.586 | 0.759/0.678 | 0.835/0.738 | 0.918/0.803 | 1, 10 |
| deer | 0.825 | 0.760 | 0.949/0.871 | same | same | 1, 25 |
| boar | 0.900 | 0.824 | 1.035/0.943 | same | same | 1, 25 |
| wood | 0.750 | 0.595 | 0.862/0.731 | 0.992/0.822 | 1.141/0.922 | 1.5, 10 |
| gold | 0.750 | 0.628 | 0.862/0.760 | 0.992/0.859 | 1.141/0.968 | 1, 10 |

Feudal+ columns include Wheelbarrow (C 15, v 1.294). Imperial wood C 20.
Weighted average (50% food on sheep, 35% wood, 15% gold): Dark 0.635, Feudal with tier-1 techs 0.75 res/s per villager.
Sustain check: one TC needs 2.5 food/s, that is 3.8 villagers on sheep at d 0.5. Consistent with the 6-villager all-food opening.

## Scots (pre-release, no numbers)
- Villager rates: no bonus announced, so generic baseline until 17.0 notes.
- Highland Wealth: start with one Highland Cattle that generates food over time while grazing at Berry Bushes (passive income, MODEL.md 2.9 slot: rate, cap, bushes consumed?). Tower Houses produce and shelter cattle. Fishponds also mentioned.
- Landmarks: Abbey of the Isles (relic, healing, research/production speed), Stone of Destiny (nearby building cost partly refunded as gold, early Kirkmen), Snowdoun Gate (free infantry), Tower of Skye, Dun Eideann, Three Loch Lookout.
- Unique units: Border Reiver, Cateran, Gallowglass, Ghillie, Highland Archer, Kirkmen, Lochaber Men-at-Arms, Pikemen (schiltron).
