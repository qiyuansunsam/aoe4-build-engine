"""Merge fill files into data/upcoming-civs/checklist.json.

Fill file (data/upcoming-civs/fills/*.json): {"transcribedBy": "...", "fills": [{"civ","kind","name","field","value",
"videoId" (or "sourceUrl"),"timestamp":"mm:ss","quote","confidence":"heard|read-on-screen|inferred|text|datamined",
"variant": null or tier/context, "newItem": description when the object is not in the text sources}]}
Every run rebuilds the checklist from the civ JSONs plus all fill files, so a corrected fill replaces its old value.
Rules: one source -> `single-source`; every source says the object has no such stat -> `n/a`; two independent sources agree -> `confirmed`; sources disagree -> the value backed by
at least two sources and by more sources than any other wins (`confirmed`, the rest kept in `dissent`), otherwise
`conflict` with all `candidates`. A source is a videoId / URL; the datamined jeandogaming.com records count as one.
Numbers match within 0.0051 (the game tooltip rounds 1.375 to 1.38). Free-text fields (effectText, classes,
bonusDamage) never conflict: every reading is kept and an English one is shown. Variant readings (tiers, upgrades)
sit in `variants` and never compete with the base value. Name matching is case-insensitive; unmatched fills are
reported, never guessed.
"""
import json, pathlib, re, collections, sys, unicodedata
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT / 'data/upcoming-civs'
sys.path.insert(0, str(ROOT / 'scripts'))
from build_upcoming_checklist import OPTIONAL, build_items, write_markdown, UNIT_FIELDS, BUILDING_FIELDS, TECH_FIELDS, LANDMARK_FIELDS, BONUS_FIELDS  # noqa: E402
KIND_FIELDS = {'unit': UNIT_FIELDS, 'building': BUILDING_FIELDS, 'technology': TECH_FIELDS, 'landmark': LANDMARK_FIELDS, 'bonus': BONUS_FIELDS}

def norm(v):
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        s = re.sub(r'\s*\(.*?\)\s*', ' ', v).strip()  # drop annotations such as "Dark (inferred from ...)"
        s = re.split(r'\s*[;/]\s*', s)[0].strip()      # keep the first alternative of "Barracks; also spawned by ..."
        if re.fullmatch(r'-?\d+(\.\d+)?', s): return float(s)
        return re.sub(r'\s+', ' ', s.lower())
    return v

TEXT_FIELDS = {'effectText', 'classes', 'bonusDamage'}
MULTI_FIELDS = {'building', 'effectValue', 'interval', 'cap'}

def fold(name):
    """Name key: accents, case, punctuation and plural ending ignored (Skåne Crossbowmen == Skâne Crossbowman)."""
    s = unicodedata.normalize('NFKD', name.replace('&', ' and ')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s); s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'(men|s)$', lambda m: 'man' if m.group(1) == 'men' else '', s)

def same(a, b, field=''):
    x, y = norm(a), norm(b)
    if isinstance(x, float) and isinstance(y, float):
        if field.endswith('Seconds') and (x % 1 or y % 1) and abs(x - y) <= 0.5: return True  # tooltip shows 19.5 s as 20s
        return abs(x - y) <= 0.0051
    return x == y

def english(v):
    return isinstance(v, str) and not re.search(r'[぀-鿿]', v)

def main():
    chk_path = DIR / 'checklist.json'; chk = json.loads(chk_path.read_text(encoding='utf-8'))
    chk['items'] = build_items(fresh=True)
    index = {}
    items_by_key = {(i['civ'], i['kind'], fold(i['name'])): i for i in chk['items']}
    for item in chk['items']:
        for f in item['fields']:
            index[(item['civ'], item['kind'], fold(item['name']), f['field'])] = (item, f)
    unmatched, applied = [], 0
    res_path = DIR / 'resolutions.json'
    rules = json.loads(res_path.read_text(encoding='utf-8')) if res_path.exists() else {}
    resolutions = rules.get('resolutions', [])
    aliases = {(a['civ'], a['kind'], fold(a['from'])): (a['to'], a.get('toKind', a['kind'])) for a in rules.get('aliases', [])}
    excluded = {(e['civ'], e['kind'], fold(e['name'])) for e in rules.get('exclude', [])}
    # datamined fills first, so a discovered object takes the game-file spelling when readers spell it differently
    paths = sorted((DIR / 'fills').glob('*.json'), key=lambda p: (not p.name.startswith('jeando-'), p.name))
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        for fill in data.get('fills', []):
            ident = (fill.get('civ'), fill.get('kind'), fold(str(fill.get('name', ''))))
            if ident in excluded: continue
            if ident in aliases:
                fill = {**fill, 'name': aliases[ident][0], 'kind': aliases[ident][1], 'nameAsRead': fill.get('name')}
                ident = (fill['civ'], fill['kind'], fold(fill['name']))
            for r in resolutions:  # reviewed re-routing: a reading that belongs to a different object (e.g. the other Town Center)
                if r.get('moveTo') and (r['civ'], r['kind'], fold(r['name']), r['field']) == (*ident[:2], fold(str(fill.get('name', ''))), fill.get('field'))                         and same(r['value'], fill.get('value')) and (not r.get('videoId') or r['videoId'] == fill.get('videoId')):
                    fill = {**fill, 'name': r['moveTo'], 'nameAsRead': fill.get('name'), 'resolution': r['reason']}
            key = (fill.get('civ'), fill.get('kind'), fold(str(fill.get('name', ''))), fill.get('field'))
            hit = index.get(key)
            if not hit and fill.get('civ') in ('vikings', 'scots') and fill.get('kind') in KIND_FIELDS and fill.get('field') in KIND_FIELDS[fill['kind']]:
                item = {'civ': fill['civ'], 'kind': fill['kind'], 'name': fill['name'], 'origin': 'discovered',
                        'description': fill.get('newItem') if isinstance(fill.get('newItem'), str) else f'first seen in {path.name}', 'wikiSource': None,
                        'fields': [{'field': fd, 'value': None, 'status': 'unknown', 'source': None, 'confidence': None, 'videoSources': []}
                                   for fd in KIND_FIELDS[fill['kind']] if fd not in OPTIONAL[fill['kind']]]}
                existing = items_by_key.get(key[:3])
                if existing: item = existing  # object exists, only this optional field is new
                else:
                    chk['items'].append(item); items_by_key[key[:3]] = item
                    for f in item['fields']: index[(item['civ'], item['kind'], fold(item['name']), f['field'])] = (item, f)
                if key not in index:
                    f = {'field': key[3], 'value': None, 'status': 'unknown', 'source': None, 'confidence': None, 'videoSources': []}
                    item['fields'].append(f); index[key] = (item, f)
                hit = index.get(key)
            if not hit:
                unmatched.append({**fill, 'file': path.name}); continue
            item, f = hit
            src = {'videoId': fill.get('videoId') or fill.get('sourceUrl'), 'timestamp': fill.get('timestamp'), 'quote': fill.get('quote'), 'value': fill.get('value'),
                   'confidence': fill.get('confidence'), 'transcribedBy': data.get('transcribedBy', path.stem)}
            for extra in ('frame', 'sourceUrl', 'note', 'verifiedBy'):
                if fill.get(extra): src[extra] = fill[extra]
            if fill.get('resolution'): src['resolution'] = fill['resolution']
            for r in resolutions:  # reviewed reclassification: this reading is a modified value, not the base
                if r.get('variant') and (r['civ'], r['kind'], fold(r['name']), r['field']) == key and same(r['value'], fill.get('value')) \
                        and (not r.get('videoId') or r['videoId'] == src['videoId']) and not fill.get('variant'):
                    fill = {**fill, 'variant': r['variant']}; src['resolution'] = r['reason']
            if fill.get('variant'):  # tier / upgraded reading: kept beside the base value, never compared with it
                src['variant'] = fill['variant']; f.setdefault('variants', [])
                if not any(s.get('videoId') == src['videoId'] and s.get('variant') == src['variant'] and norm(s.get('value')) == norm(src['value']) for s in f['variants']):
                    f['variants'].append(src); applied += 1
                continue
            f.setdefault('videoSources', [])
            if not any(s.get('videoId') == src['videoId'] and norm(s.get('value')) == norm(src['value']) for s in f['videoSources']):
                f['videoSources'].append(src); applied += 1
    # implicit zeros: a production tooltip lists every non-zero cost, so a frame that shows some costs of an object
    # and not this resource is a reading of 0 for it (a reader who skipped a cost shows up as a conflict, not hidden)
    for item in chk['items']:
        if item['kind'] == 'bonus': continue
        cost_fields = {f['field']: f for f in item['fields'] if f['field'].startswith('cost.')}
        seen = collections.defaultdict(dict)
        for fld, f in cost_fields.items():
            for s in f.get('videoSources') or []:
                if s.get('confidence') == 'read-on-screen': seen[s['videoId']][fld] = s
        for vid, got in seen.items():
            ref = next(iter(got.values()))
            for fld, f in cost_fields.items():
                if fld not in got and not any(s.get('videoId') == vid for s in f.get('videoSources') or []):
                    f.setdefault('videoSources', []).append({'videoId': vid, 'timestamp': ref.get('timestamp'), 'frame': ref.get('frame'), 'value': 0,
                        'confidence': 'implicit-zero', 'quote': f"tooltip lists {', '.join(sorted(got))} and no {fld.split('.')[1]} icon", 'transcribedBy': 'merge rule'})
    # resolve statuses
    counts = collections.Counter()
    for item in chk['items']:
        for f in item['fields']:
            srcs = f.get('videoSources') or []
            if not srcs: counts[f['status']] += 1; continue
            if all(str(s['value']).strip().lower() == 'n/a' for s in srcs):
                f['value'] = 'n/a'; f['status'] = 'n/a'; counts['n/a'] += 1; continue
            if f['field'] in TEXT_FIELDS:
                pick = next((s for s in srcs if s.get('confidence') == 'datamined'), None) or next((s for s in srcs if english(s['value'])), srcs[0])
                if f['status'] != 'known-text' or f.get('value') is None: f['value'] = pick['value']
                f['status'] = 'confirmed' if len({s.get('videoId') for s in srcs}) >= 2 else 'single-source'
                counts[f['status']] += 1; continue
            groups = []  # [representative value, set of sources]; numbers within tolerance share a group
            def put(value, source):
                for g in groups:
                    if same(g[0], value, f['field']): g[1].add(source); return
                groups.append([value, {source}])
            for s in sorted(srcs, key=lambda s: s.get('confidence') != 'datamined'):  # datamined first: its precision represents the group
                put(s['value'], s.get('videoId'))
            if f['status'] == 'known-text' and f.get('value') is not None and not str(f['value']).strip().lower().startswith('unknown'): put(f['value'], 'text')
            groups.sort(key=lambda g: -len(g[1]))
            if f['field'] in MULTI_FIELDS:  # several true answers (trained at two buildings; a tech with two numbers)
                f['textValue'] = f['value'] if f['status'] == 'known-text' else None; f['value'] = groups[0][0]  # best-supported reading; wiki wording kept
                f['status'] = 'confirmed' if len(groups[0][1]) >= 2 else 'single-source'
                if len(groups) > 1: f['alternatives'] = [g[0] for g in groups[1:]]
                counts[f['status']] += 1; continue
            if len(groups) == 1:
                if f['status'] == 'known-text' and not same(f['value'], groups[0][0], f['field']): f['textValue'] = f['value']
                f['value'] = groups[0][0]
                f['status'] = 'confirmed' if len(groups[0][1]) >= 2 else 'single-source'
            elif len(groups[0][1]) >= 2 and len(groups[0][1]) > len(groups[1][1]):
                f['value'] = groups[0][0]; f['status'] = 'confirmed'
                f['dissent'] = [{'value': s['value'], 'videoId': s.get('videoId'), 'timestamp': s.get('timestamp'), 'note': s.get('note')}
                                for s in srcs if not same(s['value'], groups[0][0], f['field'])]
            else:
                f['status'] = 'conflict'; f['candidates'] = [{'value': s['value'], 'videoId': s.get('videoId'), 'timestamp': s.get('timestamp')} for s in srcs]
            counts[f['status']] += 1
    chk['summary'] = {'items': len(chk['items']), 'fields': sum(len(i['fields']) for i in chk['items']), **{k: counts[k] for k in ('unknown', 'known-text', 'single-source', 'confirmed', 'conflict', 'n/a')}}
    chk['fillsApplied'] = applied; chk['unmatchedFills'] = unmatched
    chk_path.write_text(json.dumps(chk, ensure_ascii=False, indent=1), encoding='utf-8')
    write_markdown(chk['items'], chk.get('builtAt'))
    print(json.dumps({'applied': applied, 'unmatched': len(unmatched), **chk['summary']}))

if __name__ == '__main__':
    main()
