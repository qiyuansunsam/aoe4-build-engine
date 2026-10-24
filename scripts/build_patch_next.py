"""Build data/patch-next.json: the Age of Empires IV Update 17.0 preview notes
transcribed as an overlay on data/game-catalog.json.

Usage:
    python -X utf8 scripts/build_patch_next.py

Inputs
    data/game-catalog.json                      installed-build catalog (read only)
    data/patch-next/raw/update-17-0-balance.txt verbatim balance sections of the notes
Output
    data/patch-next.json

Every rule below is hand-transcribed from the raw notes. `current` is always
read from the catalog at run time; `next` is the value stated in the notes, or a
value derived from it (then confidence == "derived" and `derivation` says how).
A stated before-value that disagrees with the catalog sets mismatch: true and
keeps both numbers. Notes that cannot be mapped to a record field go to
`textChanges` (behaviour/ability text) or `unmatched` (with the reason).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "game-catalog.json"
RAW = ROOT / "data" / "patch-next" / "raw" / "update-17-0-balance.txt"
OUT = ROOT / "data" / "patch-next.json"

SOURCE_URL = "https://www.ageofempires.com/news/age-of-empires-iv-update-17-0/"
META = {
    "schemaVersion": 1,
    "version": "17.0",
    "status": "announced-not-released",
    "sourceUrl": SOURCE_URL,
    "publishedAt": "2026-10-22",
    "scheduledRelease": "2026-10-29",
    "transcribedAt": "2026-10-23",
}

# --------------------------------------------------------------------------
# catalog access
# --------------------------------------------------------------------------
cat = json.loads(CATALOG.read_text(encoding="utf-8"))
KIND = {"units": "unit", "buildings": "building", "technologies": "technology"}
INDEX: dict[str, tuple[str, dict]] = {}
for key, kind in KIND.items():
    for rec in cat[key]:
        INDEX[rec["id"]] = (kind, rec)

raw_text = RAW.read_text(encoding="utf-8")


def rec(rid: str) -> tuple[str, dict]:
    if rid not in INDEX:
        raise KeyError(f"catalog has no record {rid}")
    return INDEX[rid]


def find(kind: str | None = None, name: str | None = None, civ=None, idre: str | None = None, where=None):
    """Return record ids matching a name regex / civ list / id regex / predicate."""
    out = []
    civs = {civ} if isinstance(civ, str) else (set(civ) if civ else None)
    for key, k in KIND.items():
        if kind and k != kind:
            continue
        for r in cat[key]:
            if civs and r.get("civilization") not in civs:
                continue
            if name and not re.fullmatch(name, (r.get("name") or "").strip()):
                continue
            if idre and not re.search(idre, r["id"]):
                continue
            if where and not where(r):
                continue
            out.append(r["id"])
    return out


def get_field(r: dict, field: str):
    """Resolve a dotted overlay field path on a catalog record.

    weapon.<weapon id>.damageMin / damageMax / range.max
    weapon.<weapon id>.bonuses.<unit_type>.base_damage_modifier
    """
    parts = field.split(".")
    if parts[0] == "weapon":
        wid = parts[1]
        ws = [w for w in (r.get("weapon") or []) if w.get("id") == wid]
        if not ws:
            raise KeyError(f"{r['id']} has no weapon {wid}")
        cur = ws[0]
        rest = parts[2:]
        if rest and rest[0] == "bonuses":
            bs = [b for b in cur.get("bonuses", []) if b.get("unit_type") == rest[1]]
            if not bs:
                raise KeyError(f"{r['id']} weapon {wid} has no bonus vs {rest[1]}")
            cur = bs[0]
            rest = rest[2:]
        for p in rest:
            cur = cur[p]
        return cur
    cur = r
    for p in parts:
        cur = cur[p]
    return cur


def assert_in_notes(text: str) -> None:
    """Every noteText must be a verbatim sentence from the raw notes."""
    if text not in raw_text:
        raise ValueError(f"noteText not found verbatim in raw notes: {text!r}")


# --------------------------------------------------------------------------
# collectors
# --------------------------------------------------------------------------
entries: list[dict] = []
text_changes: list[dict] = []
unmatched: list[dict] = []
seen: set[tuple[str, str]] = set()


def entry(rid: str, field: str, nxt, note: str, section: str, matches: str = "exact",
          noted_before=None, confidence: str = "official", derivation: str | None = None,
          scope: str | None = None, extra: dict | None = None):
    assert_in_notes(note)
    kind, r = rec(rid)
    key = (rid, field)
    if key in seen:
        raise ValueError(f"duplicate entry for {key}")
    seen.add(key)
    current = get_field(r, field)
    e = {
        "recordId": rid,
        "pbgid": (r.get("source") or {}).get("pbgid"),
        "name": (r.get("name") or "").strip(),
        "civilization": r.get("civilization"),
        "kind": kind,
        "field": field,
        "current": current,
        "next": nxt,
        "noteText": note,
        "section": section,
        "confidence": confidence,
        "matches": matches,
    }
    if scope:
        e["scope"] = scope
    if noted_before is not None:
        e["notedBefore"] = noted_before
        if current != noted_before:
            e["mismatch"] = True
    if derivation:
        e["derivation"] = derivation
    if extra:
        e.update(extra)
    entries.append(e)


def text(rid: str | None, name: str, civ: str | None, section: str, note: str, related: list[str] | None = None):
    assert_in_notes(note)
    t = {"recordId": rid, "name": name, "civilization": civ, "section": section, "noteText": note}
    if rid:
        kind, r = rec(rid)
        t["kind"] = kind
        t["pbgid"] = (r.get("source") or {}).get("pbgid")
    if related:
        for x in related:
            rec(x)
        t["relatedRecordIds"] = related
    text_changes.append(t)


def unmatch(note: str, section: str, reason: str):
    assert_in_notes(note)
    unmatched.append({"noteText": note, "section": section, "reason": reason})


# ==========================================================================
# Balance and Gameplay Changes (All Civilizations)
# ==========================================================================
SEC = "Balance and Gameplay Changes (All Civilizations)"

N_TC = "Town Center construction time increased from 150 → 165 seconds."
for rid in find("building", name="Town Center", idre=r"^building_town_center_(?!capital)"):
    _, r = rec(rid)
    t = r["buildTimeSeconds"]
    if t == 150:
        entry(rid, "buildTimeSeconds", 165, N_TC, SEC, matches="applies-to-all-tiers",
              noted_before=150, scope="all-civilizations")
    elif t == 30:
        # Mongol packed Town Center: 30 s is the unpack time, not a construction time.
        continue
    else:
        # Civilization-specific build time baked into the definition (Chinese 75, Order of the Dragon 120).
        entry(rid, "buildTimeSeconds", round(t * 165 / 150, 1), N_TC, SEC, matches="applies-to-all-tiers",
              noted_before=150, confidence="derived", scope="all-civilizations",
              derivation=f"catalog stores a civilization-adjusted time of {t} s (not the 150 s the notes quote); "
                         f"next = {t} x 165/150, assuming the civilization multiplier is kept")
unmatch(N_TC, SEC, "Capital Town Centers (building_town_center_capital_*) share the 150 s field but are pre-placed, "
                   "not constructed; left unchanged. Mongol packed Town Center (building_town_center_moving_mon) uses 30 s unpack time.")

N_RAM = "Ram health increased from 370 → 410."
for rid in find("unit", name=r"(Clocktower )?Battering Ram"):
    _, r = rec(rid)
    if r["hp"] == 370:
        entry(rid, "hp", 410, N_RAM, SEC, matches="applies-to-all-tiers", noted_before=370, scope="all-civilizations")
    else:
        unmatch(N_RAM, SEC, f"{rid} is named Battering Ram but has hp {r['hp']}, not 370")

for n in (
    "Villagers returning to work from the Town Center now accept shift-click queued commands.",
    "Relics will no longer be destroyed if deposited into a building just as it is destroyed.",
    "Fixed an issue where switching to attacking a unit just after throwing a torch will cause a torch to be thrown at the enemy unit.",
    "Fixed an issue where Scouts attempting to drop a carcass can sometimes fail.",
):
    text(None, "General", None, "General Changes & Bugfixes", n)

# ==========================================================================
# Abbasid Dynasty
# ==========================================================================
SEC = "Abbasid Dynasty"
text("upgrade_trade_commodity_trade_abb", "Grand Bazaar", "abbasid", SEC,
     "Fixed a bug which caused the Trade Ships’ extra resources from Grand Bazaar to be calculated incorrectly.")
text("upgrade_admin_city_planning_abb", "City Planning", "abbasid", SEC,
     "The City Planning health bonus is now applied to Lumber Camps and Mining Camps within influence.")

# ==========================================================================
# Byzantines
# ==========================================================================
SEC = "Byzantines"
text("building_cistern_byz", "Cistern", "byzantine", SEC,
     "Cistern gather rate aura reduced from 26% → 24% at water level 5.")
N = "Teardrop Shields cost increased from 100 Food 250 Gold → 150 Food 350 Gold."
entry("upgrade_teardrop_shields_byz", "cost.food", 150, N, SEC, noted_before=100)
entry("upgrade_teardrop_shields_byz", "cost.gold", 350, N, SEC, noted_before=250)
text("building_landmark_age2_galata_tower_byz", "Golden Horn Tower", "byzantine", SEC,
     "Golden Horn Tower production speed reduced by 10%.")
text("building_landmark_age2_cistern_byz", "Cistern of the First Hill", "byzantine", SEC,
     "Cistern of the First Hill cooldown per unit reduced from 45 seconds → 30 seconds.")
N = "Cheirosiphon health increased from 310 → 330."
for rid in find("unit", name="Cheirosiphon", civ="byzantine"):
    entry(rid, "hp", 330, N, SEC, noted_before=310)
text("unit_naval_combat_ship_2_byz", "Dromon", "byzantine", SEC,
     "Byzantine and Macedonian Dromons are now correctly labelled as “Massive Ship” instead of “Springald Ship”.",
     related=["unit_naval_combat_ship_2_byz_ha_mac"])
text("unit_royal_knight_2_merc_byz", "Royal Knight (mercenary)", "byzantine", SEC,
     "Mercenary Royal Knights no longer lose their Royal Bloodlines after researching Biology.",
     related=["unit_royal_knight_3_merc_byz", "unit_royal_knight_4_merc_byz", "upgrade_cavalry_bloodline_byz"])
text("unit_manatarms_4_byz", "Elite Varangian Guard", "byzantine", SEC,
     "Fixed an issue causing the Byzantine Elite Varangian Guard to fail to switch to the axe when the Berserking ability is used.")

# ==========================================================================
# Chinese / English
# ==========================================================================
text("unit_official_1_chi", "Imperial Official", "chinese", "Chinese",
     "Imperial Officials can no longer supervise points of interest.")
text("building_landmark_age3_whitehall_palace_eng", "Wynguard Palace", "english", "English",
     "Wynguard Armies no longer display incorrect populations in the score screen.")

# ==========================================================================
# Golden Horde (mongol_ha_gol)
# ==========================================================================
SEC = "Golden Horde"
text("upgrade_tent_dark_1_khan_mon_ha_gol", "Khan and Torguuds", "mongol_ha_gol", SEC,
     "Discount on Khan and Torguuds reduced from 20% → 15%.",
     related=["unit_bodyguard_2_mon_ha_gol", "unit_bodyguard_3_mon_ha_gol", "unit_bodyguard_4_mon_ha_gol", "unit_khan_2_mon_ha_gol"])
text("upgrade_tent_dark_1_khan_mon_ha_gol", "Khan and Torguuds", "mongol_ha_gol", SEC,
     "Khan and Torguud increased health reduced from +30 → +25.",
     related=["unit_bodyguard_2_mon_ha_gol", "unit_bodyguard_3_mon_ha_gol", "unit_bodyguard_4_mon_ha_gol", "unit_khan_2_mon_ha_gol"])
unmatch("Discount on Khan and Torguuds reduced from 20% → 15%.", SEC,
        "The discount is a tent-choice modifier; Torguud/Batu Khan catalog costs are base values, so no cost field changes.")
unmatch("Khan and Torguud increased health reduced from +30 → +25.", SEC,
        "The +30 is a tent-choice modifier applied at runtime; catalog hp fields are base values.")
text("upgrade_tent_feudal_1_pasture_mon_ha_gol", "Muscovy Yasak", "mongol_ha_gol", SEC,
     "Muscovy Yasak wood reduction per Heavy Infantry or Heavy Cavalry on the field increased from 2 → 3.")
text("upgrade_military_production_speed_mon_ha_gol", "Increased Supplies", "mongol_ha_gol", SEC,
     "Fixed an issue causing the Increased Supplies technology to not apply correctly to Military Buildings constructed from Building Carts.")
text("upgrade_tent_dark_2_cart_mon_ha_gol", "Building Carts", "mongol_ha_gol", SEC,
     "Fixed an issue where cancelling a Building Cart when unpacking could cause the building to become invisible.")

# ==========================================================================
# Holy Roman Empire
# ==========================================================================
SEC = "Holy Roman Empire"
text("unit_monk_1_hre", "Prelate", "hre", SEC, "Prelate Inspiration gather rate increased from 35% → 40%.")
text("upgrade_inspired_infantry_hre", "Inspired Warriors", "hre", SEC,
     "Inspired Warriors effect duration increased from 60 → 90 seconds.")
text("unit_black_rider_hre", "Black Rider", "hre", SEC, "Build limit increased from 5 → 6 per active Keep.")
entry("unit_black_rider_hre", "trainTimeSeconds", 30, "Production time reduced from 35 → 30 seconds.", SEC, noted_before=35)
N = "Landsknecht cost reduced from 60 Food 100 Gold → 50 Food 100 Gold."
entry("unit_landsknecht_3_hre", "cost.food", 50, N, SEC, noted_before=60)
entry("unit_landsknecht_4_hre", "cost.food", 50, N, SEC, matches="applies-to-all-tiers", noted_before=60)
unmatch(N, SEC, "unit_landsknecht_mercenaries_hre (Landsknecht Mercenaries, 40 Food 120 Gold) and the Byzantine mercenary "
                "Landsknecht (Silver/Olive Oil cost) do not have the quoted 60 Food price; left unchanged.")
text(None, "Dock", "hre", SEC, "Relics that are deposited in Docks will no longer be lost if the Dock is destroyed.")

# ==========================================================================
# Japanese
# ==========================================================================
SEC = "Japanese"
text("upgrade_shinobi_sabotage_jpn", "Sabotage", "japanese", SEC,
     "Shinobi units can no longer sabotage Golden Tents or Templar capital Town Centers.",
     related=["unit_shinobi_2_jpn", "building_landmark_golden_tent_mon_ha_gol", "building_town_center_capital_tem"])
text(None, "Rocket emplacement", "japanese", SEC,
     "Fixed an issue which prevented Japanese rocket emplacements from dealing bonus damage to elephants.")

# ==========================================================================
# Jin Dynasty
# ==========================================================================
SEC = "Jin Dynasty"
IP = {
    2: ("Base damage increased from 16 → 17. Base health increased from 200 → 210.", 16, 17, 200, 210),
    3: ("Veteran damage increased from 20 → 21. Health increased from 250 → 255.", 20, 21, 250, 255),
    4: ("Elite damage increased from 23 → 24. Health increased from 290 → 295.", 23, 24, 290, 295),
}
for tier, (note, d0, d1, h0, h1) in IP.items():
    for rid in (f"unit_iron_pagoda_{tier}_jin", f"unit_iron_pagoda_{tier}_jin_grassland"):
        wid = f"weapon_iron_pagoda_{tier}_jin"
        m = "exact" if rid.endswith("_jin") else "applies-to-all-tiers"
        entry(rid, f"weapon.{wid}.damageMin", d1, note, SEC, matches=m, noted_before=d0)
        entry(rid, f"weapon.{wid}.damageMax", d1, note, SEC, matches=m, noted_before=d0)
        entry(rid, "hp", h1, note, SEC, matches=m, noted_before=h0)
IP_RELATED = [f"unit_iron_pagoda_{t}_jin{s}" for t in (2, 3, 4) for s in ("", "_grassland")]
text("unit_iron_pagoda_2_jin", "Iron Pagoda", "jin_dynasty", SEC,
     "Far-range area damage increased from 15% → 20%.", related=IP_RELATED)
text("unit_iron_pagoda_2_jin", "Iron Pagoda", "jin_dynasty", SEC,
     "Damage impact time improved from 0.75 → 0.5 seconds.", related=IP_RELATED)

BC = "unit_bedcrossbow_{}_jin"
BW = "weapon.weapon_bedcrossbow_{}_jin.{}"
# Feudal Age (tier 2)
entry(BC.format(2), BW.format(2, "damageMin"), 10, "Damage increased from 8 → 10 .", SEC, noted_before=8)
entry(BC.format(2), BW.format(2, "damageMax"), 10, "Damage increased from 8 → 10 .", SEC, noted_before=8)
entry(BC.format(2), BW.format(2, "bonuses.melee_infantry.base_damage_modifier"), 6,
      "Bonus damage vs melee infantry increased from 4 → 6.", SEC, noted_before=4)
entry(BC.format(2), "hp", 90, "Health increased from 85 → 90.", SEC, noted_before=85)
# Veteran (tier 3)
entry(BC.format(3), BW.format(3, "damageMin"), 11, "Damage increased from 10 → 11.", SEC, noted_before=10)
entry(BC.format(3), BW.format(3, "damageMax"), 11, "Damage increased from 10 → 11.", SEC, noted_before=10)
entry(BC.format(3), BW.format(3, "bonuses.melee_infantry.base_damage_modifier"), 6,
      "Bonus damage vs melee infantry increased from 4 → 6.", SEC, noted_before=4)
entry(BC.format(3), "armor.Melee", 1, "Melee armor increased from 0 → 1.", SEC, noted_before=0)
# Elite (tier 4)
entry(BC.format(4), BW.format(4, "damageMin"), 14, "Damage increased from 13 → 14.", SEC, noted_before=13)
entry(BC.format(4), BW.format(4, "damageMax"), 14, "Damage increased from 13 → 14.", SEC, noted_before=13)
entry(BC.format(4), BW.format(4, "bonuses.melee_infantry.base_damage_modifier"), 7,
      "Bonus damage vs melee infantry increased from 5 → 7.", SEC, noted_before=5)
entry(BC.format(4), "hp", 115, "Health increased from 110 → 115.", SEC, noted_before=110)
entry(BC.format(4), "armor.Melee", 2, "Melee armor increased from 0 → 2.", SEC, noted_before=0)

text(None, "Jin Dynasty", "jin_dynasty", SEC, "Updated the Selection Card Art background for the Jin Dynasty.")
text("unit_mengan_mouke_2_jin", "Meng'an Mouke Defender", "jin_dynasty", SEC,
     "Meng’an Mouke Defenders will now properly spawn from coastal Tributary States.",
     related=["upgrade_tributary_menganmouke_jin"])
text(None, "Mounted Villager", "jin_dynasty", SEC,
     "Specialized Pick and Shaft Mining now properly increase the Mounted Villager’s Gold gather rate.")

# ==========================================================================
# Knights Templar
# ==========================================================================
SEC = "Knights Templar"
N = "Fortress cost increased from 300 Gold 600 Stone → 350 Gold 650 Stone."
entry("building_defense_fortress_tem", "cost.gold", 350, N, SEC, noted_before=300)
entry("building_defense_fortress_tem", "cost.stone", 650, N, SEC, noted_before=600)
text("upgrade_age_dark_com_1_tem", "Knights Hospitaller (age up)", "templar", SEC,
     "Bonus worker movement speed reduced from 10% → 8%.")
text("upgrade_age_dark_com_1_tem", "Knights Hospitaller (age up)", "templar", SEC,
     "Bonus worker health reduced from 30% → 25%.")
text(None, "Landscape Preservation", "templar", SEC,
     "Castle Age bonus Wood gather rate reduced from +20% → +15%.")
text(None, "Landscape Preservation", "templar", SEC,
     "Imperial Age bonus Wood gather rate reduced from +20% → +15%.")
text("unit_condottiero_4_tem", "Condottiero", "templar", SEC,
     "Fixed a bug which prevented the Condottiero from taking damage as a heavy unit.")

# ==========================================================================
# Macedonians (byzantine_ha_mac)
# ==========================================================================
SEC = "Macedonians"
MAC = "byzantine_ha_mac"
text("building_landmark_age1_winery_byz_ha_mac", "Grand Winery", MAC, SEC,
     "Improved Food gather rate increased from 30% → 35%.")
text("building_landmark_age1_winery_byz_ha_mac", "Grand Winery", MAC, SEC,
     "Silver generation per garrisoned Relic increased from 80 → 100.")
text("building_landmark_age1_hippodrome_byz_ha_mac", "Imperial Hippodrome", MAC, SEC,
     "Champion Horseman spawn time increased from 120 → 130 seconds.", related=["unit_champion_horseman_byz_ha_mac"])
text("building_landmark_age1_hippodrome_byz_ha_mac", "Imperial Hippodrome", MAC, SEC,
     "Champion Riddari spawn time increased from 195 → 205 seconds.", related=["unit_champion_knight_byz_ha_mac"])
text("building_landmark_age2_galata_tower_byz_ha_mac", "Golden Horn Tower", MAC, SEC,
     "Golden Horn Tower crossbowman production time increased from 112 → 135 seconds.")
for n in (
    "Mills now generate Food when affected by Cistern’s Favor.",
    "Cistern’s Favor accrual time improved from 90 → 60 seconds.",
    "Increased maximum number of Cistern’s Favor charges from 9 → 99.",
):
    text("building_landmark_age2_cistern_byz_ha_mac", "Cistern of the First Hill", MAC, SEC, n)
N = "Cheirosiphon health increased from 310 → 330."
for rid in find("unit", name="Cheirosiphon", civ=MAC):
    entry(rid, "hp", 330, N, SEC, noted_before=310)
entry("unit_manatarms_2_byz_ha_mac", "hp", 115, "Early Varangian Guard health reduced from 120 → 115.", SEC, noted_before=120)
text("building_landmark_age3_western_merc_house_byz_ha_mac", "Palatine School", MAC, SEC,
     "Cataphract batch production time increased from 20 → 25 seconds.", related=["unit_cataphract_4_byz_mac_ha"])
unmatch("Cataphract batch production time increased from 20 → 25 seconds.", SEC,
        "unit_cataphract_4_byz_mac_ha has trainTimeSeconds 40, not the 20 s batch time quoted; the batch timer is a landmark "
        "action, not the unit field. Left unchanged.")
entry("unit_cataphract_4_byz_mac_ha", "cost.merc_byz", 260, "Cataphract batch cost increased from 750 Silver → 780.", SEC,
      matches="name-only", confidence="derived",
      derivation="catalog stores the per-unit Silver cost (250 = 750 / 3 per batch); next = 780 / 3 = 260")
text(None, "Cistern’s Favor hotkey", MAC, SEC, "Added a remappable hotkey for the Cistern’s Favor hotkey.")
text("upgrade_flaming_springald_byz_ha_mac", "Roman Fire", MAC, SEC,
     "Roman Fire upgrade no longer gives Macedonian Springalds an additional 0.5 range.")
text(None, "Cistern’s Favor", MAC, SEC, "Cistern’s Favor resource production now appears in player resources increment.")
text("building_landmark_age1_hippodrome_byz_ha_mac", "Imperial Hippodrome", MAC, SEC,
     "Fixed an exploit which allowed players to train an infinite number of Hippodrome Champions when playing with keyboard and mouse on console.")
text("building_varangian_runestone_byz_ha_mac", "Runestones", MAC, SEC,
     "Runestones no longer overwrite Line Formation when playing on console using keyboard and mouse.")
text("unit_champion_knight_byz_ha_mac", "Hippodrome Riddari", MAC, SEC,
     "Fixed an issue which prevented the Champion Riddari from using Runestones.",
     related=["building_varangian_runestone_byz_ha_mac"])

# ==========================================================================
# Malians / Mongols
# ==========================================================================
text("building_landmark_age2_landmarkc_control_mal", "Grand Fulani Corral", "malian", "Malians",
     "Fulani Corral Food generation per Cattle reduced from 18 Food → 16 Food.")
N = "Landmark movement speed increased from 0.75 → 0.9."
unmatch(N, "Mongols", "Mongol landmark records (building_wonder_*_moving_mon) carry no speedEngineUnits field in the catalog; "
                      "packed-landmark movement is a runtime state, so there is no field to overlay.")

# ==========================================================================
# Order of the Dragon (hre_ha_01)
# ==========================================================================
SEC = "Order of the Dragon"
N = "Gilded Landsknecht cost reduced from 120 Food 200 Gold → 100 Food 200 Gold."
entry("unit_landsknecht_3_hre_ha_01", "cost.food", 100, N, SEC, noted_before=120)
entry("unit_landsknecht_4_hre_ha_01", "cost.food", 100, N, SEC, matches="applies-to-all-tiers", noted_before=120)
text("unit_crossbowman_3_hre_ha_01", "Gilded Crossbowman", "hre_ha_01", SEC,
     "Fixed an issue where the Gilded Crossbowman would have slower attack speed against buildings than its default attack after researching Incendiary Arrows.",
     related=["unit_crossbowman_4_hre_ha_01"])
text("building_tech_university_control_hre_ha_01", "University", "hre_ha_01", SEC,
     "Fixed an issue which caused Order of the Dragon universities to grant population space.")

# ==========================================================================
# Ottomans
# ==========================================================================
SEC = "Ottomans"
text(None, "Ottoman buildings", "ottoman", SEC, "Building discount reduced from 40% → 30%.")
unmatch("Building discount reduced from 40% → 30%.", SEC,
        "Civilization-wide discount applied at runtime; catalog building costs are base values, so no per-record field changes.")
entry("unit_handcannon_3_ott", "weapon.weapon_handcannon_3_ott.bonuses.cavalry.base_damage_modifier", 10,
      "Bonus damage vs Cavalry reduced from 11 → 10.", SEC, noted_before=11)
entry("unit_handcannon_4_ott", "weapon.weapon_handcannon_4_ott.bonuses.cavalry.base_damage_modifier", 12,
      "Elite bonus damage vs Cavalry reduced from 13 → 12.", SEC, noted_before=13)
N = "Sipahi attack range reduced from 0.75 → 0.6 tiles."
SIPAHI_DERIV = ("notes quote tiles; catalog range.max is in engine units (3 for the Sipahi spear). 3 engine units = 0.75 tiles "
                "gives 4 engine units per tile, so next = 0.6 x 4 = 2.4 engine units")
for tier in (2, 3, 4):
    wid = f"weapon_horseman_{tier}_ott"
    for rid in (f"unit_horseman_{tier}_ott", f"unit_sipahi_{tier}_byz"):
        _, r = rec(rid)
        m = "exact" if r["civilization"] == "ottoman" else "name-only"
        entry(rid, f"weapon.{wid}.range.max", 2.4, N, SEC, matches=m, confidence="derived",
              derivation=SIPAHI_DERIV + ("" if m == "exact" else "; Byzantine mercenary Sipahi references the same Ottoman weapon definition"),
              scope="family", extra={"notedBeforeTiles": 0.75, "notedNextTiles": 0.6, "unit": "engineUnits"})
unmatch(N, SEC, "weapon_horseman_{2,3,4}_charge_ott (the Sipahi charge attack, also range 3) is not mentioned; left unchanged.")
text("building_landmark_age1_han_caravanserai_ott", "Sultanhani Trade Network", "ottoman", SEC,
     "Sultanhani Trade Network Gold generation increased from 26 → 28 per garrisoned Trader.")
for n in (
    "Dark Age healing rate reduced from 1 to 0.5 health per second.",
    "Feudal Age healing rate reduced from 1 to 0.8 health per second.",
    "Castle Age & Imperial Age are unchanged at 2 and 3 health per second respectively.",
):
    text("upgrade_imperial_monk_formation_ott", "Field Work", "ottoman", SEC, n)

# ==========================================================================
# Rus
# ==========================================================================
text("unit_spearman_3_rus", "Veteran Spearman", "rus", "Rus",
     "Rus Veteran and Elite Spearman now use a different weapon so that it is easier to distinguish them as Spearman.",
     related=["unit_spearman_4_rus"])

# ==========================================================================
# Sengoku Daimyo (japanese_ha_sen)
# ==========================================================================
SEC = "Sengoku Daimyo"
SEN = "japanese_ha_sen"
text("unit_yatai_1_jpn_ha_sen", "Yatai", SEN, SEC,
     "Yatai Food Trader spawn requirement reduced from 250 Food → 215 Food.",
     related=["unit_yatai_food_cart_jpn_ha_sen", "unit_yatai_food_ship_jpn_ha_sen"])
for rid in ("unit_ozutsu_3_jpn_ha_sen", "unit_ozutsu_codex_3_jpn_ha_sen"):
    m = "exact" if rid == "unit_ozutsu_3_jpn_ha_sen" else "applies-to-all-tiers"
    entry(rid, "hp", 140, "Health increased from 130 → 140.", SEC, matches=m, noted_before=130)
    for wid in ("weapon_ozutsu_3_jpn_ha_sen", "weapon_ozutsu_large_aoe_3_jpn_ha_sen"):
        entry(rid, f"weapon.{wid}.damageMin", 24, "Damage increased from 22 → 24.", SEC, matches=m, noted_before=22)
        entry(rid, f"weapon.{wid}.damageMax", 24, "Damage increased from 22 → 24.", SEC, matches=m, noted_before=22)
        entry(rid, f"weapon.{wid}.bonuses.building.base_damage_modifier", 80,
              "Bonus damage vs buildings increased from 70 → 80.", SEC, matches=m, noted_before=70)
text(None, "Castle of the Crow", SEN, SEC,
     "Updated the text on the Sengoku Castle of the Crow landmark to mention it only applies to ranged siege units.")
text(None, "Rocket emplacement", SEN, SEC,
     "Fixed an issue which prevented Sengoku Daimyo rocket emplacements from dealing bonus damage to elephants.")

# ==========================================================================
# Tughlaq Dynasty / Zhu Xi's Legacy
# ==========================================================================
text("unit_war_elephant_raider_2_sul_ha_tug", "Raider Elephant", "sultanate_ha_tug", "Tughlaq Dynasty",
     "Raider Elephants are significantly less trumpety when moving around.",
     related=["unit_war_elephant_raider_3_sul_ha_tug", "unit_war_elephant_raider_4_sul_ha_tug"])
SEC = "Zhu Xi's Legacy"
text("building_landmark_age1_prefecture_chi_ha_01", "Jiangnan Tower", "chinese_ha_01", SEC,
     "Resources-spent requirement for the first army spawn increased from 2200 → 2400 resources.")
text("building_landmark_age1_prefecture_chi_ha_01", "Jiangnan Tower", "chinese_ha_01", SEC,
     "Resources-spent cap increased from 8200 → 8400 resources.")
text("upgrade_library_improved_officials", "Advanced Administration", "chinese_ha_01", SEC,
     "The Advanced Administration upgrade now properly increases the Imperial Official build limit.",
     related=["unit_official_1_chi_ha_01"])
text("unit_official_1_chi_ha_01", "Imperial Official", "chinese_ha_01", SEC,
     "Imperial Officials can no longer supervise points of interest.")

# ==========================================================================
# The Crucible (game mode; not catalog stats)
# ==========================================================================
CRUCIBLE_REASON = "The Crucible game-mode content (boons, perks, mutators, boss scaling); not a catalog unit/building/technology stat."
for n in (
    "Boss unit health now scales more rapidly with each difficulty level.",
    "Boss units now gain additional health scaling in Castle and Imperial Age.",
    "Boss unit damage now also scales in Castle and Imperial Age.",
    "Boss unit size increased.",
    "Boggy Ground now only applies its debuff to enemy units. Armor corrosion of -1 armor added.",
    "Burgage Lords House cost increase reduced from 25 → 15 Wood.",
    "Lighter Cavalry attack damage increased from +2 → +4.",
    "Cavalry Hero aura health buff reduced from 40% → 35%.",
    "Quality over Quantity bonus increased from 150% → 200% Also now applies to bonus damage.",
    "Supremacy immediately grants Elite Man-at-arms on selection.",
    "Training Dummies now explode on death, dealing damage.",
    "Fast Expand bonus reduced from 75% cheaper Town Centers → 60% cheaper.",
    "Handy Cannons now deal significantly more pierce damage and hit more targets.",
    "Thorny Economics health bonus increased from +100% → +150%.",
    "Giant Nest of Bees Reload time increased from 4 to 8 seconds.",
    "In Crucible, the Golden Horde’s Building Carts can no longer unpack into docks on maps where naval is disabled.",
    "In Crucible, Smite now strikes units fully randomly within the casting area.",
    "In Crucible, the Forward Outposts 4 Perk no longer provide Cannons to Templar Outposts, Springalds are granted instead.",
    "Capturable Champions now properly benefit from Infinitry and Last Stand Boons.",
    "Fixed an issue where some heavy cavalry units did not benefit from the Vulnerability boon.",
):
    unmatch(n, "The Crucible", CRUCIBLE_REASON)
unmatch("Panic Button: Epic → Standard", "The Crucible", CRUCIBLE_REASON + " (Boon rarity; also Supremacy Epic → Cursed, "
        "Growth Fund Standard → Epic, Permanent Garrison Standard → Epic.)")

# ==========================================================================
# write
# ==========================================================================
mismatches = [e for e in entries if e.get("mismatch")]
out = dict(META)
out["rawNotes"] = "data/patch-next/raw/update-17-0-balance.txt"
out["sectionsCovered"] = [
    "General Changes & Bugfixes", "Balance and Gameplay Changes (All Civilizations)",
    "Abbasid Dynasty", "Byzantines", "Chinese", "English", "Golden Horde", "Holy Roman Empire", "Japanese",
    "Jin Dynasty", "Knights Templar", "Macedonians", "Malians", "Mongols", "Order of the Dragon", "Ottomans",
    "Rus", "Sengoku Daimyo", "Tughlaq Dynasty", "Zhu Xi's Legacy", "The Crucible",
]
out["counts"] = {
    "entries": len(entries),
    "entriesDerived": sum(1 for e in entries if e["confidence"] == "derived"),
    "textChanges": len(text_changes),
    "unmatched": len(unmatched),
    "mismatches": len(mismatches),
    "recordsTouched": len({e["recordId"] for e in entries}),
}
out["entries"] = entries
out["textChanges"] = text_changes
out["unmatched"] = unmatched
out["newContent"] = {
    "civilizations": ["vikings", "scots"],
    "note": "Raiders of the North (Vikings, Scots) releases with 17.0 on 2026-10-29; the 17.0 notes give no unit/building/technology numbers for them. See data/upcoming-civs/.",
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out["counts"]))
for e in mismatches:
    print("MISMATCH", e["recordId"], e["field"], "current", e["current"], "notedBefore", e["notedBefore"])
