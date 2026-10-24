"""Cross-check the Vikings'/Scots' standard objects against the installed 16.3 game files.

Standard units, buildings and technologies share a base attribute id across civilizations (unit_archer_2_vik,
unit_archer_2_eng ...). For every datamined 17.0 standard record, the installed catalog (data/game-catalog.json, read
from the Steam build's Attrib.sga) gives the same base object's 16.3 values (majority over civilization copies).
Equal values become a second, independent source (videoId "installed-catalog-16.3"); different values are kept as a
variant "installed 16.3 value" so the 17.0 change (or civ-specific difference) is visible without a false conflict.
Speed: catalog speedEngineUnits / 4 = tiles per second (archer 5 -> 1.25). Writes fills/catalog-crosscheck.json.
Usage: python -X utf8 scripts/catalog_crosscheck_fills.py
"""
import collections, json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
# civilization suffix of an attribute id (unit_knight_3_eng, upgrade_x__vikings, ..._abb_ha_01); a tier such as
# upgrade_melee_damage_iii must keep its _iii
CIV_SUFFIX = r'(__(vikings|scots)|_(vik|sco|abb|byz|chi|eng|fre|gol|hre|jin|jpn|lan|mac|mal|mon|ott|rus|sen|sul|tem|tug)(_ha_\w+)?|_ha_01)$'
DIR = ROOT / 'data/upcoming-civs'

def base(rid):
    rid = re.sub(CIV_SUFFIX, '', rid)
    return rid.replace('_control', '')

def catalog_values(rec, kind):
    out = {}
    cost = rec.get('cost') or {}
    for res in ('food', 'wood', 'gold', 'stone'):
        if res in cost: out[f'cost.{res}'] = cost[res]
    if kind == 'unit':
        out['trainTimeSeconds'] = rec.get('trainTimeSeconds'); out['hp'] = rec.get('hp')
        armor = rec.get('armor') or {}
        out['armor.melee'] = armor.get('Melee'); out['armor.ranged'] = armor.get('Ranged')
        if rec.get('speedEngineUnits') is not None: out['speed'] = round(rec['speedEngineUnits'] / 4, 4)
    elif kind in ('building', 'landmark'):
        out['buildTimeSeconds'] = rec.get('buildTimeSeconds'); out['hp'] = rec.get('hp')
    elif kind == 'technology':
        out['researchTimeSeconds'] = rec.get('researchTimeSeconds')
    return {k: v for k, v in out.items() if v is not None}

def main():
    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    by_base = collections.defaultdict(list)
    for section, kind in (('units', 'unit'), ('buildings', 'building'), ('technologies', 'technology')):
        for rec in catalog[section]: by_base[(kind, base(rec['id']))].append(rec)
    fills, stats = [], collections.Counter()
    for civ in ('vikings', 'scots'):
        for f in json.loads((DIR / f'fills/jeando-{civ}.json').read_text(encoding='utf-8'))['fills']:
            if not f.get('newItem'): continue  # unique objects have no 16.3 counterpart
            rid = f['note'].replace('record ', '')
            kind = 'building' if f['kind'] == 'landmark' else f['kind']
            recs = by_base.get((kind, base(rid)))
            if not recs: stats['no 16.3 counterpart'] += 1; continue
            shared = [r for r in recs if r['id'] == base(rid)]  # the standard record (upgrade_melee_damage_i) beats civ variants (_jpn, _sul)
            recs = shared or recs
            votes = collections.Counter(json.dumps(catalog_values(r, kind).get(f['field'])) for r in recs)
            votes.pop('null', None)
            if not votes: continue
            value = json.loads(votes.most_common(1)[0][0])
            agree = isinstance(value, (int, float)) and isinstance(f['value'], (int, float)) and abs(value - f['value']) <= 0.0051
            stats['equal' if agree else 'differs'] += 1
            fills.append({'civ': civ, 'kind': f['kind'], 'name': f['name'], 'field': f['field'], 'value': value,
                          'variant': f['variant'] if agree else ('installed 16.3 value' + (f', {f["variant"]}' if f['variant'] else '')),
                          'videoId': 'installed-catalog-16.3', 'timestamp': None, 'confidence': 'game-files-16.3',
                          'quote': f'{base(rid)}: {f["field"]} = {value} in {len(recs)} civilization copies of the installed 16.3 catalog ({votes.most_common(1)[0][1]} agree)',
                          'note': f'cross-check of record {rid}'})
    (DIR / 'fills/catalog-crosscheck.json').write_text(json.dumps({'transcribedBy': 'scripts/catalog_crosscheck_fills.py (installed 16.3 Attrib.sga catalog)', 'fills': fills},
                                                                 ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(fills), 'fills', dict(stats))

if __name__ == '__main__':
    main()
