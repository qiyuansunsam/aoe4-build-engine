"""Age of every installed building and technology, for the Library's by-age grouping (data/catalog-ages.json).

Technologies: the installed game files' own requirement (`requirements` -> required_player_upgrade feudal_age /
castle_age / imperial_age, present=true); else data/tech_all.json (aoe4world) by exact attribute id, then by the same
attribute in another civilization. Age-up technologies (feudal_age ...) are their own category.
Buildings: the installed building's own `requirement_ext` (decoded ebps under the catalog's decodedRoot): positive
feudal/castle/imperial_age requirements, alternatives inside required_any_in_list taking the lowest age (the Town
Center needs feudal_age or the fast_expand game-mode upgrade, so Feudal), negations ignored. aoe4world lists every
Town Center as Dark Age because the capital one exists from the start. A building whose requirements name no age falls
back to data/buildings_all.json (aoe4world) by exact attribute id, then the same attribute in another civilization,
then the building name, then the earliest age of the technologies it researches.
Vikings/Scots preview records carry their own age (data/catalog-preview-17.0.json); it is overridden only where every
installed civilization copy of the same standard building has the same requirement age and the preview disagrees
(the datamined ageName says Dark Age for the Town Center, like aoe4world). The method is kept per id.
Usage: python -X utf8 scripts/build_catalog_ages.py
"""
import collections, json, pathlib, re
from inspect_rgd import load
ROOT = pathlib.Path(__file__).resolve().parents[1]
CIV_SUFFIX = r'_(abb|byz|chi|eng|fre|gol|hre|jin|jpn|lan|mac|mal|mon|ott|rus|sen|sul|tem|tug|vik|sco)(_ha_\w+)?$'
AGE_TECH = {'dark_age': 1, 'feudal_age': 2, 'castle_age': 3, 'imperial_age': 4}

def as_list(v):
    return v if isinstance(v, list) else [v] if v else []

def requirement_age(table):
    """Lowest age that satisfies an installed requirement table (0 when it names none)."""
    if not isinstance(table, dict): return 0
    need = 0
    for kind, items in table.items():
        for it in as_list(items):
            if not isinstance(it, dict): continue
            if kind == 'required_player_upgrade':
                name = (it.get('upgrade_name') or {}).get('$PBGNAME')
                if it.get('is_present') and name in AGE_TECH: need = max(need, AGE_TECH[name])
            elif kind == 'required_all_in_list':
                need = max(need, requirement_age(it.get('requirements')))
            elif kind == 'required_any_in_list':
                alts = [a for k, vs in (it.get('requirements') or {}).items() for v in as_list(vs) if (a := requirement_age({k: v}))]
                if alts: need = max(need, min(alts))
    return need

def base_id(rid):
    return re.sub(CIV_SUFFIX, '', rid).replace('_control', '')

def aoe4world(path):
    rows = json.loads((ROOT / path).read_text(encoding='utf-8'))
    rows = rows['data'] if isinstance(rows, dict) else rows
    by_attrib, by_base, by_name = {}, collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for r in rows:
        if not r.get('age'): continue
        if r.get('attribName'):
            by_attrib[r['attribName']] = r['age']; by_base[re.sub(CIV_SUFFIX, '', r['attribName'])][r['age']] += 1
        by_name[r['name']][r['age']] += 1
    return by_attrib, by_base, by_name

def main():
    cat = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    ages, method = {'buildings': {}, 'technologies': {}}, {}
    t_attrib, t_base, _ = aoe4world('data/tech_all.json')
    for t in cat['technologies']:
        rid = t['id']
        if re.match(r'^(dark|feudal|castle|imperial)_age', rid): method[rid] = 'age-up'; continue
        req = [AGE_TECH[re.sub(CIV_SUFFIX, '', q['id'])] for q in t.get('requirements') or []
               if q.get('present') and re.sub(CIV_SUFFIX, '', q.get('id', '')) in AGE_TECH]
        if req: ages['technologies'][rid], method[rid] = max(req), 'installed requirement'
        elif rid in t_attrib: ages['technologies'][rid], method[rid] = t_attrib[rid], 'aoe4world attribute'
        elif t_base.get(re.sub(CIV_SUFFIX, '', rid)): ages['technologies'][rid], method[rid] = t_base[re.sub(CIV_SUFFIX, '', rid)].most_common(1)[0][0], 'aoe4world same attribute, other civilization'
    b_attrib, b_base, b_name = aoe4world('data/buildings_all.json')
    decoded = pathlib.Path(cat['provenance'].get('decodedRoot') or '')
    for b in cat['buildings']:
        rid = b['id']
        raw = decoded / (b['source']['asset'][:-4] + '.json')
        req = requirement_age(load(raw).get('requirement_ext', {}).get('requirement_table')) if raw.is_file() else 0
        if req: ages['buildings'][rid], method[rid] = req, 'installed requirement'
        elif rid in b_attrib: ages['buildings'][rid], method[rid] = b_attrib[rid], 'aoe4world attribute'
        elif b_base.get(re.sub(CIV_SUFFIX, '', rid)): ages['buildings'][rid], method[rid] = b_base[re.sub(CIV_SUFFIX, '', rid)].most_common(1)[0][0], 'aoe4world same attribute, other civilization'
        elif b_name.get(b['name']): ages['buildings'][rid], method[rid] = b_name[b['name']].most_common(1)[0][0], 'aoe4world building name'
        else:
            researched = [ages['technologies'][t] for t in b.get('researchableTechnologies') or [] if t in ages['technologies']]
            if researched: ages['buildings'][rid], method[rid] = min(researched), 'earliest technology it researches'
    installed = collections.defaultdict(set)
    for b in cat['buildings']:
        if method.get(b['id']) == 'installed requirement' and 'landmark' not in b['id']: installed[base_id(b['id'])].add(ages['buildings'][b['id']])
    preview = json.loads((ROOT / 'data/catalog-preview-17.0.json').read_text(encoding='utf-8'))
    for b in preview['buildings']:
        same = installed.get(base_id(b['id']))
        if same and len(same) == 1 and b.get('age') != next(iter(same)):
            ages['buildings'][b['id']] = next(iter(same))
            method[b['id']] = f"installed requirement of {base_id(b['id'])} in every 16.3 civilization (preview record said {b.get('age')})"
    out = {'source': 'installed game files (building and technology requirements) and data/buildings_all.json / tech_all.json (aoe4world), matched to data/game-catalog.json ids',
           **ages, 'method': method,
           'unmatched': sorted(r['id'] for k in ('buildings', 'technologies') for r in cat[k] if r['id'] not in ages[k] and method.get(r['id']) != 'age-up')}
    (ROOT / 'data/catalog-ages.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print({k: f"{len(ages[k])}/{len(cat[k])}" for k in ages}, dict(collections.Counter(method.values())), 'unmatched', len(out['unmatched']))

if __name__ == '__main__':
    main()
