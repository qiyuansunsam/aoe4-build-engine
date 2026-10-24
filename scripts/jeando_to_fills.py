"""Convert the jeandogaming.com datamined records into checklist fills (data/upcoming-civs/fills/jeando-<civ>.json).

Input: data/upcoming-civs/raw/jeando/<civ>_dataset.json (scripts/extract_jeando_dataset.py).
Mapping: lowest tier of a unit family is the base reading (variant null); higher tiers and alternate copies
(mustered, toggle, free, landmark-spawned) are variants. Names are matched to checklist names after accent and
plural folding; anything else becomes a discovered item. Tier-upgrade techs are named after their unit
("Upgrade to Hardened Bondi"). Attack speed is calculated from the primary weapon's timings:
windup + cooldown + winddown + aim + reload + the firing phase, max(0.125 s tick, burst_duration). That reproduces every tooltip read
from footage (Bondi spear 1.88, Spearwall 1.12, torch 2.12, Berserker 1.25, Hirdman 1.38, Shield Maiden 2.12, Ghillie
sword 2.00, Jylland Knight 1.50, Drakkar 4.88 with its 0.25 s burst). Bonus damage is not in the records; it comes from footage.
Usage: python -X utf8 scripts/jeando_to_fills.py
"""
import json, pathlib, re, unicodedata
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'
SRC = 'jeando-datamined'
AGE = {'Dark Age': 'Dark', 'Feudal Age': 'Feudal', 'Castle Age': 'Castle', 'Imperial Age': 'Imperial'}
LANDMARK_AGE = {'Age II': 'Feudal', 'Age III': 'Castle', 'Age IV': 'Imperial'}
TIER_PREFIX = re.compile(r'^(Early|Hardened|Veteran|Elite)\s+')
ALT = re.compile(r'_(muster|toggle|highlanders|free|no_req|rikets|konungr)(?=_|$)')

def fold(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s); s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'(men|s)$', lambda m: 'man' if m.group(1) == 'men' else '', s)

def family(rid):
    """unit_spearman_2_vik -> unit_spearman_{}_vik ; ids without a tier digit are their own family."""
    return re.sub(r'_(\d)(?=_[a-z]+$)', '_{}', rid)

def tier(rid):
    m = re.search(r'_(\d)_[a-z]+$', rid)
    return int(m.group(1)) if m else 0

def main():
    import sys; sys.path.insert(0, str(ROOT / 'scripts'))
    from build_upcoming_checklist import build_items
    names = {}
    for it in build_items(fresh=True):  # text-source objects only; everything else is a discovered object
        names.setdefault((it['civ'], it['kind'], fold(it['name'])), it['name'])
        names.setdefault((it['civ'], '*', fold(re.sub(r'\s*\(.*\)', '', it['name']))), (it['kind'], it['name']))
    for civ in ('vikings', 'scots'):
        recs = json.loads((DIR / f'raw/jeando/{civ}_dataset.json').read_text(encoding='utf-8'))['records']
        recs = {k: v for k, v in recs.items() if v.get('civKey') == civ or k.endswith(('_vik', '_sco')) or f'__{civ}' in k}
        units = {k: v for k, v in recs.items() if k.startswith(('unit_', 'highland_cattle'))}
        base_name, base_id = {}, {}
        for fam in {family(k) for k in units if not ALT.search(k)}:
            members = sorted((k for k in units if family(k) == fam and not ALT.search(k)), key=tier)
            base_id[fam] = members[0]; base_name[fam] = TIER_PREFIX.sub('', units[members[0]]['name'])
        other = 'scots' if civ == 'vikings' else 'vikings'
        other_ids = json.loads((DIR / f'raw/jeando/{other}_dataset.json').read_text(encoding='utf-8'))['records']
        stems = {re.sub(r'_[a-z]+$', '', k) for k in other_ids}
        by_name = {}
        for fam, bid in base_id.items(): by_name.setdefault(base_name[fam], []).append(fam)
        alt_fams = set()
        for nm, fams in by_name.items():
            if len(fams) > 1:
                standard = [f for f in fams if re.sub(r'_[a-z]+$', '', base_id[f]) in stems] or sorted(fams, key=len)[:1]
                alt_fams |= set(fams) - set(standard[:1])
        fills = []
        def add(kind, name, field, value, rid, variant, quote):
            if value is None or value == '': return
            key = (civ, kind, fold(name)); hit = names.get(key)
            loose = names.get((civ, '*', fold(name)))
            compatible = {'unit': {'unit'}, 'building': {'building', 'landmark'}, 'landmark': {'landmark', 'building'}, 'technology': {'technology'}}
            if not hit and loose and loose[0] in compatible[kind]: kind, hit = loose
            seg = {'unit': 'units', 'building': 'buildings', 'landmark': 'buildings', 'technology': 'techs'}[kind]
            f = {'civ': civ, 'kind': kind, 'name': hit or name, 'field': field, 'value': value, 'variant': variant,
                 'videoId': SRC, 'sourceUrl': f'https://jeandogaming.com/en/aoe4/explorer/{civ}/{seg}/{rid}', 'timestamp': None,
                 'quote': quote, 'confidence': 'datamined', 'note': f'record {rid}'}
            if not hit: f['newItem'] = f'datamined record {rid}'
            fills.append(f)
        for rid, r in recs.items():
            costs = r.get('costs') or {}
            cost_fields = [(f'cost.{res}', costs.get(res, 0) if costs else None) for res in ('food', 'wood', 'gold', 'stone')]
            quote = json.dumps({k: r.get(k) for k in ('name', 'className', 'ageName', 'hitpoints', 'speed', 'armor', 'costs') if r.get(k) is not None}, ensure_ascii=False)
            if rid in units:
                fam = family(rid); alt = ALT.search(rid)
                if alt:  # alternate copy (mustered, toggled, landmark-spawned, free): attach to its parent unit
                    stripped = ALT.sub('', rid); shown = TIER_PREFIX.sub('', r['name'])
                    fam = next((f for f in (family(stripped),) if f in base_id), None)                         or next((f for f in base_id if f.replace('_{}', '') == stripped), None)                         or next((f for f in base_id if base_name[f] == shown), fam)
                bid = base_id.get(fam)
                name = base_name.get(fam) or TIER_PREFIX.sub('', r['name'])
                variant = None if rid == bid else (TIER_PREFIX.match(r['name']).group(1) if TIER_PREFIX.match(r['name']) else (r.get('ageName') or f'tier {tier(rid)}'))
                if alt: variant = f'{alt.group(1)} copy ({rid})' if variant is None else f'{variant}, {alt.group(1)} copy'
                if fam in alt_fams: variant = f'alternate record {rid}' if variant is None else f'{variant}, alternate record {rid}'
                if rid != bid and not alt and TIER_PREFIX.sub('', r['name']) == name and not TIER_PREFIX.match(r['name']):
                    variant = r.get('ageName') or f'tier {tier(rid)}'
                weapons = [w for w in (r.get('weapons') or []) if w.get('damage_type') in ('melee', 'ranged', 'siege')]                     or [w for w in (r.get('weapons') or []) if w.get('damage_type') == 'true damage']
                w0 = weapons[0] if weapons else None
                if costs:
                    for fld, val in cost_fields: add('unit', name, fld, val, rid, variant, quote)
                    add('unit', name, 'trainTimeSeconds', costs.get('time'), rid, variant, quote)
                add('unit', name, 'hp', r.get('hitpoints'), rid, variant, quote)
                if r.get('armor'):
                    add('unit', name, 'armor.melee', r['armor'].get('melee'), rid, variant, quote)
                    add('unit', name, 'armor.ranged', r['armor'].get('ranged'), rid, variant, quote)
                if w0:
                    add('unit', name, 'damage', w0.get('damage'), rid, variant, quote)
                    add('unit', name, 'range', w0.get('range'), rid, variant, quote)
                    interval = sum(w0.get(k, 0) for k in ('windup', 'cooldown', 'winddown', 'aim', 'reload')) + max(0.125, w0.get('burst_duration', 0))
                    add('unit', name, 'attackSpeed', round(interval, 3), rid, variant,
                        quote + ' | attackSpeed = windup+cooldown+winddown+aim+reload+max(0.125 tick, burst_duration) of ' + json.dumps(w0))
                elif 'weapons' in r:  # the record lists no damaging weapon (boats, traders, monks, cattle): no attack, not unknown
                    for fld in ('damage', 'range', 'attackSpeed'): add('unit', name, fld, 'n/a', rid, variant, quote + ' | no damaging weapon in record')
                add('unit', name, 'speed', r.get('speed'), rid, variant, quote)
                add('unit', name, 'age', AGE.get(r.get('ageName')), rid, variant, quote)
                add('unit', name, 'classes', r.get('className'), rid, variant, quote)
            elif rid.startswith('building_'):
                is_landmark = ('landmark' in (r.get('unitTypes') or []) or 'Landmark' in (r.get('className') or '')) and 'town_center' not in rid  # the capital TC is classed as a landmark but is a pre-placed building
                kind = 'landmark' if is_landmark else 'building'
                bname = r['name'] + (' (additional)' if 'town_center' in rid and 'capital' not in rid else '')  # the starting (capital) TC is the one footage shows
                variant = None
                same = [k for k, v in recs.items() if k.startswith('building_') and v.get('name') == r.get('name') and ('capital' in k) == ('capital' in rid)]
                if len(same) > 1 and rid != sorted(same, key=len)[0]: variant = f'alternate record {rid}'
                for fld, val in cost_fields: add(kind, bname, fld, val, rid, variant, quote)
                add(kind, bname, 'buildTimeSeconds', costs.get('time'), rid, variant, quote)
                add(kind, bname, 'hp', r.get('hitpoints'), rid, variant, quote)
                if is_landmark:  # the record's ageName is the age it is built in; className names the age it leads to
                    m = re.match(r'(Age I+V?)', r.get('className') or '')
                    add(kind, bname, 'age', LANDMARK_AGE.get(m.group(1)) if m else None, rid, variant, quote)
                    add(kind, bname, 'effectText', r.get('description'), rid, variant, quote)
                # building ageName is not used: it disagrees with in-game footage (Tower House, Mustering Hall, Fishpond)
            elif rid.startswith(('upgrade_', 'muster_')):
                name = r['name']
                m = re.match(r'upgrade_unit_([a-z]+)_(\d)', rid)
                if m and name.startswith('Upgrade to'):
                    fam_name = next((base_name[f] for f in base_name if f.startswith(f'unit_{m.group(1)}_')), m.group(1))
                    fam_name = names.get((civ, 'unit', fold(fam_name))) or fam_name  # checklist spelling, e.g. Skâne Crossbowman
                    if not name.endswith(fam_name): name = f'{name} {fam_name}'
                if rid.endswith('wheelbarrow_1') and name == 'Brouette': continue  # French duplicate of Wheelbarrow
                twins = sorted(k for k, v in recs.items() if k.startswith(('upgrade_', 'muster_')) and v.get('name') == r.get('name') and not k.startswith('upgrade_unit_'))
                tv = f'record {rid}' if len(twins) > 1 and rid != twins[0] else None  # e.g. Springald Emplacement on Outpost vs Keep
                for fld, val in cost_fields: add('technology', name, fld, val, rid, tv, quote)
                add('technology', name, 'researchTimeSeconds', costs.get('time') if costs else None, rid, tv, quote)
                add('technology', name, 'age', AGE.get(r.get('ageName')), rid, tv, quote)
                add('technology', name, 'effectText', r.get('description'), rid, tv, quote)
        out = DIR / 'fills' / f'jeando-{civ}.json'
        out.write_text(json.dumps({'transcribedBy': 'scripts/jeando_to_fills.py from jeandogaming.com explorer records (datamined)', 'fills': fills}, ensure_ascii=False, indent=1), encoding='utf-8')
        print(civ, len(fills), 'fills,', sum(1 for f in fills if f.get('newItem')), 'for discovered items')

if __name__ == '__main__':
    main()
