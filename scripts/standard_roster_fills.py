"""Fill production building / age for the Vikings' and Scots' standard objects from the installed game data.

Standard units, buildings and technologies in the datamined 17.0 records (data/upcoming-civs/raw/jeando/*) share
their base attribute id with every other civilization's copy (unit_archer_2_vik ~ unit_archer_2_eng). Where the 17.0
records do not say which building trains/researches an object, the installed 16.3 catalog's producer lists
(data/game-catalog.json: trainableUnits / researchableTechnologies, majority over civilizations, landmarks excluded)
give it, and standard building ages come from data/buildings_all.json (aoe4world data, majority over civilizations).
Every fill carries confidence "standard-roster" and the ids it was matched on; unique objects are never filled here.
Writes data/upcoming-civs/fills/standard-roster.json.
Usage: python -X utf8 scripts/standard_roster_fills.py
"""
import collections, json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
# civilization suffix of an attribute id (unit_knight_3_eng, upgrade_x__vikings, ..._abb_ha_01); a tier such as
# upgrade_melee_damage_iii must keep its _iii
CIV_SUFFIX = r'(__(vikings|scots)|_(vik|sco|abb|byz|chi|eng|fre|gol|hre|jin|jpn|lan|mac|mal|mon|ott|rus|sen|sul|tem|tug)(_ha_\w+)?|_ha_01)$'
DIR = ROOT / 'data/upcoming-civs'
AGES = {1: 'Dark', 2: 'Feudal', 3: 'Castle', 4: 'Imperial'}

def base(rid):
    return re.sub(r'(__(vikings|scots)|_(vik|sco))$', '', rid)

def main():
    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    producers = collections.defaultdict(collections.Counter)
    for b in catalog['buildings']:
        if 'landmark' in b['id'] or 'wonder' in b['id'] or 'capital' in b['id']: continue
        for uid in b.get('trainableUnits') or []: producers[re.sub(CIV_SUFFIX, '', uid)][b['name']] += 1
        for tid in b.get('researchableTechnologies') or []: producers[re.sub(CIV_SUFFIX, '', tid)][b['name']] += 1
    ages = collections.defaultdict(collections.Counter)
    for b in json.loads((ROOT / 'data/buildings_all.json').read_text(encoding='utf-8'))['data']:
        if b.get('age'): ages[b['name']][b['age']] += 1
    # gaps are taken from the datamined fills alone (never from the merged checklist, which already holds this
    # script's previous output): a standard object whose record names no producer / age gets one here
    record_of, provided = {}, collections.defaultdict(set)
    for civ in ('vikings', 'scots'):
        for f in json.loads((DIR / f'fills/jeando-{civ}.json').read_text(encoding='utf-8'))['fills']:
            if f.get('variant') is not None or not f.get('newItem'): continue
            record_of.setdefault((civ, f['kind'], f['name']), f['note'].replace('record ', ''))
            provided[(civ, f['kind'], f['name'])].add(f['field'])
    civ_buildings = {civ: {r.get('name') for k, r in json.loads((DIR / f'raw/jeando/{civ}_dataset.json').read_text(encoding='utf-8'))['records'].items() if k.startswith('building_')}
                     for civ in ('vikings', 'scots')}
    fills = []
    for (civ, kind, name), rid in record_of.items():
        it = {'civ': civ, 'kind': kind, 'name': name}
        unknown = {'building', 'age'} - provided[(civ, kind, name)]
        if 'building' in unknown and rid and it['kind'] in ('unit', 'technology'):
            hits = producers.get(base(rid)) or producers.get(re.sub(r'_\d$', '', base(rid)))
            own = {n: c for n, c in (hits or {}).items() if n in civ_buildings[civ]}  # only buildings this civ has (Scots: Blacksmith, not Forge/Arsenal)
            if own:
                name, n = max(own.items(), key=lambda kv: kv[1])
                fills.append({'civ': it['civ'], 'kind': it['kind'], 'name': it['name'], 'field': 'building', 'value': name, 'variant': None,
                              'videoId': 'installed-catalog-16.3', 'timestamp': None, 'confidence': 'standard-roster',
                              'quote': f'{base(rid)} is produced at {name} for {n} civilizations in the installed 16.3 catalog',
                              'note': f'record {rid}; not observed for {it["civ"]}'})
        if 'age' in unknown and it['kind'] == 'building':
            plain = re.sub(r'\s*\(.*\)$', '', it['name'])
            if ages.get(plain):
                age, n = ages[plain].most_common(1)[0]
                fills.append({'civ': it['civ'], 'kind': 'building', 'name': it['name'], 'field': 'age', 'value': AGES[age], 'variant': None,
                              'videoId': 'aoe4world-buildings', 'timestamp': None, 'confidence': 'standard-roster',
                              'quote': f'{plain} requires age {age} for {n} civilizations in data/buildings_all.json',
                              'note': f'standard building; not observed for {it["civ"]}'})
    (DIR / 'fills/standard-roster.json').write_text(json.dumps({'transcribedBy': 'scripts/standard_roster_fills.py (installed catalog producers, aoe4world building ages)', 'fills': fills},
                                                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(fills), 'standard-roster fills', collections.Counter(f['field'] for f in fills))

if __name__ == '__main__':
    main()
