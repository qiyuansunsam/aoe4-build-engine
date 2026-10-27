"""Compile data/civ-rules/<civ>.json (installed 16.3.11308 rule packs with evidence) into the compact tables the
multi-civilization engine reads: data/civ-engine-rules.json.

Every number comes from a rule pack (which cites the installed catalog, decoded Attrib records or the installed
locale). This script renames keys, converts units (engine units -> tiles, per minute -> per second), groups
technology variants (landmark copies, Mongol Improved copies) and records the modelling glue per civilization: which
building is the berry drop-off, which pack mechanic feeds which engine slot, and the map/placement assumptions the
packs cannot settle (named under `assumptions`, each overridable from the comparison page parameters).
Usage: python -X utf8 scripts/build_civ_engine_rules.py
"""
import importlib, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
BY_ID = {r['id']: r for k in ('units', 'buildings', 'technologies') for r in CATALOG[k]}
RES = ('food', 'wood', 'gold', 'stone')
TILE = 4.0  # engine units per tile: installed movement values / 4 = tiles per second (as the Library shows speed)
CIVS = ('french', 'mongol', 'malian', 'japanese')
NAMES = {'french': 'French', 'mongol': 'Mongols', 'malian': 'Malians', 'japanese': 'Japanese', 'scots': 'Scots', 'vikings': 'Vikings'}
# Civilizations whose glue lives in scripts/civ_glue/<civ>.py (a `glue(p, s, helpers)` function); their packs may target a
# preview patch (17.0 records for Vikings/Scots), in which case ids stand in for installed pbgids.
GLUE_DIR = ROOT / 'scripts/civ_glue'
EXTRA = tuple(sorted(f.stem for f in GLUE_DIR.glob('*.py') if not f.stem.startswith('_') and (ROOT / 'data/civ-rules' / f'{f.stem}.json').exists())) if GLUE_DIR.exists() else ()
# Not stat upgrades of the line itself: researched when planned, not part of the done condition.
NOT_LINE_STAT = re.compile(r'military_academy|enlistment_incentives|farima_leadership|siege_engineers|precision_training')


def cost(c):
    return {r: round(float((c or {}).get(r, 0) or 0), 4) for r in RES}


PREVIEW = {'on': False}  # set while compiling a pack that is not on the installed patch


def pbgid(record_id, fallback=None):
    r = BY_ID.get(record_id)
    got = (r or {}).get('source', {}).get('pbgid') or fallback
    return got if got or not PREVIEW['on'] else record_id  # preview civs: the 17.0 record id is the key


def kebab(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')


def load(civ):
    return json.loads((ROOT / 'data/civ-rules' / f'{civ}.json').read_text(encoding='utf-8'))


def ev_list(x):
    return [e for e in (x or {}).get('evidence', []) if isinstance(e, str)][:4]


def tech_effects(tid, t, civ):
    """Engine effects for a technology, keyed by the installed id pattern; values from the pack's own effect list."""
    effs, out = t.get('effects') or [], []
    val = lambda kind, default=None: next((e.get('value') for e in effs if e.get('kind') == kind and isinstance(e.get('value'), (int, float))), default)
    base = re.sub(r'_(improved_)?mon$|_jpn$|_kura_jpn$|_fre$|_mal$|_vik$|_sco$|__scots$|__vikings$', '', tid).replace('_improved', '')
    if 'food_harvest_rate' in base:
        out.append({'kind': 'gather_rate', 'target': 'food_soft', 'op': 'mul', 'value': val('gather_rate', 1.1)})
    elif 'wood_harvest_rate' in base:
        out.append({'kind': 'gather_rate', 'target': 'wood', 'op': 'mul', 'value': val('gather_rate', 1.15)})
        if base.endswith('_4'):
            carry = next((e.get('value') for e in effs if e.get('kind') == 'carry' and isinstance(e.get('value'), (int, float))), 5)
            out.append({'kind': 'carry', 'target': 'wood', 'op': 'add', 'value': carry})
    elif 'gold_harvest_rate' in base:
        v = val('gather_rate', None)
        if v is None:  # Cupellation: gold gatherers drop off 15% more per trip (formatter argument 15)
            v = next((e.get('value') for e in effs if isinstance(e.get('value'), (int, float)) and 1 < e.get('value') < 2), 1.15)
        out.append({'kind': 'gather_rate', 'target': 'gold' if (civ == 'mongol' or base.endswith('_4')) else 'mine', 'op': 'mul', 'value': v})
    elif 'wheelbarrow' in base:
        carry = next((e.get('value') for e in effs if e.get('kind') == 'carry' and isinstance(e.get('value'), (int, float))), None)
        speed = next((e.get('value') for e in effs if e.get('kind') == 'speed' and isinstance(e.get('value'), (int, float))), None)
        if carry: out.append({'kind': 'carry', 'target': 'all', 'op': 'add', 'value': carry})
        if speed: out.append({'kind': 'speed', 'target': 'villager', 'op': 'mul', 'value': speed})
    elif 'hunting_gear' in base:
        out.append({'kind': 'gather_rate', 'target': 'hunt', 'op': 'mul', 'value': val('gather_rate', 1.15)})
    elif 'military_academy' in base:
        out.append({'kind': 'production_speed', 'target': 'military', 'op': 'mul', 'value': val('production_speed', 1.33)})
    # Some packs write a rate bonus as the raw fraction (0.15) rather than the multiplier (1.15).
    for e in out:
        if e['kind'] in ('gather_rate', 'production_speed') and e['op'] == 'mul' and 0 < e['value'] < 1: e['value'] = round(1 + e['value'], 4)
    return out


def building_key(raw, landmark_ids):
    s = str(raw or '').strip()
    if not s: return None
    s = re.split(r'\s+\(|\s+or\s+', s)[0].strip()
    if s.startswith('landmark:'): return s
    if s in landmark_ids: return 'landmark:' + landmark_ids[s]
    if s.lower() in ('landmark',): return None
    return kebab(s.replace('_', '-'))


def compile_civ(civ):
    p = load(civ)
    PREVIEW['on'] = not str(p.get('patch', '16.3.11308')).startswith('16.3')
    lm_ids = {}
    landmarks = {}
    for age, opts in (p.get('landmarks') or {}).items():
        landmarks[int(age)] = []
        for l in opts:
            key = l.get('key') or kebab(l['name'])
            lm_ids[l['id']] = key
    for age, opts in (p.get('landmarks') or {}).items():
        for l in opts:
            key = lm_ids[l['id']]
            landmarks[int(age)].append({'key': key, 'id': l['id'], 'pbgid': pbgid(l['id']), 'name': l['name'], 'cost': cost(l.get('cost')),
                                        'time': l.get('buildSeconds'), 'effects': [], 'notes': [e.get('notes', '') for e in l.get('effects') or []][:3]})
    buildings = {}
    for k, b in (p.get('buildings') or {}).items():
        key = kebab(k.replace('_', '-'))
        buildings[key] = {'id': b.get('id'), 'pbgid': pbgid(b.get('id')), 'name': (BY_ID.get(b.get('id')) or {}).get('name') or b.get('name') or k.replace('_', ' ').title(),
                          'cost': cost(b.get('cost')), 'time': b.get('buildSeconds'), 'age': b.get('age') or 1, 'accepts': b.get('dropoff') or [],
                          'eco': key in ('house', 'farmhouse', 'mill', 'lumber-camp', 'mining-camp', 'farm', 'ger', 'pasture', 'ovoo', 'forge', 'cattle-ranch', 'pit-mine')}
    tc = p['townCenter']
    buildings['town-center'] = {'id': tc.get('extraId'), 'pbgid': pbgid(tc.get('extraId'), tc.get('extraPbgid')), 'name': 'Town Center', 'cost': cost(tc.get('cost')), 'time': tc.get('buildSeconds'),
                                'age': tc.get('extraRequiresAge') or 2, 'accepts': ['food', 'wood', 'gold', 'stone'], 'eco': False}
    techs, groups = {}, {}
    for t in p.get('technologies') or []:
        tid = t['id']
        if tid in ('feudal_age', 'castle_age', 'imperial_age'): continue
        bkey = building_key(t.get('building'), lm_ids)
        if bkey == 'town-center' or bkey == 'town_center': bkey = 'town-center'
        cat = t.get('category') or 'other'
        if cat == 'landmark' and bkey and not bkey.startswith('landmark:'): cat = 'military'
        rec = {'pbgid': pbgid(tid), 'name': t['name'], 'age': t.get('age') or 1, 'building': bkey, 'buildingName': (buildings.get(bkey) or {}).get('name') or (t.get('building') or ''),
               'cost': cost(t.get('cost')), 'time': t.get('researchSeconds') or 0, 'cat': 'economy' if cat == 'economy' else cat, 'effects': tech_effects(tid, t, civ)}
        if bkey and bkey.startswith('landmark:'): rec['landmark'] = bkey[9:]
        if '_improved' in tid: rec['improved'] = True
        techs[tid] = rec
    # variants: landmark copies (upgrade_landmark_X_fre -> upgrade_X_fre), Mongol Improved copies, Japanese Kura copies
    for tid in list(techs):
        base = None
        if tid.startswith('upgrade_landmark_'): base = 'upgrade_' + tid[len('upgrade_landmark_'):]
        elif '_improved_mon' in tid: base = tid.replace('_improved_mon', '_mon') if tid.replace('_improved_mon', '_mon') in techs else tid.replace('_improved_mon', '')
        elif tid == 'upgrade_unit_wheelbarrow_1_improved_mon': base = 'upgrade_unit_town_center_wheelbarrow_1_mon'
        elif tid.endswith('_kura_jpn'): base = tid.replace('_kura_jpn', '_jpn')
        if base and base in techs:
            techs[tid]['groupOf'] = base
            techs[base].setdefault('variants', []).append(tid)
            techs[tid]['cat'] = techs[base]['cat']
    lines = {}
    for l in (p.get('army') or {}).get('lines') or []:
        key = kebab(l['key'].replace('_', '-'))
        prods = [building_key(x, lm_ids) for x in l.get('producers') or []]
        tiers = [{'age': t.get('age') or 1, 'pbgid': pbgid(t['id']), 'id': t['id'], 'name': t['name'], 'cost': cost(t.get('cost')), 'time': t.get('trainSeconds'), 'pop': t.get('pop') or 1} for t in l['tiers']]
        # Tier ages run upward: a later tier never comes before the earlier one.
        for i in range(1, len(tiers)): tiers[i]['age'] = max(tiers[i]['age'], tiers[i - 1]['age'])
        for i, u in enumerate(l.get('tierUpgrades') or []):
            if u in techs:
                techs[u]['tierOf'] = key; techs[u]['tierIndex'] = i + 1
                if i > 0: techs[u]['requires'] = [l['tierUpgrades'][i - 1]]
                techs[u]['cat'] = 'unit-tier'
        want = []
        for u in (l.get('tierUpgrades') or []) + (l.get('applicableTechs') or []):
            if u not in techs or NOT_LINE_STAT.search(u): continue
            base = techs[u].get('groupOf') or u
            if base not in want: want.append(base)
        lines[key] = {'name': l['name'].split(' (')[0], 'producers': [x for x in prods if x], 'tiers': tiers, 'techs': want}
    v = p['villager']
    gather = {}
    for src, g in v['gather'].items():
        if not isinstance(g, dict) or g.get('rate') is None: continue
        gather[{'boar': 'boar', 'shore_fish': 'fish'}.get(src, src)] = {'rate': g['rate'], 'carry': g.get('carry', 10)}
    start = p['start']
    units = [{'pbgid': pbgid(u['id'], u.get('pbgid')), 'name': u['name'], 'count': u['count'], 'pop': 1}
             for u in start.get('units', []) if u['id'].startswith('unit_') and 'villager' not in u['id']]
    spec = {'key': civ, 'name': NAMES[civ], 'patch': p.get('patch', '16.3.11308'),
            'start': {'villagers': start['villagers'], 'res': cost(start['resources']), 'popCap': start.get('popCap') or 10, 'units': units},
            'villager': {'pbgid': pbgid(v['id']), 'cost': cost(v['cost']), 'time': v['trainSeconds'], 'speed': (v.get('speedEngineUnits') or 4.5) / TILE, 'gather': gather},
            'tc': {'pbgid': pbgid(tc.get('extraId')), 'pop': tc.get('popProvided') if tc.get('popProvided') is not None else 10, 'prodByAge': {int(k): v for k, v in (tc.get('villagerProductionMultiplierByAge') or {}).items()}},
            'buildings': buildings, 'landmarks': landmarks, 'techs': techs, 'lines': lines, 'mech': {}, 'startEffects': [], 'roles': {}, 'assumptions': {},
            'sources': f'data/civ-rules/{civ}.json'}
    return p, spec


def mech(p, key):
    m = next((m for m in p.get('mechanics') or [] if m['key'] == key), None)
    return (m or {}).get('params') or {}


def lm(spec, key):
    for opts in spec['landmarks'].values():
        for l in opts:
            if l['key'] == key: return l
    raise KeyError(key)


def french(p, s):
    b = s['buildings']
    b['house']['pop'] = 10; b['house']['house'] = True
    s['house'] = 'house'; s['blacksmith'] = 'blacksmith'
    s['assumptions']['housePop'] = 'House +10 population (statemodel default; not stated in the French records, same value the Japanese and Malian packs read)'
    lm(s, 'school-of-cavalry')['producer'] = {'lines': ['royal-knight']}
    lm(s, 'school-of-cavalry')['effects'] = [{'kind': 'production_speed', 'target': 'stable', 'op': 'mul', 'value': 1.2}]
    lm(s, 'guild-hall')['effects'] = [{'kind': 'passive_income', 'target': 'gold', 'op': 'add', 'value': 1.0}]
    s['assumptions']['guildHall'] = 'Guild Hall at its lowest step (20 per 20 s); its growth thresholds are not in installed records'
    lm(s, 'royal-institute')['effects'] = []
    s['ageUpGrants'] = {2: ['upgrade_melee_damage_i'], 3: ['upgrade_melee_damage_ii'], 4: ['upgrade_melee_damage_iii']}
    s['defaultLines'] = ['royal-knight']
    s['defaults'] = {}
    s['unmodeled'] = ['Chamber of Commerce traders', 'Red Palace and keep effects', 'College of Artillery', 'trade', 'Royal Knight charge damage']


def malian(p, s):
    b = s['buildings']
    b['house']['house'] = True; b['house']['pop'] = mech(p, 'baked-civ-discounts').get('house', {}).get('pop', 5)
    s['house'] = 'house'; s['blacksmith'] = 'blacksmith'
    pm = mech(p, 'pit-mine'); cat = mech(p, 'cattle'); ranch = mech(p, 'cattle-ranch'); corral = mech(p, 'grand-fulani-corral'); quarry = mech(p, 'mansa-quarry')
    s['mech'] = {
        'pitMine': {'goldPerSecond': pm.get('goldPerSecond', 0.6), 'perHouse': pm.get('perHouse', 0.25), 'op': 'add', 'limit': pm.get('limitPerPlayerRaw', 1)},
        'cattle': {'pbgid': pbgid(cat.get('unitId')), 'name': 'Cattle', 'producers': cat.get('producers', ['mill']), 'cost': cost(cat.get('cost')), 'time': cat.get('trainSeconds', 15), 'food': cat.get('food', 500), 'cap': cat.get('vehicleCap', 20), 'distance': 0.5},
        'ranch': {'slots': ranch.get('slots', 3), 'foodPerSecond': ranch.get('foodPerSecond', 25 / 60)},
        'corral': {'foodPerSecond': corral.get('foodPerSecond', 0.3)},
    }
    s['villager']['gather']['cattle'] = {'rate': cat.get('villagerGatherRate', 0.81), 'carry': cat.get('villagerCarry', 10)}
    lm(s, 'mansa-quarry')['effects'] = [{'kind': 'passive_income', 'target': 'gold', 'op': 'add', 'value': quarry.get('goldPerSecond', 1.25)}]
    lm(s, 'grand-fulani-corral')['corral'] = True
    s['assumptions'].update({'pitHouses': 'At most 8 Houses or Mining Camps fit inside one Pit Mine influence (influence generator range 4; geometry, not a game value)',
                             'cattle': 'Ranch food scales with completed food technologies; garrisoned cattle do not deplete; Corral income stacks with Ranch income (pack: unresolved)',
                             'pitMineStacking': 'Pit Mine rate 36 x (1 + 0.25 n) with n Houses + Mining Camps in its influence (pack formula)'})
    s['defaultLines'] = ['sofa']
    s['defaults'] = {'cattle': {'ranch': True, 'ranches': {'2': 2, '3': 4, '4': 4}, 'herdTarget': 0, 'age': 1, 'from': 0}, 'mech': {'pitMines': 1, 'pitHouses': 8}}
    s['unmodeled'] = ['trade and Toll Outposts', 'Saharan Trade Network', 'Farimba Garrison units', 'Griot Bara festivals', 'Manuscript Trade']


def japanese(p, s):
    b = s['buildings']
    b['farmhouse']['pop'] = mech(p, 'farmhouse').get('popProvided', 10); b['farmhouse']['house'] = True
    s['house'] = 'farmhouse'; s['blacksmith'] = 'forge'
    s['roles'] = {'berries': 'farmhouse', 'deer': 'farmhouse', 'berriesFar': 'farmhouse', 'gold': 'forge', 'stone': 'forge'}
    d = mech(p, 'daimyo_town_center_upgrades'); y = mech(p, 'yorishiro_placement'); g = mech(p, 'floating_gate_yorishiro'); k = mech(p, 'kura_storehouse'); sm = mech(p, 'silver_mining')
    for tier in d.get('tiers', []):
        t = s['techs'].get(tier['id'])
        if t:
            t['building'] = 'town-center'; t['cat'] = 'civ-economy'
            t['effects'] = [{'kind': 'farm_aura', 'target': 'farm_near_tc', 'op': 'set', 'value': tier['farmGatherMultiplier']}]
            t['freeVillagers'] = tier.get('freeVillagers', 1)
    for a, b_ in (('upgrade_capital_tier_2_jpn', 'upgrade_capital_tier_1_jpn'), ('upgrade_capital_tier_3_jpn', 'upgrade_capital_tier_2_jpn')):
        if a in s['techs']: s['techs'][a]['requires'] = [b_]
    s['mech'] = {
        'yorishiro': {'interval': g.get('intervalSeconds', 120), 'cap': g.get('cap', 4), 'bunrei': 'upgrade_shrine_bunrei_jpn', 'bunreiAdd': g.get('bunreiCapAdd', 2),
                      'tcProduction': 1 + y.get('townCenterProductionSpeedPct', 30) / 100, 'farmhouseFood': y.get('farmhouseFoodPerMinute', 70) / 60,
                      'lumberWood': y.get('lumberCampWoodPerMinute', 70) / 60, 'forgeGold': y.get('forgeGoldPerMinute', 50) / 60},
        'kura': {'farmInterval': k.get('farmSpawnIntervalSeconds', 50)},
        'silverMining': {'fraction': sm.get('bonusPct', 20) / 100},
        'noFarmTechs': True,
    }
    lm(s, 'floating-gate')['yorishiro'] = True
    lm(s, 'kura-storehouse')['kura'] = True
    s['assumptions'].update({'kuraFarms': 'The Kura Storehouse spawns at most 8 free farms (farmland capacity is not in installed records)',
                             'farmsNearTC': 'Up to 12 farms fit inside one Town Center farm aura (range 40 engine units; geometry, not a game value)',
                             'yorishiro': 'Yorishiro income is continuous at the tooltip rate (delivery mechanism not in installed records)'})
    s['defaultLines'] = ['samurai', 'onna-bugeisha']
    s['defaults'] = {'mech': {'kuraFarms': 8, 'farmsPerTC': 12, 'yorishiro': ['farmhouse', 'farmhouse', 'lumber', 'tc', 'farmhouse', 'lumber']},
                     'civTechs': {'upgrade_capital_tier_1_jpn': 2, 'upgrade_capital_tier_2_jpn': 3, 'upgrade_capital_tier_3_jpn': 4}}
    s['unmodeled'] = ['Bannermen and their auras', 'Buddhist Zen gold', 'Castle of the Crow caravans', 'Tanegashima stockpile', 'Koka Township shinobi']


def mongol(p, s):
    s['house'] = None; s['blacksmith'] = 'blacksmith'
    s['mech'] = {'noHouses': True}
    s['roles'] = {'berries': 'ger', 'deer': 'ger', 'berriesFar': 'ger', 'wood': 'ger', 'gold': 'ger', 'stone': None}
    pa = mech(p, 'pasture'); ov = mech(p, 'ovoo_stone'); dp = mech(p, 'double_production'); dep = mech(p, 'ovoo_depletion')
    s['mech']['pasture'] = {'interval': pa.get('interval', 140), 'sheepFood': pa.get('sheepFood', 200), 'distance': 1.0}
    s['mech']['ovoo'] = {'stonePerSecondByAge': {int(k): v for k, v in ov.get('stonePerSecondByAge', {}).items()}, 'deposits': [dep.get('largeDeposit', 2400), dep.get('smallDeposit', 1200)]}
    items = {}
    for iid, it in (dp.get('items') or {}).items():
        items[iid] = {'producer': it['producer'], 'cost': cost(it.get('chargedCostIfMultiplied')), 'units': it.get('unitsPerItem', 2)}
    s['mech']['double'] = {'villager': next((v['cost'] for k, v in items.items() if 'villager' in k), None),
                           'lines': {}}
    for lk, line in s['lines'].items():
        for t in line['tiers']:
            dk = t['id'].replace('_mon', '_double_mon').replace('unit_', 'unit_', 1)
            if dk in items: t['doubleCost'] = items[dk]['cost']
    lm(s, 'white-stupa')['effects'] = [{'kind': 'passive_income', 'target': 'stone', 'op': 'add', 'value': 4.0}, {'kind': 'cost', 'target': 'double-stone', 'op': 'mul', 'value': 0.5}]
    lm(s, 'steppe-redoubt')['effects'] = [{'kind': 'gather_rate', 'target': 'gold', 'op': 'mul', 'value': 1.5}]
    s['buildings']['ger']['accepts'] = ['food', 'wood', 'gold']
    s['assumptions'].update({'producersInOvoo': 'Town Center and production buildings stand inside the Ovoo influence, so double production is available (placement choice)',
                             'redoubtAtGold': 'The Steppe Redoubt is placed at the gold mine, so every gold villager drops off there (+50%)',
                             'stoneDeposits': 'The Ovoo draws on one large (2,400) then one small (1,200) stone outcrop',
                             'pastureInterval': 'Pasture sheep every 140 s (current tooltip argument; the sheep record says 112 s)'})
    s['defaultLines'] = ['keshik']
    s['defaults'] = {'mech': {'doubleVillagers': True, 'doubleArmy': True, 'improved': False}}
    # The army start list includes one packed Ger (unpacked in 8 s); the engine places it at the wood line from the start.
    s['start']['freeBuildings'] = [{'key': 'ger', 'site': 'wood', 'pbgid': pbgid('building_house_mon')}]
    s['assumptions']['startGer'] = 'The packed starting Ger is unpacked at the wood line at the start (its 8 s unpack is not modelled)'
    s['planExtras'] = {'1': [['b', 'ovoo', 'stone']]}
    s['unmodeled'] = ['trade and the Silk Road', 'Khaganate Palace free armies', 'Kurultai aura', 'plunder', 'Yam speed', 'packing']


GLUE = {'french': french, 'malian': malian, 'japanese': japanese, 'mongol': mongol}
HELPERS = {'mech': mech, 'lm': lm, 'cost': cost, 'pbgid': pbgid, 'kebab': kebab, 'BY_ID': BY_ID, 'ROOT': ROOT}


def extra_glue(civ):
    sys.path.insert(0, str(GLUE_DIR))
    try:
        mod = importlib.import_module(civ)
    finally:
        sys.path.pop(0)
    return lambda p, s: mod.glue(p, s, HELPERS)


if __name__ == '__main__':
    out = {'schemaVersion': 1, 'patch': '16.3.11308', 'generatedBy': 'scripts/build_civ_engine_rules.py', 'civs': {}}
    for civ in CIVS + EXTRA:
        p, s = compile_civ(civ)
        (GLUE.get(civ) or extra_glue(civ))(p, s)
        PREVIEW['on'] = False
        out['civs'][civ] = s
        print(civ, len(s['techs']), 'techs,', len(s['buildings']), 'buildings,', sum(len(v) for v in s['landmarks'].values()), 'landmarks, lines', {k: len(v['techs']) for k, v in s['lines'].items()})
    # atomic replace: several agents may compile and read the rules at the same time
    tmp = ROOT / f'data/civ-engine-rules.json.{os.getpid()}.tmp'
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(tmp, ROOT / 'data/civ-engine-rules.json')
    print('wrote data/civ-engine-rules.json', (ROOT / 'data/civ-engine-rules.json').stat().st_size // 1024, 'KB')
