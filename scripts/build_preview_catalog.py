"""Build the Library's 17.0 preview catalog for Vikings and Scots (data/catalog-preview-17.0.json).

The installed catalog (data/game-catalog.json, Steam build 24231237) has no Vikings or Scots. This writes their
units (one record per tier, like the installed catalog), buildings, landmarks and technologies in the same record
shape, so the Library's Next view can list them beside the 17.0 overlay. Evidence kinds stay separate: nothing is
written into game-catalog.json, and every record carries `preview` with the merged checklist status and sources of
each field (data/upcoming-civs/checklist.json).

Values: the merged checklist value where the checklist has one for that record (base tier = the object's value,
higher tiers = the variant with that tier label), otherwise the datamined 17.0 record (jeandogaming.com explorer,
data/upcoming-civs/raw/jeando/<civ>_dataset.json). Speed and range are stored in engine units like the installed
catalog (4 per tile: 1.25 tiles/s -> 5). Attack interval = windup + cooldown + winddown + aim + reload +
max(0.125, burst_duration). Producers come from each object's merged `building` value.
Usage: python -X utf8 scripts/build_preview_catalog.py
"""
import collections, json, pathlib, re, unicodedata
ROOT = pathlib.Path(__file__).resolve().parents[1]
# civilization suffix of an attribute id (unit_knight_3_eng, upgrade_x__vikings, ..._abb_ha_01); a tier such as
# upgrade_melee_damage_iii must keep its _iii
CIV_SUFFIX = r'(__(vikings|scots)|_(vik|sco|abb|byz|chi|eng|fre|gol|hre|jin|jpn|lan|mac|mal|mon|ott|rus|sen|sul|tem|tug)(_ha_\w+)?|_ha_01)$'
DIR = ROOT / 'data/upcoming-civs'
OUT = ROOT / 'data/catalog-preview-17.0.json'
AGE_NUM = {'Dark': 1, 'Feudal': 2, 'Castle': 3, 'Imperial': 4}
AGE_NAME = {'Dark Age': 1, 'Feudal Age': 2, 'Castle Age': 3, 'Imperial Age': 4}
TYPE = {'melee': 'Melee', 'ranged': 'Ranged', 'fire': 'Fire', 'siege': 'Siege', 'true damage': 'True Damage'}
CIV = {'vikings': {'name': 'Vikings', 'suffix': 'vik'}, 'scots': {'name': 'Scots', 'suffix': 'sco'}}

def fold(name):
    s = unicodedata.normalize('NFKD', name.replace('&', ' and ')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', s)).strip()

def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

def source_names():
    names = {'jeando-datamined': 'datamined 17.0 records', 'installed-catalog-16.3': 'installed game 16.3', 'aoe4world-buildings': 'aoe4world building data', 'text': 'official/wiki text'}
    for v in json.loads((DIR / 'videos.json').read_text(encoding='utf-8'))['videos']:
        m = re.search(r'v=([\w-]{11})', v['url'])
        if m: names[m.group(1)] = v['channel']
    parts = ROOT / '.cache/bili/parts.json'
    if parts.exists():
        for p in json.loads(parts.read_text(encoding='utf-8')):
            names[f"{p['bvid']}_p{p['page']}"] = f"{p['owner']} (bilibili)"
    return names

def evidence(f, names, value=None, label=None):
    """Compact per-field evidence: status, value, up to 5 source labels."""
    if label:  # a tier record: the readings filed under this tier label
        rows = [v for v in f.get('variants') or [] if (v.get('variant') or '') == label and (value is None or same(v.get('value'), value))]
        srcs = sorted({v.get('videoId') for v in rows if v.get('videoId')})
        status = 'confirmed' if len(srcs) >= 2 else ('single-source' if srcs else 'record-only')
        return {'status': status, 'sources': [names.get(s, s) for s in srcs][:5]}
    srcs = []
    for s in f.get('videoSources') or []:
        if same(s.get('value'), f.get('value'), f['field']):
            lab = names.get(s.get('videoId'), s.get('videoId') or '')
            if s.get('timestamp'): lab += f" {s['timestamp']}"
            if lab not in srcs: srcs.append(lab)
    out = {'status': f['status'], 'sources': srcs[:5]}
    if f.get('dissent'): out['dissent'] = [f"{d.get('value')} ({names.get(d.get('videoId'), d.get('videoId'))})" for d in f['dissent']][:3]
    return out

def same(a, b, field=''):
    if num(a) is not None and num(b) is not None:
        if field.endswith('Seconds') and (a % 1 or b % 1) and abs(a - b) <= 0.5: return True
        return abs(a - b) <= 0.0051
    return str(a).strip().lower() == str(b).strip().lower()

COST_LABELS = {'food': 'Food', 'wood': 'Wood', 'gold': 'Gold', 'stone': 'Stone'}
UNIT_TAGS = {'military', 'infantry', 'cavalry', 'ranged', 'melee', 'human', 'siege', 'naval', 'ship', 'worker', 'religious', 'monk',
             'villager', 'scout', 'trade', 'torch_thrower', 'gunpowder', 'archer', 'crossbowman', 'spearman', 'knight', 'infantry_light',
             'infantry_heavy', 'cavalry_light', 'cavalry_heavy', 'light_melee_infantry', 'heavy_melee_infantry', 'ranged_infantry'}

def unit_tags(types):
    """Readable unit classes only; engine bookkeeping types (formational, find_*, included_by_*, scar_*) are dropped."""
    return [t for t in (types or []) if t in UNIT_TAGS]

def building_names(f):
    """'Barracks; Snowdoun Gate', 'Barracks and Mustering Hall', 'Longhouse (Smithy)' -> folded building names."""
    out = []
    for value in [f.get('value')] + list(f.get('alternatives') or []):
        if not isinstance(value, str): continue
        for part in re.split(r';|,| and | or |/', re.sub(r'\s*\([^)]*\)', '', value)):
            if part.strip(): out.append(fold(part.strip()))
    return out

BONUS_TYPES = {'cavalry': 'cavalry', 'elephants': 'war_elephant', 'elephant': 'war_elephant', 'worker elephant': 'worker_elephant', 'heavy': 'heavy',
               'light melee infantry': 'infantry_light', 'light gunpowder': 'gunpowder_light', 'ship': 'ship', 'building': 'building', 'siege': 'siege',
               'scout': 'scout', 'ranged infantry': 'ranged_infantry', 'infantry': 'infantry'}

def parse_bonus(text):
    """'+17 vs Cavalry; +3 vs Elephants' -> catalog-style bonuses. Unparsed text is kept as `note`."""
    out = []
    for m in re.finditer(r'\+\s*(\d+(?:\.\d+)?)\s*vs\.?\s*([A-Za-z ]+?)(?=;|,|\+|$)', str(text or '')):
        target = m.group(2).strip().lower()
        out.append({'unit_type': BONUS_TYPES.get(target, target.replace(' ', '_')), 'base_damage_modifier': float(m.group(1)) if '.' in m.group(1) else int(m.group(1)), 'label': m.group(2).strip()})
    return out

CLASS_WORDS = [('archer ship', 'archer_ship'), ('springald ship', 'springald_ship'), ('incendiary ship', 'naval_fireship'),
               ('military ships', 'naval_military'), ('ships', 'naval_unit'), ('gunpowder', 'gunpowder'),
               ('melee infantry', 'melee_infantry'), ('ranged infantry', 'ranged_infantry'), ('cavalry', 'cavalry'),
               ('religious units', 'monk'), ('gatherers', 'villager'), ('siege', 'siege'), ('infantry', 'infantry')]  # most specific first
BUILDING_SUBJECT = ('tower', 'keep', 'building', 'palisade', 'dock', 'landmark', 'town center', 'wall', 'longhouse', 'stealth forest', 'outpost')

def names_unit(forms, desc):
    """A unit named in the text, not as part of a ship class or an emplacement ('Archer Ship', 'Springald Emplacement')."""
    return any(re.search(rf'\b{re.escape(f)}\w*\b(?!\s+(?:ships?|emplacements?)\b)', desc) for f in forms)

def name_forms(name):
    base = re.sub(r'^(?:Early|Hardened|Veteran|Elite) ', '', name)
    base = re.sub(r'\s*\(.*\)$', '', base)
    forms = {base, base + 's'}
    if base.endswith('man'): forms.add(base[:-3] + 'men')
    if 'Man-at-Arms' in base: forms.add(base.replace('Man-at-Arms', 'Men-at-Arms'))
    return {fold(f) for f in forms if f}

def strip_civ(rid):
    return re.sub(CIV_SUFFIX, '', rid).replace('_control', '')

def installed_applicability():
    """Base unit id -> base tech ids the installed game files apply to it (data/catalog-enrichment.json upgradeGroups,
    kept when at least half of that unit's civilization copies have it; age-ups dropped)."""
    cat = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    enrich = json.loads((ROOT / 'data/catalog-enrichment.json').read_text(encoding='utf-8'))
    per_unit = collections.defaultdict(list)
    for u in cat['units']:
        groups = (enrich.get(u['id']) or {}).get('upgradeGroups') or []
        per_unit[strip_civ(u['id'])].append({strip_civ(t) for g in groups for t in g.get('technologyIds') or [] if not t.endswith('_age')})
    units = {}
    for base, copies in per_unit.items():
        votes = collections.Counter(t for c in copies for t in c)
        units[base] = {t for t, n in votes.items() if n * 2 >= len(copies)}
    return {'units': units, 'techs': {strip_civ(t['id']) for t in cat['technologies']}}

INSTALLED = None

def attach_upgrades(out, civ, meta, unit_recs, tech_recs):
    global INSTALLED
    INSTALLED = INSTALLED or installed_applicability()
    """Every unit's applicable upgrades, grouped by the building that researches them (the installed catalog's
    `upgradeGroups`). A technology applies when one of its datamined stat modifiers (jeandogaming.com comparator
    table: upgradeId, stat, targetClasses, availableCivKeys) targets a class the unit has, when it is one of this
    civ's unique technologies and its description names the unit or a class the unit has, or when it is the unit's
    own tier upgrade."""
    all_recs = json.loads((DIR / f'raw/jeando/{civ}_dataset.json').read_text(encoding='utf-8'))['records']
    def tech_id(upgrade_id):
        if upgrade_id in tech_recs: return upgrade_id
        return next((t for t in tech_recs if re.sub(r'__(vikings|scots)$', '', t) == upgrade_id), None)
    targets, stats = collections.defaultdict(set), collections.defaultdict(set)
    for m in all_recs.values():
        if 'upgradeId' in m and civ in (m.get('availableCivKeys') or []):
            tid = tech_id(m['upgradeId'])
            if tid: targets[tid].update(m.get('targetClasses') or []); stats[tid].add(m.get('stat'))
    researched_at = collections.defaultdict(list)
    for b in out['buildings']:
        if b['civilization'] == civ:
            for t in b['researchableTechnologies']: researched_at[t].append(b['id'])
    tier_up = {t for t, r in tech_recs.items() if (r.get('name') or '').startswith('Upgrade to')}
    unit_classes = set().union(*(set(r.get('unitTypes') or []) for r in unit_recs.values()))
    # read the text when the modifiers target no unit (none at all, or only buildings: Wallace's Rally speeds up the Barracks)
    textual = [t for t in tech_recs if not (targets.get(t, set()) & unit_classes) and t not in tier_up]
    standard = {t for t in tech_recs if strip_civ(t) in INSTALLED['techs']}  # same base tech exists in the installed game
    civ_forms = set().union(*(name_forms(x['name']) for x in out['units'] if x['civilization'] == civ))
    for u in (x for x in out['units'] if x['civilization'] == civ):
        rec = unit_recs[u['id']]
        classes = set(rec.get('unitTypes') or [])
        weapon_types = {w.get('damage_type') for w in rec.get('weapons') or []}
        forms = name_forms(u['name'])
        def effective(t):  # a melee-damage tech does nothing for a unit with no melee weapon (Bloomery on an archer)
            s = stats[t]
            if s and s <= {'melee_damage'} and 'melee' not in weapon_types: return False
            if s and s <= {'ranged_damage'} and 'ranged' not in weapon_types: return False
            return True
        applicable = {t for t, tc in targets.items() if tc & classes and effective(t)}
        for t in textual:
            desc = fold(tech_recs[t].get('description') or '')
            if names_unit(civ_forms, desc):  # the text names its beneficiaries ("Tacksmen and Border Reivers gain ... vs melee infantry")
                if names_unit(forms, desc): applicable.add(t)
                continue
            hits = [(desc.find(p), cls) for p, cls in CLASS_WORDS if p in desc]
            if not hits: continue
            first_class = min(i for i, _ in hits)
            found = [m.start() for b in BUILDING_SUBJECT for m in [re.search(rf'\b{b}s?\b', desc)] if m]  # whole words: 'Wallace' is not a wall
            first_building = min(found or [len(desc)])
            if first_building < first_class: continue  # a building is the subject ("Towers and Keeps gain ...")
            cls = next(c for p, c in CLASS_WORDS if p in desc)  # most specific phrase present
            if cls in classes: applicable.add(t)
        installed = INSTALLED['units'].get(strip_civ(u['id']))
        if installed is not None:
            # standard unit: damage techs exactly as the installed game files apply them (the datamined targets also
            # list villagers for Bloomery); other standard techs from both sources (the installed enrichment misses
            # e.g. Wheelbarrow and Textiles on villagers, Piety on monks)
            damage = {t for t in standard if stats[t] and stats[t] <= {'all_damage', 'melee_damage', 'ranged_damage'}}
            applicable = {t for t in applicable if t not in damage} | {t for t in standard if strip_civ(t) in installed}
        applicable |= {tr['upgrade'] for tr in u.get('tierTransitions') or [] if tr.get('upgrade') in tech_recs}
        groups = collections.defaultdict(list)
        for t in sorted(applicable):
            groups[(researched_at.get(t) or [None])[0]].append(t)
        tier = u['preview'].get('tier') or ''
        copy = 'copy' in tier or 'alternate record' in tier  # mustered / toggled / highlanders / free / landmark-spawned copy of a roster unit
        out.setdefault('meta', {})[u['id']] = {'available': True, 'rosterAvailable': not copy, 'tags': u['classes'],
                                               'upgradeGroups': [{'buildingId': b, 'technologyIds': ts} for b, ts in groups.items()]}

def main():
    chk = json.loads((DIR / 'checklist.json').read_text(encoding='utf-8'))
    names = source_names()
    items = {(i['civ'], i['kind'], fold(i['name'])): i for i in chk['items']}
    out = {'schemaVersion': 1, 'version': '17.0', 'status': 'preview, not in the installed game',
           'builtAt': chk.get('builtAt'), 'sources': 'data/upcoming-civs/checklist.json (merged: early-access video frames read twice, datamined 17.0 records, installed 16.3 files, verified web sources); data/upcoming-civs/raw/jeando/*_dataset.json',
           'summary': chk['summary'], 'civilizations': [], 'units': [], 'buildings': [], 'technologies': []}
    for civ, meta in CIV.items():
        recs = json.loads((DIR / f'raw/jeando/{civ}_dataset.json').read_text(encoding='utf-8'))['records']
        recs = {k: v for k, v in recs.items() if (v.get('civKey') == civ or k.endswith('_' + meta['suffix']) or f'__{civ}' in k)}
        # which checklist object (and tier label) each record feeds: from the datamined fills' notes
        link = {}
        for f in json.loads((DIR / f'fills/jeando-{civ}.json').read_text(encoding='utf-8'))['fills']:
            rid = f['note'].replace('record ', '')
            link.setdefault(rid, (f['kind'], f['name'], f.get('variant')))
        def obj(rid):
            k = link.get(rid)
            return (items.get((civ, k[0], fold(k[1]))), k[2]) if k else (None, None)
        def field(item, name):
            return next((f for f in (item or {}).get('fields', []) if f['field'] == name), None)
        def pick(item, label, name, record_value):
            """Merged value for this record: base -> object value, tier -> variant with this label, else record."""
            f = field(item, name)
            if f is None: return record_value, None
            if label is None:
                if f['status'] in ('unknown',) or f.get('value') is None: return record_value, evidence(f, names) if f.get('videoSources') else None
                return f['value'], evidence(f, names)
            hit = next((v['value'] for v in f.get('variants') or [] if (v.get('variant') or '') == label and v.get('confidence') == 'datamined'), None)
            value = hit if hit is not None else record_value
            return value, evidence(f, names, value, label)
        out['civilizations'].append({'id': civ, 'name': meta['name'], 'icon': None, 'preview': {'version': '17.0', 'note': 'Raiders of the North; releases 2026-10-29'},
                                     'source': {'asset': f'jeandogaming.com/en/aoe4/explorer/{civ}', 'pbgid': None, 'sha256': None}})
        producers = collections.defaultdict(list)  # building name -> record ids it trains / researches
        unit_recs = {k: v for k, v in recs.items() if k.startswith(('unit_', 'highland_cattle'))}
        tiers_by_family = collections.defaultdict(list)
        for rid in unit_recs: tiers_by_family[re.sub(r'_(\d)(?=_[a-z]+$)', '_{}', rid)].append(rid)
        for rid, r in unit_recs.items():
            item, label = obj(rid)
            costs = r.get('costs') or {}
            ev = {}
            def take(name, record_value):
                v, e = pick(item, label, name, record_value)
                if e: ev[name] = e
                return v
            cost = {res: take(f'cost.{res}', costs.get(res, 0) if costs else None) for res in ('food', 'wood', 'gold', 'stone')}
            cost = {k: (v if num(v) is not None else 0) for k, v in cost.items()}
            weapons = []
            for i, w in enumerate(r.get('weapons') or []):
                interval = sum(w.get(k, 0) for k in ('windup', 'cooldown', 'winddown', 'aim', 'reload')) + max(0.125, w.get('burst_duration', 0))
                dt = TYPE.get(w.get('damage_type'), str(w.get('damage_type')).title())
                weapons.append({'id': f'{rid}_weapon_{i}', 'name': dt + (' charge' if w.get('is_charge') else ''), 'damage': {'damage_type': dt, 'max': w.get('damage'), 'min': w.get('damage')},
                                'damageMin': w.get('damage'), 'damageMax': w.get('damage'), 'damageType': dt, 'windupSeconds': w.get('windup'), 'winddownSeconds': w.get('winddown'),
                                'cooldownSeconds': {'max': w.get('cooldown', w.get('reload')), 'min': w.get('cooldown', w.get('reload'))}, 'aimSeconds': w.get('aim'),
                                'attackIntervalSeconds': round(interval, 3), 'range': {'max': round(w.get('range', 0) * 4, 3), 'min': 0},
                                'projectileCount': w.get('projectile_count'), 'bonuses': []})
            primary = next((w for w in weapons if w['damageType'] in ('Melee', 'Ranged', 'Siege')), None) or next((w for w in weapons if w['damageType'] == 'True Damage'), None)
            if primary:
                dmg = take('damage', primary['damageMax'])
                if num(dmg) is not None: primary.update(damageMax=dmg, damageMin=dmg); primary['damage'].update(max=dmg, min=dmg)
                rng = take('range', primary['range']['max'] / 4)
                if num(rng) is not None: primary['range']['max'] = round(rng * 4, 3)
                spd = take('attackSpeed', primary['attackIntervalSeconds'])
                if num(spd) is not None: primary['attackIntervalSeconds'] = spd
                bonus = take('bonusDamage', None)
                if bonus and str(bonus).lower() not in ('none', 'none listed', 'n/a'): primary['bonuses'] = parse_bonus(bonus); primary['bonusText'] = bonus
                weapons.remove(primary); weapons.insert(0, primary)
            speed = take('speed', r.get('speed'))
            hp = take('hp', r.get('hitpoints'))
            armor = r.get('armor') or {}
            am, ar = take('armor.melee', armor.get('melee', 0)), take('armor.ranged', armor.get('ranged', 0))
            train = take('trainTimeSeconds', costs.get('time') if costs else None)
            age = take('age', {v: k for k, v in AGE_NUM.items()}.get(AGE_NAME.get(r.get('ageName'))))
            pop = take('population', None) if label is None else None
            fam = re.sub(r'_(\d)(?=_[a-z]+$)', '_{}', rid)
            transitions = []
            for other in sorted(tiers_by_family.get(fam, []), key=lambda x: x):
                if other != rid:
                    t = re.search(r'_(\d)_[a-z]+$', other)
                    if t and t.group(1) > (re.search(r'_(\d)_[a-z]+$', rid) or re.search('(0)', '0')).group(1):
                        up = next((k for k in recs if k.startswith('upgrade_unit_') and re.sub(r'upgrade_', '', k).startswith(re.sub(r'_\d_[a-z]+$', '', other).replace('unit_', 'unit_') + '_' + t.group(1))), None)
                        transitions.append({'upgrade': up, 'entity': other, 'squad': other})
            record = {'id': rid, 'civilization': civ, 'name': r.get('name'), 'description': r.get('description') or '', 'icon': r.get('icon'),
                      'cost': cost, 'costLabels': COST_LABELS, 'displayCost': {k: v for k, v in cost.items() if num(v) and v > 0},
                      'trainTimeSeconds': train if num(train) is not None else None, 'hp': hp if num(hp) is not None else None,
                      'armor': {'Melee': am if num(am) is not None else 0, 'Ranged': ar if num(ar) is not None else 0, 'Fire': 0},
                      'speedEngineUnits': round(speed * 4, 4) if num(speed) is not None else None, 'population': pop if num(pop) is not None else 1,
                      'age': AGE_NUM.get(age) if isinstance(age, str) else age, 'classes': unit_tags(r.get('unitTypes')), 'weapon': weapons,
                      'tierTransitions': transitions, 'statStatus': 'preview-17.0',
                      'preview': {'version': '17.0', 'object': item['name'] if item else r.get('name'), 'tier': label, 'fields': ev}}
            out['units'].append(record)
            b = field(item, 'building')
            if b and label is None:
                for bn in building_names(b):
                    producers[bn].extend(tiers_by_family.get(fam, [rid]))
        tech_recs = {k: v for k, v in recs.items() if k.startswith(('upgrade_', 'muster_')) and not k.endswith('wheelbarrow_1')}
        for rid, r in tech_recs.items():
            item, label = obj(rid)
            costs = r.get('costs') or {}
            ev = {}
            def take(name, record_value):
                v, e = pick(item, label, name, record_value)
                if e: ev[name] = e
                return v
            cost = {res: take(f'cost.{res}', costs.get(res, 0) if costs else 0) for res in ('food', 'wood', 'gold', 'stone')}
            cost = {k: (v if num(v) is not None else 0) for k, v in cost.items()}  # n/a (auto-researched) = nothing paid
            rt = take('researchTimeSeconds', costs.get('time') if costs else None)
            age = take('age', {v: k for k, v in AGE_NUM.items()}.get(AGE_NAME.get(r.get('ageName'))))
            take('effectText', r.get('description'))
            record = {'id': rid, 'civilization': civ, 'name': item['name'] if item else r.get('name'), 'description': r.get('description') or '', 'icon': r.get('icon'),
                      'cost': cost, 'costLabels': COST_LABELS, 'displayCost': {k: v for k, v in cost.items() if num(v) and v > 0}, 'researchTimeSeconds': rt if num(rt) is not None else None,
                      'age': AGE_NUM.get(age) if isinstance(age, str) else None, 'requirements': [], 'modifiers': [], 'statStatus': 'preview-17.0',
                      'preview': {'version': '17.0', 'object': item['name'] if item else r.get('name'), 'tier': label, 'fields': ev}}
            out['technologies'].append(record)
            b = field(item, 'building')
            if b:
                for bn in building_names(b):
                    producers[bn].append(rid)
        for rid, r in recs.items():
            if not rid.startswith('building_'): continue
            item, label = obj(rid)
            costs = r.get('costs') or {}
            ev = {}
            def take(name, record_value):
                v, e = pick(item, label, name, record_value)
                if e: ev[name] = e
                return v
            cost = {res: take(f'cost.{res}', costs.get(res, 0) if costs else 0) for res in ('food', 'wood', 'gold', 'stone')}
            cost = {k: (v if num(v) is not None else 0) for k, v in cost.items()}
            bt = take('buildTimeSeconds', costs.get('time') if costs else None)
            hp = take('hp', r.get('hitpoints'))
            age = take('age', None)
            if (item or {}).get('kind') == 'landmark': take('effectText', r.get('description'))
            name = r.get('name')
            ids = producers.get(fold(name), [])
            record = {'id': rid, 'civilization': civ, 'name': name, 'description': r.get('description') or '', 'icon': r.get('icon'),
                      'cost': cost, 'costLabels': COST_LABELS, 'displayCost': {k: v for k, v in cost.items() if num(v) and v > 0}, 'buildTimeSeconds': bt if num(bt) is not None else None,
                      'hp': hp if num(hp) is not None else None, 'armor': {'Ranged': (r.get('armor') or {}).get('ranged', 0), 'Melee': (r.get('armor') or {}).get('melee', 0)},
                      'age': AGE_NUM.get(age) if isinstance(age, str) else None,
                      'trainableUnits': sorted({i for i in ids if i in unit_recs}), 'researchableTechnologies': sorted({i for i in ids if i in tech_recs}),
                      'statStatus': 'preview-17.0', 'preview': {'version': '17.0', 'object': item['name'] if item else name, 'tier': label, 'fields': ev,
                                                                'landmark': (item or {}).get('kind') == 'landmark'}}
            out['buildings'].append(record)
        attach_upgrades(out, civ, meta, unit_recs, tech_recs)
        named_age = {b['name']: b['age'] for b in out['buildings'] if b['civilization'] == civ and b['age']}
        for b in out['buildings']:  # bastion / upgraded copies take the age of the same-named building
            if b['civilization'] == civ and not b['age'] and b['name'] in named_age: b['age'] = named_age[b['name']]
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    counts = {k: collections.Counter(r['civilization'] for r in out[k]) for k in ('units', 'buildings', 'technologies')}
    orphans = [(t['civilization'], t['name']) for t in out['technologies'] if not any(t['id'] in b['researchableTechnologies'] for b in out['buildings'])]
    print(OUT, round(OUT.stat().st_size / 2**20, 2), 'MB', {k: dict(v) for k, v in counts.items()})
    print('techs without a producing building:', len(orphans), orphans[:20])
    print('units without a producing building:', [(u['civilization'], u['name']) for u in out['units'] if not any(u['id'] in b['trainableUnits'] for b in out['buildings'])][:30])

if __name__ == '__main__':
    main()
