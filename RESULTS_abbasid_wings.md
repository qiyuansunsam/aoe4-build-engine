# Abbasid 3 TC wing orders on patch 16.2.10604, target = all Camel Rider techs + 200 pop (v3, 2026-10-23)

Engine: engine/sim.py after engine/_patch_162.py (Administrative Wing, 5-tier Golden Age, Algebra, City Planning; see data/PATCH_STATUS.md). Grid: all 24 orders of 3 wings from {Economic, Culture, Administrative, Military} x villagers {120, 140} x eco-tech timing {asap, late, minimal} x blacksmiths {1, 2} x City Planning farm adjacency {0, 3} (admin orders only). Fixed: 3 TCs before Castle, 5 stables, continuous camel production. Raw: results_wings_grid.csv, summary: results_wings_summary.txt.

v1 and v2 of this file ran on the Season 13 wing set (Trade Wing with traders, 3-tier Golden Age with research and production speed). Those results are void for the live patch.

## Results (best of the remaining knobs for each row)

| question | answer |
|---|---|
| Castle wing with Economic at Feudal | Administrative 17:44 (17:52 if City Planning does not touch farms), Culture 18:02, Military 18:02 |
| Feudal wing | Military 17:26, Culture 17:29, Administrative 17:33, Economic 17:44 |
| fastest order found | Military -> Administrative -> Culture, 17:26 (Feudal 4:14, TC3 7:36, Castle 9:33, Imperial 15:03, 2 blacksmiths, tier-3 eco techs skipped) |
| close second | Culture -> Administrative -> Economic, 17:29, techs done 16:47, 2,200 res cheaper |
| blacksmiths | 1: best 18:50; 2: best 17:26. Research chain is the binding constraint now that Golden Age no longer speeds research |
| Golden Age tiers (all buildings in influence) | 10 at 5:49 to 6:23, 20 at 8:56 to 9:42, 30 at 10:19 to 11:11; tier 50 not reached before the finish in most runs |
| City Planning on farms (0 vs 3 neighbours) | 0 to 10 s |
| eco-tech timing | asap vs late vs skip tier 3: 5 s apart; skipping tier 3 saves 3,000 to 3,500 res at no time cost |
| villagers | 120 and 140 finish identically in every order |
| spread of all 468 runs | 17:26 to about 20:00 |

## Reading

1. Culture vs Administrative at Castle (your original question, Economic Feudal): Administrative by 10 to 18 s. Administrative's +50% on Golden Age gives +22.5% gather from tier 1 and +30% build speed from tier 2 for the whole Castle Age; Culture's Preservation of Knowledge saves 20% on techs and the Imperial wing, and Algebra (Castle) returns 9f 9w 6g per minute per military tech, about 6 res/s once 15 techs are in. Those two packages are within one controller tick of each other, so call it a tie with a lean to Administrative.
2. Economic at Feudal is the slowest Feudal wing for this goal on 16.2 too. Fresh Foodstuffs is a plain mill tech; the wing's own content (Fertile Crescent, Agriculture, Improved Processing) is worth about 3,000 res, less than Culture's PoK + Algebra or Administrative's Golden Age multiplier applied from 6:00.
3. Military at Feudal wins only because 2 Spearmen + 2 Archers fill 4 pop slots for free and Boot Camp is skipped; it is an artefact of the 200-pop finish line, not a camel strategy.
4. The second blacksmith is worth 1.5 minutes, more than any wing choice. The research chain (9 blacksmith techs at 60 s each plus stable techs) is the critical path.
5. Everything here is from a hand-written plan executed by a deficit-driven allocator. Differences under 30 s are inside the controller's own noise.

## Assumptions carried (grade C unless noted)

- Golden Age: every building (farms included) inside House of Wisdom influence.
- City Planning: "work rate" taken to include farm gather rate (variant 3) or not (variant 0); 5 stables in a row (1.6 neighbours each).
- Algebra counts blacksmith, stable, Military Academy and Biology techs (15), capped per the wiki.
- Map distances, 3/(n+2) builder formula, TC pop value 10, no raids, no idle time, 5 stables fixed.
- Update 17.0 (2026-10-29) will change TC build time to 165 s and City Planning HP coverage; rerun after its notes.

## v3.1 addendum: the two-scenario question (2026-10-23)

Scenarios: A = Economic, Culture, Administrative. B = Economic, Administrative, Military. Both: 120 villagers, 5 stables, tier-3 eco techs skipped, Feudal eco techs either researched in Feudal or held until after the Castle wing (so PoK discounts them in A). City Planning stacking in B: 3 TCs touching (villager production +10.7%), 5 stables in a row (+12.8%), 2 blacksmiths touching (+8%), farms 0 or 3 neighbours.

| castle wing | Feudal eco techs | blacksmiths | CP farms | 200 pop | all techs | finish |
|---|---|---|---|---|---|---|
| Culture | Feudal | 1 | - | 18:25 | 19:15 | 19:15 |
| Culture | Feudal | 2 | - | 18:15 | 16:46 | 18:15 |
| Culture | after Castle | 1 | - | 18:23 | 19:30 | 19:30 |
| Culture | after Castle | 2 | - | 18:17 | 16:28 | 18:17 |
| Administrative | Feudal | 1 | 0 | 18:01 | 19:08 | 19:08 |
| Administrative | Feudal | 2 | 0 | 17:56 | 17:19 | 17:56 |
| Administrative | Feudal | 2 | 3 | 17:41 | 16:48 | 17:41 |
| Administrative | after Castle | 1 | 0 | 17:57 | 19:07 | 19:07 |
| Administrative | after Castle | 2 | 0 | 17:55 | 17:03 | 17:55 |
| Administrative | after Castle | 2 | 3 | 18:02 | 16:37 | 18:02 |

Holding Feudal eco techs until Castle brings TC3 from 7:30 to 7:09 and Castle from 9:45 to 9:22 in both scenarios, and changes the 200-pop time by under 10 s; it is not a Culture-specific gain. Resources banked at the finish are 5,000 to 13,000 food, so 200 pop is bound by the five stables (80 camels x 28 s / 5) and the research chain, not by income; that is why Administrative's production bonuses (Golden Age tier 2 build speed, City Planning on stables and TCs) beat Culture's discounts here.
