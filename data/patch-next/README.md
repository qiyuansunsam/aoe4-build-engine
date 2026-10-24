# patch-next: Update 17.0 overlay

`data/patch-next.json` is the Age of Empires IV **Update 17.0** preview notes
(published 2026-10-22, scheduled 2026-10-29) transcribed as an overlay on the
installed-build catalog `data/game-catalog.json`. The Library page's **Next**
toggle applies it; the catalog itself is unchanged (installed build 16.3.11308).

## Regenerate

```powershell
python -X utf8 scripts/build_patch_next.py
```

The script is declarative: every change is a hand-written rule that names the
catalog record id(s), the field path and the value from the notes. `current` is
read from the catalog at run time. The script fails loudly if a record id or
weapon/bonus path does not exist, if a `noteText` is not a verbatim line of the
raw notes, or if the same (record, field) is emitted twice. It prints the counts
and the mismatches when it finishes.

Raw inputs under `raw/`:

- `update-17-0-page.html` - the page as downloaded 2026-10-24 00:01 local
  (sha256 `3bb96609f9f97ed6a1e337da1a98237a3e18945a63d5231b57412fc55483820e`).
- `update-17-0-page.txt` - plain-text rendering of the article body.
- `update-17-0-balance.txt` - the lines actually relied on (The Crucible,
  Balance & Bugfixes, all civilization sections). Every `noteText` in the JSON
  is a verbatim line from this file.

If the article is edited before release, re-download it, regenerate the text
(an HTML-to-text pass that keeps `li`/heading structure is enough), diff
`raw/update-17-0-balance.txt`, adjust the rules and re-run.

## Counts (2026-10-23 transcription)

| bucket | count |
| --- | --- |
| `entries` (one per record x field) | 139 |
| of which `confidence: "derived"` | 10 |
| distinct records touched | 103 |
| `textChanges` (behaviour / ability / fix text) | 67 |
| `unmatched` | 29 (21 are The Crucible mode content) |
| `mismatch: true` | 3 |

Sections covered: General Changes & Bugfixes; Balance and Gameplay Changes
(All Civilizations); Abbasid Dynasty; Byzantines; Chinese; English; Golden
Horde; Holy Roman Empire; Japanese; Jin Dynasty; Knights Templar; Macedonians;
Malians; Mongols; Order of the Dragon; Ottomans; Rus; Sengoku Daimyo; Tughlaq
Dynasty; Zhu Xi's Legacy; The Crucible (routed to `unmatched`). The notes have
no sections for English variants (Lancaster), French, Jeanne d'Arc, Delhi,
Ayyubids, Malians beyond one line, or Templar beyond what is listed - those civs
only receive the all-civilization Town Center and Ram changes.

## Field paths

- `cost.food|wood|gold|stone|merc_byz`, `hp`, `armor.Melee|Ranged|Fire`,
  `trainTimeSeconds`, `buildTimeSeconds`, `researchTimeSeconds`.
- `weapon.<weapon id>.damageMin`, `weapon.<weapon id>.damageMax`,
  `weapon.<weapon id>.range.max` - the weapon is addressed by its catalog
  `weapon[].id`, not by index, because the same weapon id can sit at different
  indexes across records.
- `weapon.<weapon id>.bonuses.<unit_type>.base_damage_modifier` - the bonus
  entry whose `unit_type` matches (`cavalry`, `melee_infantry`, `building`).

Extra fields a consumer may see on an entry: `scope`
(`all-civilizations` | `family`), `notedBefore`, `mismatch`, `derivation`,
and for the Sipahi range `notedBeforeTiles` / `notedNextTiles` / `unit`.
`matches` keeps the requested enum: `exact`, `applies-to-all-tiers` (used for
every family/variant expansion, including the all-civilization Town Center and
Ram rows and spawned variants such as `_grassland` Iron Pagodas or the Oda
`_codex_` Early Ozutsu), `name-only`.

## Caveats

- **Derived values (10).** Marked `confidence: "derived"` with a `derivation`
  string; the UI should show them differently from official numbers.
  - Town Center build time for Chinese (75 s) and Order of the Dragon (120 s):
    the catalog bakes the civilization multiplier into the definition, the
    notes quote the generic 150 -> 165. Overlay scales proportionally
    (82.5 / 132) and flags `mismatch: true`. These are the only three mismatches.
  - Sipahi range: the notes say 0.75 -> 0.6 **tiles**; the catalog stores
    engine units (3). Overlay uses 4 engine units per tile (3 / 0.75) -> 2.4.
    The catalog's INSTALLED_DATA.md explicitly does not vouch for a tile
    conversion, so treat this as an inference. The Byzantine mercenary Sipahi
    rows reference the same Ottoman weapon ids and are included as
    `matches: "name-only"`.
  - Palatine School Cataphract batch cost 750 -> 780 Silver: the catalog stores
    the per-unit cost (250 = 750 / 3), so the overlay writes 260.
- **Not applied, by design.** Capital Town Centers keep 150 s (pre-placed, not
  constructed). The Mongol packed Town Center keeps its 30 s unpack time. The
  Sipahi charge weapon (`weapon_horseman_*_charge_ott`) is not mentioned in the
  notes and is left at range 3. Landsknecht Mercenaries (40 Food) and Byzantine
  mercenary Landsknechts (Silver) do not carry the 60 Food price and are
  unchanged.
- **Percent / runtime modifiers** (Ottoman building discount, Golden Horde
  Khan/Torguud discount and +HP, Prelate inspiration, Cistern aura, gather-rate
  bonuses, spawn timers, healing rates) live in `textChanges`, with the
  affected record id where one exists, because the catalog fields are base
  values and the modifier is applied at runtime.
- **Mongol landmark movement speed** 0.75 -> 0.9 is `unmatched`: building
  records carry no speed field.
- **The Crucible** balance/rarity/bugfix lines are `unmatched` with a mode
  reason so the UI can hide them; they are not catalog stats.
- Everything else in `textChanges` with `recordId: null` (dock relic fix,
  Landscape Preservation, Castle of the Crow text, rocket emplacements, Jin
  Mounted Villager) names a thing that is not a catalog unit/building/tech
  record or whose id could not be identified without guessing.
- `newContent`: Vikings and Scots ship with 17.0 but the notes give no numbers;
  see `data/upcoming-civs/`.
- Status is `announced-not-released`. After the game updates, re-extract the
  catalog (see `data/INSTALLED_DATA.md`) and compare every `next` here against
  the new installed values before retiring this overlay.
