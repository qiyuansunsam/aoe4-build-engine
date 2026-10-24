# Four reference builds: source audit

The four entries are recorded historical 4v4 perspectives, not executable plans certified by the Abbasid simulator. They retain every recorded completion time and recorded resource sample. Starts, worker allocation, exact live army strength and a gathered-resource curve are not reconstructed.

| Build | Completion/age event groups | Resource samples | Source match |
|---|---:|---:|---|
| French cavalry opening | 574 | 144 | 253765646 / 23172989 |
| Mongol stable opening | 168 | 66 | 254429285 / 24672417 |
| Malian cow boom | 319 | 82 | 254443718 / 7195780 |
| Japanese two-TC | 443 | 78 | 254451193 / 24222589 |

## Catalog coverage

The installed catalog already contains 1,291 unit records across 23 playable civilization namespaces, including 53 French, 101 Mongol, 52 Malian and 67 Japanese records. All trainable unit blueprint IDs in these four matches resolve to installed catalog records with base statistics and source fingerprints. The missing Japanese ID 2138188 is a dropped melee banner, not an extra soldier. Missing Mongol squad IDs are packed building forms; their timeline labels now identify this state instead of implying new construction.

The special IDs are verified under decoded-all/attrib: sbps/races/mongol/buildings/*_moving_mon and ebps/races/japanese/units/bannerman_samurai/melee_dropped_banner_jpn. Unpacked names are taken from corresponding installed building records.

## Resource and unit accounting

Final totalResourcesGathered and totalResourcesSpent are preserved separately. In the French, Mongol and Japanese sources the final resources.<resource>Gathered sample equals final totalResourcesSpent for all four resources. The Malian source is within one late spending interval. Therefore these misleading series are not treated as true gathered curves. Existing inferred spending snapshots retain this uncertainty in seriesEvidence and caveats.

Unit counts are recorded finished minus destroyed entries, not a certified standing army. Upgrades may leave old-tier bookkeeping rows; transformed lists are empty in these sources. No unproven transfer or cost reconstruction is applied. Japanese dropped banners are excluded.

scripts/export_game_library.py now updates only the four curated perspectives in place and preserves all other matches, downloaded perspectives and player-search metadata. It also populates completionRows, sourceGameId and full build steps; the former first-completion-only and 12-minute truncation are removed.

Verification: python -X utf8 scripts/test_reference_builds.py checks all source timestamp arrays, counted completion coverage, full steps, exact final totals, unknown gathered series, military catalog coverage, installed provenance, and retention of the larger collection.

## Comparable base-cost army estimates

`site/observed-army.js` provides an explicit estimate from positive recorded production-minus-loss balances multiplied by the installed catalog's base food, wood, gold and stone costs. It returns per-unit cost, per-unit total, resource distribution and army total. All 370 snapshots in the four curated references have military cost coverage. Empty recorded armies return zero; missing observations or unresolved catalog costs return an unknown total with a separate known subtotal.

This values recorded balances; it does not infer live survivors, fix unresolved tier transfers, charge for actual training, apply civilization discounts, add research spending or price non-resource tokens. Free/respawned heroes can still have a catalog base cost, so this is not a resource-spending curve. `scripts/test_observed_army.cjs` checks every curated snapshot against source counts and catalog costs plus unknown and zero-cost cases.
