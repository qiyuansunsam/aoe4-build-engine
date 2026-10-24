# Historical model data baseline

The simulator retains its 16.2 baseline. The installed database is independently verified as **16.3.11308** from executable ProductVersion. See [the current patch audit](patch-audit.json) and [installed extraction](INSTALLED_DATA.md); the 17.0 preview is informational and not applied.

| source | covers | status |
|---|---|---|
| aoe4world/data JSON (units, techs, buildings) | Season 13, patch 16.1.9737 (repo commit 2026-05-04) | STALE: predates 16.2 (2026-06-01). Still valid for generic unit/tech costs that 16.2 did not touch; wrong for Abbasid wings and Golden Age |
| official patch notes 16.2.10604 (ageofempires.com) | historical model baseline | Abbasid section applied to engine/sim.py via engine/_patch_162.py |
| fandom wiki (Administration Wing, Golden Age, Algebra, City Planning pages) | updated to 16.2 | used for tech costs/times the patch notes omit |
| Update 17.0 preview (scheduled 2026-10-29) | future; preview published 2026-10-22 | Announced changes tracked in patch-audit.json; not applied to installed facts or simulation |

## Patch 16.2 Abbasid changes applied
- Trade Wing -> Administrative Wing: no free traders; +50% to every Golden Age tier; techs City Planning (II, 25w 75g 30s, +8% HP and work rate per adjacent identical building, drop-off camps excluded), Siege Directive (III), Grand Bazaar (IV).
- Culture Wing: Algebra (III, 100f 250g 60s) replaces Medical Centers: House of Wisdom generates 3f 3w 2g per military tech researched every 20 s, cap 58/58/38.67.
- Golden Age: 5 tiers at 10/20/30/50/75 buildings: +15% gather, +20% construction speed, +15% Camel Rider damage, +20% trader income, +10% melee infantry damage. The old +20% research speed (30) and +20% gather/research/production (60) are gone.
- Armored Caravans moved to Market, Spice Roads removed. Economic and Military wings unchanged. Camel Rider cost/time unchanged.

## Rule going forward
Before any civ-specific run: check the official news page for the newest patch and diff its civ section against the engine tables. aoe4world data is a convenience mirror, not the source of truth for the live patch.
