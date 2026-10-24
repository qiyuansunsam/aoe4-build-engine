"""Build the Vikings/Scots stat checklist from the collected wiki/official data.

Reads data/upcoming-civs/{vikings,scots}.json and writes data/upcoming-civs/checklist.json plus
CHECKLIST.md. Every object (unit, building, technology, landmark, bonus) gets the stat fields a build
crafter needs; a field is `known` when the text sources already supply a number, otherwise `unknown`.
Transcript/video readers fill `unknown` fields in place (value, source, timestamp, transcribedBy).
Re-running keeps filled values: existing checklist entries are merged by (civ, kind, name, field).
"""
import json, pathlib, re, datetime
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'
UNIT_FIELDS = ['cost.food', 'cost.wood', 'cost.gold', 'cost.stone', 'hp', 'armor.melee', 'armor.ranged', 'damage', 'attackSpeed', 'bonusDamage', 'range', 'speed', 'population', 'trainTimeSeconds', 'age', 'building', 'classes']
BUILDING_FIELDS = ['cost.food', 'cost.wood', 'cost.gold', 'cost.stone', 'hp', 'buildTimeSeconds', 'population', 'age', 'garrison', 'armor.ranged', 'damage', 'attackSpeed', 'range', 'bonusDamage']
TECH_FIELDS = ['cost.food', 'cost.wood', 'cost.gold', 'cost.stone', 'researchTimeSeconds', 'age', 'building', 'effectValue', 'effectText']
LANDMARK_FIELDS = ['cost.food', 'cost.wood', 'cost.gold', 'cost.stone', 'buildTimeSeconds', 'hp', 'age', 'effectValue', 'productionTimeSeconds', 'region', 'effectText', 'population', 'garrison', 'armor.ranged', 'damage', 'attackSpeed', 'range', 'bonusDamage']
BONUS_FIELDS = ['effectValue', 'interval', 'cap', 'effectText']

# Optional fields exist on an object only when a source supplies them (a Mill has no attack, a Vikings landmark no
# region); required fields always exist, so `unknown` counts only what a build or combat calculation needs.
OPTIONAL = {'unit': {'bonusDamage', 'population'},
            'building': {'population', 'garrison', 'armor.ranged', 'damage', 'attackSpeed', 'range', 'bonusDamage'},
            'technology': {'effectValue'},
            'landmark': {'productionTimeSeconds', 'effectValue', 'region', 'population', 'garrison', 'armor.ranged', 'damage', 'attackSpeed', 'range', 'bonusDamage'},
            'bonus': {'effectValue', 'interval', 'cap'}}

def get(obj, path):
    cur = obj
    for part in path.split('.'):
        if not isinstance(cur, dict): return None
        cur = cur.get(part)
    if isinstance(cur, str) and re.fullmatch(r'-?\d+(\.\d+)?', cur.strip()): return float(cur)
    return cur

def known(v):
    return v is not None and v != '' and not (isinstance(v, str) and v.lower() in ('unknown', 'null', 'n/a'))

def build_items(fresh=False):
    """Checklist items from the civ JSONs. fresh=True ignores the existing checklist (merge_checklist_fills.py
    rebuilds every source from the fill files, so nothing stale survives a corrected fill)."""
    out_path = DIR / 'checklist.json'
    previous, discovered = {}, []
    if out_path.exists() and not fresh:
        for item in json.loads(out_path.read_text(encoding='utf-8')).get('items', []):
            if item.get('origin') == 'discovered': discovered.append(item)
            for f in item['fields']:
                previous[(item['civ'], item['kind'], item['name'], f['field'])] = f
    items = []
    for civ in ('vikings', 'scots'):
        d = json.loads((DIR / f'{civ}.json').read_text(encoding='utf-8'))
        groups = [('unit', d.get('uniqueUnits', []), UNIT_FIELDS), ('building', d.get('uniqueBuildings', []), BUILDING_FIELDS),
                  ('technology', d.get('uniqueTechnologies', []), TECH_FIELDS), ('landmark', d.get('landmarks', []), LANDMARK_FIELDS),
                  ('bonus', d.get('bonuses', []), BONUS_FIELDS)]
        for kind, rows, fields in groups:
            for row in rows:
                name = row.get('name') or row.get('title') or 'Unnamed'
                entry = {'civ': civ, 'kind': kind, 'name': name, 'description': row.get('effect') or row.get('text') or row.get('notes') or '',
                         'wikiSource': row.get('source'), 'fields': []}
                for field in fields:
                    alias = {'buildTimeSeconds': 'buildTime', 'trainTimeSeconds': 'trainTime', 'researchTimeSeconds': 'researchTime', 'armor.melee': 'armor.Melee', 'armor.ranged': 'armor.Ranged'}
                    value = get(row, field)
                    if not known(value) and field in alias: value = get(row, alias[field])
                    prev = previous.get((civ, kind, name, field))
                    if field in OPTIONAL[kind] and not known(value) and not prev: continue
                    if prev and prev.get('status') in ('video', 'confirmed') and known(prev.get('value')):
                        entry['fields'].append(prev); continue
                    entry['fields'].append({'field': field, 'value': value if known(value) else None,
                                            'status': 'known-text' if known(value) else 'unknown',
                                            'source': row.get('source') if known(value) else None, 'confidence': row.get('confidence') if known(value) else None,
                                            'videoSources': prev.get('videoSources', []) if prev else []})
                    if prev and prev.get('variants'): entry['fields'][-1]['variants'] = prev['variants']
                items.append(entry)
    have = {(i['civ'], i['kind'], i['name'].lower()) for i in items}
    items += [i for i in discovered if (i['civ'], i['kind'], i['name'].lower()) not in have]  # added by merge_checklist_fills.py
    return items

def main():
    out_path = DIR / 'checklist.json'
    items = build_items()
    total = sum(len(i['fields']) for i in items)
    unknown = sum(1 for i in items for f in i['fields'] if f['status'] == 'unknown')
    result = {'schemaVersion': 1, 'builtAt': datetime.date.today().isoformat(), 'civilizations': ['vikings', 'scots'],
              'fieldStatuses': ['unknown', 'known-text', 'single-source', 'confirmed', 'conflict', 'n/a'],
              'summary': {'items': len(items), 'fields': total, 'unknown': unknown, 'known': total - unknown}, 'items': items}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    write_markdown(items, result['builtAt'])
    print(json.dumps(result['summary']))

def fmt(f):
    s = f'{f["field"]}={f["value"]}'
    if f['status'] == 'conflict': s += ' (conflict: ' + ' vs '.join(sorted({str(c['value']) for c in f.get('candidates', [])})) + ')'
    elif f['status'] == 'confirmed': s += ' ✓'
    return s

def write_markdown(items, built_at):
    total = sum(len(i['fields']) for i in items)
    counts = {s: sum(1 for i in items for f in i['fields'] if f['status'] == s) for s in ('unknown', 'known-text', 'single-source', 'confirmed', 'conflict', 'n/a')}
    lines = ['# Vikings and Scots stat checklist', '', f'Built {built_at} from `data/upcoming-civs/*.json` plus merged fills. {len(items)} objects, {total} fields: '
             + ', '.join(f'{v} {k}' for k, v in counts.items()) + '.',
             'Status: `unknown` = no source yet; `known-text` = official/wiki text only; `single-source` = one source (a video frame or transcript, or the datamined records); `confirmed` (✓) = two or more independent sources agree (a disagreeing minority is kept as dissent); `conflict` = sources disagree with no majority; `n/a` = the object has no such stat (e.g. a boat with no weapon).',
             'Values are the base unit (earliest tier, no upgrades). Tier and upgrade readings are in `variants` in checklist.json. Items marked * were discovered in footage, not in the text sources.', '']
    for civ in ('vikings', 'scots'):
        lines += [f'## {civ.title()}', '']
        for kind in ('unit', 'building', 'technology', 'landmark', 'bonus'):
            rows = [i for i in items if i['civ'] == civ and i['kind'] == kind]
            if not rows: continue
            lines += [f'### {({"technology":"Technologies","bonus":"Bonuses"}).get(kind, kind.title()+"s")}', '', '| Name | Fields known | Unknown fields |', '|---|---|---|']
            for i in rows:
                k = [fmt(f) for f in i['fields'] if f['status'] != 'unknown']
                u = [f['field'] for f in i['fields'] if f['status'] == 'unknown']
                star = '*' if i.get('origin') == 'discovered' else ''
                lines.append(f'| {i["name"]}{star} | {", ".join(k) or "—"} | {", ".join(u) or "—"} |')
            lines.append('')
    (DIR / 'CHECKLIST.md').write_text('\n'.join(lines), encoding='utf-8')

if __name__ == '__main__':
    main()
