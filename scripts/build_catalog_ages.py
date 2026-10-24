"""Age of every installed building and technology, for the Library's by-age grouping (data/catalog-ages.json).

Technologies: the installed game files' own requirement (`requirements` -> required_player_upgrade feudal_age /
castle_age / imperial_age, present=true); else data/tech_all.json (aoe4world) by exact attribute id, then by the same
attribute in another civilization. Age-up technologies (feudal_age ...) are their own category.
Buildings: the installed catalog records no age, so data/buildings_all.json (aoe4world) by exact attribute id, then
the same attribute in another civilization, then the building name; a building still without one gets the earliest
age of the technologies it researches (the Arsenal researches Feudal ranged techs, so it is available by Feudal).
Vikings/Scots preview records carry their own age (data/catalog-preview-17.0.json). The method is kept per id.
Usage: python -X utf8 scripts/build_catalog_ages.py
"""
import collections, json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
CIV_SUFFIX = r'_(abb|byz|chi|eng|fre|gol|hre|jin|jpn|lan|mac|mal|mon|ott|rus|sen|sul|tem|tug)(_ha_\w+)?$'
AGE_TECH = {'dark_age': 1, 'feudal_age': 2, 'castle_age': 3, 'imperial_age': 4}

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
    for b in cat['buildings']:
        rid = b['id']
        if rid in b_attrib: ages['buildings'][rid], method[rid] = b_attrib[rid], 'aoe4world attribute'
        elif b_base.get(re.sub(CIV_SUFFIX, '', rid)): ages['buildings'][rid], method[rid] = b_base[re.sub(CIV_SUFFIX, '', rid)].most_common(1)[0][0], 'aoe4world same attribute, other civilization'
        elif b_name.get(b['name']): ages['buildings'][rid], method[rid] = b_name[b['name']].most_common(1)[0][0], 'aoe4world building name'
        else:
            researched = [ages['technologies'][t] for t in b.get('researchableTechnologies') or [] if t in ages['technologies']]
            if researched: ages['buildings'][rid], method[rid] = min(researched), 'earliest technology it researches'
    out = {'source': 'installed game files (technology requirements) and data/buildings_all.json / tech_all.json (aoe4world), matched to data/game-catalog.json ids',
           **ages, 'method': method,
           'unmatched': sorted(r['id'] for k in ('buildings', 'technologies') for r in cat[k] if r['id'] not in ages[k] and method.get(r['id']) != 'age-up')}
    (ROOT / 'data/catalog-ages.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print({k: f"{len(ages[k])}/{len(cat[k])}" for k in ages}, dict(collections.Counter(method.values())), 'unmatched', len(out['unmatched']))

if __name__ == '__main__':
    main()
