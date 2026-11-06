"""Re-check the theory rule packs (data/civ-rules/<civ>.json) against the installed 17.0.12260 files.

Two independent checks, both written to data/civ-rules/patch-17-recheck.json:

1. Evidence references. Every `catalog:<kind>/<id>#<field>`, `raw:<path>#<field path>` and `locale:<id>` reference
   found anywhere in a pack is resolved in the 16.3.11308 sources and in the 17.0.12260 sources and compared.
     catalog  16.3 = data/game-catalog.json at git revision OLD_CATALOG_REV, 17.0 = the working-tree catalog
     raw      decoded records (decoded-all/attrib/**.json) where the record was decoded, otherwise the raw unpack
              (Attrib-raw/attrib/**.rgd, compared byte for byte); a changed record is flattened and the cited field
              path is looked up among the changed leaves
     locale   LocaleEnglish/en/cardinal.en.ucs of each extract
2. Pack values. Every pack object that carries an installed record id is compared field by field (cost, build /
   train / research seconds, hp, population, speed) with that record in both catalogs. A value that equals the 16.3
   record and differs from the 17.0 record is stale; a value that differs from both is a deliberate pack value and is
   listed separately. For Vikings and Scots (packs written from datamined 17.0 records before release) the pack value
   is compared with the installed 17.0 record of the same id.

Usage: python -X utf8 scripts/verify_rule_packs_17.py [--old-catalog-rev REV]
"""
import argparse, json, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / 'data' / 'civ-rules'
OUT = PACKS / 'patch-17-recheck.json'
EXTRACTS = Path('C:/Users/Sam/projects/games/kb/aoe4/extract')
OLD_X, NEW_X = EXTRACTS / 'installed-24231237', EXTRACTS / 'installed-26400362'
OLD_CATALOG_REV = 'e9e7591'   # last revision whose data/game-catalog.json is the installed 16.3.11308 catalog
STANDARD = ('french', 'mongol', 'malian', 'japanese')
PREVIEW = ('scots', 'vikings')
RES = ('food', 'wood', 'gold', 'stone')

# What the 2026-11-06 re-check changed in the packs (every new value is the installed 17.0.12260 value named beside it).
APPLIED = [
    {'packs': ['french', 'mongol', 'malian', 'japanese'], 'value': 'extra Town Center build time', 'from': 150, 'to': 165,
     'source': 'catalog:buildings/building_town_center_<civ>#buildTimeSeconds'},
    {'packs': ['mongol'], 'value': 'packed capital Town Center speed (engine units)', 'from': 3, 'to': 3.6,
     'source': 'raw:ebps/races/mongol/buildings/building_town_center_capital_moving_mon#moving_ext/speed_scaling_table/default_speed'},
    {'packs': ['malian'], 'value': 'Grand Fulani Corral food per nearby cattle', 'from': '3 every 10 s (18 per minute)', 'to': '4 every 15 s (16 per minute)',
     'source': 'raw:statemodel_schema/civs/malian#float_properties/cattle_landmark_food_rate_mal.default, cattle_landmark_food_amount_mal.default'},
    {'packs': ['vikings'], 'value': 'Smithy / Pasture and Loom automatic research time', 'from': 270, 'to': 300,
     'source': 'raw:upgrade/races/vikings/buildings/upgrade_longhouse_smithy_vik#upgrade_bag/float_properties (research_time), upgrade_longhouse_pasture_loom_vik likewise'},
    {'packs': ['vikings'], 'value': 'Kongens Dør tithe, gold per Longhouse every 30 s', 'from': 10, 'to': 12.5,
     'source': 'raw:ebps/races/vikings/buildings/building_landmark_age3_kongens_cathedral_vik#ui_ext/help_text_formatter/formatter_arguments'},
    {'packs': ['scots'], 'value': 'trained Tacksman record id', 'from': 'unit_muster_tacksmen_sco (stand-in)', 'to': 'unit_handcannon_4_sco',
     'source': 'catalog:units/unit_handcannon_4_sco (160 food 90 gold, 35 s, 130 health: the values the pack already carried)'},
    {'packs': ['scots'], 'value': 'Border Reiver speed (tiles per second)', 'from': 1.688, 'to': 1.6875, 'source': 'catalog:units/unit_border_reiver_4_sco#speedEngineUnits (6.75 / 4)'},
    {'packs': ['scots', 'vikings'], 'value': 'starting sheep listed', 'from': 'not listed', 'to': '5 sheep', 'source': 'raw:army/standard_mode/normal_<civ>.rgd#army_bag/starting_units'},
]
# Pack values with no installed record in the decoded scope: they stay on their cited pre-release sources.
NOT_COMPARED = {
    'scots': ['Mustering Hall tier thresholds and cost reductions, muster charge counts (state trees and ability records outside the decoded scope)',
              'Abbey relic move cooldown 120 s', 'relic gold per minute and relic distance (map assumptions)', 'Stone of Destiny reach (placement assumption)',
              'Highland Cattle one cow per Berry Bush (footage)'],
    'vikings': ['saga goals and rewards (ability records outside the decoded scope)', 'Call Shield Maidens cost 800 food (ability record)',
                'Sacred Grove and Gullinn Temple Berserker intervals 100 s / 50 s (state tree)', 'Bondi at the Longhouse 25% slower is compared only through the Longhouse tooltip argument',
                'Farmstead field rate 1.5x is the installed tooltip argument 50; the record scalar gather_rate_food 1.833333 is untraced',
                'Northern Migration one recruit per Town Center in parallel (footage)', 'Jylland Knight gold on death, Living off the Land, Local Rituals (combat and healing values, not used by the plans)'],
    'french, mongol, malian, japanese': ['every cited reference resolved in both patches except one descriptive Japanese reference (see notMachineCheckable); state-tree behaviour the packs already list under unresolved[] is unchanged by this re-check'],
}

CATALOG_REF = re.compile(r'catalog:(units|buildings|technologies)/([A-Za-z0-9_]+)(?:#([A-Za-z0-9_.+]+))?')
RAW_REF = re.compile(r'raw:([A-Za-z0-9_\-/.]+)(?:#([^\s=|(),;:"]+))?')
LOCALE_REF = re.compile(r'locale:(\d+)')
FIELD_PAIRS = (('buildSeconds', 'buildTimeSeconds'), ('trainSeconds', 'trainTimeSeconds'), ('researchSeconds', 'researchTimeSeconds'),
               ('hp', 'hp'), ('pop', 'population'), ('speedEngineUnits', 'speedEngineUnits'))


def strings(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from strings(v, f'{path}/{k}')
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, f'{path}[{i}]')
    elif isinstance(node, str):
        yield path, node


def strip_source(node):
    if isinstance(node, dict):
        return {k: strip_source(v) for k, v in node.items() if k not in ('source', 'entitySource', 'sha256')}
    if isinstance(node, list):
        return [strip_source(v) for v in node]
    return node


def dig(record, field):
    cur = record
    for part in field.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return KeyError
    return cur


def walk(node, pos='', nam=''):
    """Decoded record ({key, value} lists) -> (positional path, named path, leaf) triples. Repeated keys are indexed by
    list position in the positional path (the form the packs cite: statemodel_float_property[14]); in the named path a
    statemodel property is indexed by its property id, so a property added in a new build does not shift the rest."""
    join = lambda base, name: f'{base}/{name}' if base else name
    if isinstance(node, dict) and set(node) == {'data'}:
        node = node['data']
    if isinstance(node, list) and node and all(isinstance(x, dict) and 'key' in x for x in node):
        counts = Counter(x['key'] for x in node)
        seen = Counter()
        for x in node:
            key, value = x['key'], x.get('value')
            ident = None
            if key.startswith('statemodel_') and isinstance(value, list):
                ident = next((c.get('value') for c in value if isinstance(c, dict) and str(c.get('key', '')).endswith('_property_id') and isinstance(c.get('value'), str)), None)
            by_pos = f'{key}[{seen[key]}]' if counts[key] > 1 else key
            seen[key] += 1
            yield from walk(value, join(pos, by_pos), join(nam, f'{key}[{ident}]' if ident else by_pos))
    elif isinstance(node, list):
        for i, x in enumerate(node):
            yield from walk(x, f'{pos}[{i}]', f'{nam}[{i}]')
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, join(pos, k), join(nam, k))
    else:
        yield pos, nam, node


def flatten(node):
    """{named path: leaf} and {positional path: named path}, both without the leading 'default/' variant."""
    cut = lambda k: re.sub(r'^default/', '', k)
    leaves, where = {}, {}
    for pos, nam, value in walk(node):
        leaves[cut(nam)] = value
        where[cut(pos)] = cut(nam)
    return leaves, where


class Extract:
    def __init__(self, root):
        self.root = root
        self.decoded = root / 'decoded-all' / 'attrib'
        self.raw = root / 'Attrib-raw' / 'attrib'
        self._stems = None
        self._ucs = None

    def stems(self):
        if self._stems is None:
            self._stems = {'json': defaultdict(list), 'rgd': defaultdict(list)}
            for p in self.decoded.rglob('*.json'):
                self._stems['json'][p.stem].append(p)
            if self.raw.exists():
                for p in self.raw.rglob('*.rgd'):
                    self._stems['rgd'][p.stem].append(p)
        return self._stems

    def find(self, ref_path):
        """(kind, file) for a raw: reference path, or (None, None)."""
        norm = re.sub(r'^(Attrib-raw/|attrib/)+', '', ref_path.strip('./'))
        norm = re.sub(r'\.(json|rgd)$', '', norm)
        top = norm.split('/')[0]
        stem = norm.split('/')[-1]
        for kind, base, ext in (('json', self.decoded, '.json'), ('rgd', self.raw, '.rgd')):
            direct = base / (norm + ext)
            if direct.exists():
                return kind, direct
            nested = base / norm / (stem + ext)   # ebps buildings live in a folder of their own name
            if nested.exists():
                return kind, nested
        for kind, base in (('json', self.decoded), ('rgd', self.raw)):
            hits = [p for p in self.stems()[kind].get(stem, []) if top in p.relative_to(base).parts]
            if len(hits) == 1:
                return kind, hits[0]
            exact = [p for p in hits if p.relative_to(base).with_suffix('').as_posix().endswith(norm)]
            if len(exact) == 1:
                return kind, exact[0]
        return None, None

    def ucs(self):
        if self._ucs is None:
            self._ucs = {}
            for line in (self.root / 'LocaleEnglish/en/cardinal.en.ucs').read_text(encoding='utf-16').splitlines():
                key, _, text = line.partition('\t')
                if key.strip().isdigit():
                    self._ucs[int(key)] = text
        return self._ucs


RGD_CLI = Path('C:/Users/Sam/projects/games/tools/aoe4-essence/AOEMods.Essence.CLI/bin/Release/net6.0/AOEMods.Essence.CLI.exe')
RGD_CACHE = ROOT / '.cache' / 'rgd-recheck'


def rgd_json(path, tag):
    """Decode one raw .rgd record with the Essence CLI (cached under .cache/rgd-recheck)."""
    import hashlib
    out = RGD_CACHE / tag / (hashlib.sha1(path.as_posix().encode()).hexdigest()[:16] + '-' + path.stem + '.json')
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run([str(RGD_CLI), 'rgd-decode', '-f', 'json', str(path), str(out)], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        except Exception:
            return None
    try:
        return json.loads(out.read_text(encoding='utf-8-sig'))
    except Exception:
        return None


def matcher(prefix, keys):
    """How a cited field path selects leaves of a flattened record. Packs cite fields four ways: the full path, a path
    with an elided head ('...required_near_entity/required_unit_type[1]'), a path tail ('gather_target[10]/gather_rate')
    and a statemodel property by name ('float_properties/cattle_ranch_food_rate.default')."""
    if not prefix:
        return lambda ks: list(ks)
    full = lambda ks: [k for k in ks if k == prefix or k.startswith(prefix + '/') or k.startswith(prefix + '[')]
    if full(keys):
        return full
    tail = prefix.split('...')[-1].strip('/.')
    if tail:
        inside = lambda ks: [k for k in ks if ('/' + tail + '/') in ('/' + k + '/') or ('/' + tail + '[') in ('/' + k) or k.endswith('/' + tail)]
        if inside(keys):
            return inside
    tokens = [x for x in re.split(r'[/.]', tail) if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{3,}', x)]
    named = lambda ks: [k for k in ks if any(f'[{x}]' in k for x in tokens)]
    if tokens and named(keys):
        return named
    return lambda ks: []


def field_prefix(field):
    f = re.sub(r'^default/', '', field or '')
    f = re.split(r'\[\d+\.\.\d+\]', f)[0]            # squad[0..11] -> squad
    f = re.sub(r'/\{.*$', '', f)                      # accepted_resources/{food,...}
    return f.rstrip('/.')


def compare_raw(old, new, ref_path, field):
    kind, old_file = old.find(ref_path)
    if not old_file:
        kind, new_file = new.find(ref_path)
        if new_file:   # Vikings and Scots records, the installed 17.0 villager and army records the packs now cite
            return 'changed', {'file': new_file.relative_to(new.decoded if kind == 'json' else new.raw).as_posix(), 'old': 'record absent from 16.3.11308', 'new': 'present (new in 17.0)'}
        return 'unchecked', 'record not found in either extract (reference path is descriptive, not a file path)'
    rel = old_file.relative_to(old.decoded if kind == 'json' else old.raw)
    new_file = (new.decoded if kind == 'json' else new.raw) / rel
    if not new_file.exists():
        return 'changed', {'file': rel.as_posix(), 'old': 'present', 'new': 'record absent from the 17.0.12260 extract'}
    if kind == 'rgd':
        if old_file.read_bytes() == new_file.read_bytes():
            return 'unchanged', None
        a, b = rgd_json(old_file, '16.3'), rgd_json(new_file, '17.0')   # bytes differ: decode both and compare the fields
        if a is None or b is None:
            return 'changed', {'file': 'Attrib-raw/attrib/' + rel.as_posix(), 'old': 'raw record bytes', 'new': 'raw record bytes differ and rgd-decode failed'}
    else:
        a, b = json.loads(old_file.read_text(encoding='utf-8')), json.loads(new_file.read_text(encoding='utf-8'))
    if a == b:
        return 'unchanged', None
    (fa, where), (fb, _) = flatten(a), flatten(b)
    diff = sorted(k for k in set(fa) | set(fb) if fa.get(k, KeyError) != fb.get(k, KeyError))
    prefix = field_prefix(field)
    under = matcher(prefix, set(fa) | set(fb))
    if prefix and not under(fa) and not under(fb):
        # a property cited by its 16.3 list position: find which named property that position was
        cited = {where[k] for k in matcher(prefix, set(where))(where)}
        if cited:
            under = lambda keys: [k for k in keys if k in cited]
    if prefix and not under(fa) and not under(fb):
        return 'changed', {'file': rel.as_posix(), 'old': 'cited field path not resolved', 'new': 'record changed',
                           'changedLeaves': [{'path': k, 'old': fa.get(k), 'new': fb.get(k)} for k in diff[:25]], 'changedLeafCount': len(diff)}
    hit = under(diff)
    if not hit:
        return 'unchanged', None   # the record changed elsewhere; the cited field is identical
    return 'changed', {'file': rel.as_posix(), 'changedLeaves': [{'path': k, 'old': fa.get(k), 'new': fb.get(k)} for k in hit[:25]], 'changedLeafCount': len(hit)}


def check_references(pack, old_cat, new_cat, old, new):
    refs = {}
    for where, text in strings(pack):
        for m in CATALOG_REF.finditer(text):
            refs.setdefault(('catalog', f'{m.group(1)}/{m.group(2)}', m.group(3) or ''), where)
        for m in RAW_REF.finditer(text):
            refs.setdefault(('raw', m.group(1).rstrip('.'), m.group(2) or ''), where)
        for m in LOCALE_REF.finditer(text):
            refs.setdefault(('locale', m.group(1), ''), where)
    result = {'checked': 0, 'unchanged': 0, 'changed': [], 'notMachineCheckable': []}
    for (kind, target, field), where in sorted(refs.items()):
        ref = f'{kind}:{target}' + (f'#{field}' if field else '')
        status, detail = 'unchanged', None
        if kind == 'catalog':
            group, ident = target.split('/')
            a, b = old_cat[group].get(ident), new_cat[group].get(ident)
            if a is None and b is None:
                status, detail = 'unchecked', 'record id in neither catalog'
            elif a is None or b is None:
                status, detail = 'changed', {'old': 'absent' if a is None else 'present', 'new': 'absent' if b is None else 'present'}
            else:
                fields = [f for f in field.split('+') if f] or [None]
                changes = []
                for f in fields:
                    va, vb = (strip_source(a), strip_source(b)) if f is None else (dig(a, f), dig(b, f))
                    if va is KeyError and vb is KeyError:
                        va, vb = strip_source(a), strip_source(b)   # descriptive field name: compare the whole record
                        f = f'{f} (not a record field; whole record compared)'
                    if va != vb:
                        if f is None or 'whole record' in str(f):
                            keys = sorted(k for k in set(va) | set(vb) if va.get(k) != vb.get(k))
                            changes.append({'field': f or 'whole record', 'changedKeys': keys, 'old': {k: va.get(k) for k in keys}, 'new': {k: vb.get(k) for k in keys}})
                        else:
                            changes.append({'field': f, 'old': None if va is KeyError else va, 'new': None if vb is KeyError else vb})
                if changes:
                    status, detail = 'changed', changes
        elif kind == 'raw':
            status, detail = compare_raw(old, new, target, field)
        else:
            a, b = old.ucs().get(int(target)), new.ucs().get(int(target))
            if a is None and b is None:
                status, detail = 'unchecked', 'locale id in neither locale file'
            elif a != b:
                status, detail = 'changed', {'old': a, 'new': b}
        if status == 'unchecked':
            result['notMachineCheckable'].append({'ref': ref, 'firstCitedAt': where, 'why': detail})
            continue
        result['checked'] += 1
        if status == 'unchanged':
            result['unchanged'] += 1
        else:
            result['changed'].append({'ref': ref, 'firstCitedAt': where, 'detail': detail})
    return result


def pack_objects(node, path=''):
    if isinstance(node, dict):
        if isinstance(node.get('id'), str):
            yield path, node
        for k, v in node.items():
            yield from pack_objects(v, f'{path}/{k}')
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from pack_objects(v, f'{path}[{i}]')


def record_values(record, obj):
    """The catalog values that correspond to the fields this pack object carries."""
    out = {}
    if isinstance(obj.get('cost'), dict):
        cost = record.get('cost') or {}
        keys = set(RES) | {k for k in obj['cost'] if k in cost}
        out['cost'] = {k: cost.get(k, 0) or 0 for k in sorted(keys) if (cost.get(k, 0) or 0) or (obj['cost'].get(k, 0) or 0)}
    for mine, theirs in FIELD_PAIRS:
        if mine in obj and isinstance(obj[mine], (int, float)) and theirs in record and isinstance(record[theirs], (int, float)):
            out[mine] = record[theirs]
    return out


def pack_values(obj):
    out = {}
    if isinstance(obj.get('cost'), dict):
        out['cost'] = {k: v for k, v in sorted(obj['cost'].items()) if isinstance(v, (int, float)) and v}
    for mine, _ in FIELD_PAIRS:
        if isinstance(obj.get(mine), (int, float)):
            out[mine] = obj[mine]
    return out


def same(a, b):
    if isinstance(a, dict) or isinstance(b, dict):
        a, b = a or {}, b or {}
        return all(abs((a.get(k, 0) or 0) - (b.get(k, 0) or 0)) < 1e-6 for k in set(a) | set(b))
    return abs(a - b) < 1e-6


def check_values(pack, old_by_id, new_by_id, preview):
    result = {'objectsWithInstalledId': 0, 'fieldsCompared': 0, 'equal17': 0, 'stale': [], 'packValueDiffersFromBothPatches': [], 'idsNotInstalled': []}
    missing = set()
    for where, obj in pack_objects(pack):
        # the record a pack object's cost and times describe: the extra Town Center for /townCenter (its id is the
        # capital), an explicit installedId, or the shared record behind a per-civilization stand-in id (x__scots)
        ident = obj.get('extraId') if where == '/townCenter' and obj.get('extraId') else obj.get('installedId') or obj['id']
        if ident not in new_by_id:
            ident = re.sub(r'__(scots|vikings)$', '', ident)
        new = new_by_id.get(ident)
        if new is None:
            if re.match(r'(unit|building|upgrade)_', ident):
                missing.add(obj['id'])
            continue
        result['objectsWithInstalledId'] += 1
        if isinstance(obj.get('recordCost'), dict):      # the engine charges nothing (cost {}), the record cost is kept beside it
            obj = dict(obj, cost=obj['recordCost'])
        mine, theirs = pack_values(obj), record_values(new, obj)
        old = record_values(old_by_id[ident], obj) if ident in old_by_id else {}
        mods = {m.get('property'): m.get('value') for m in new.get('modifiers') or []}
        if 'research_time' in mods and 'earlierAgeFaster' in obj:
            # a Longhouse attachment: `seconds` is its own research time, `researchSeconds` the automatic research it runs
            mine = {k: v for k, v in mine.items() if k != 'researchSeconds'}
            for field, pack_value, installed in (('seconds', obj.get('seconds'), new.get('researchTimeSeconds')),
                                                 ('researchSeconds (modifier research_time)', obj.get('researchSeconds'), mods['research_time']),
                                                 ('earlierAgeFaster (modifier research_time_reduction)', obj.get('earlierAgeFaster'), mods.get('research_time_reduction'))):
                if isinstance(pack_value, (int, float)) and isinstance(installed, (int, float)):
                    mine[field], theirs[field] = pack_value, installed
        if obj.get('autoResearch'):
            mine.pop('researchSeconds', None)             # researched by the attachment; its own record time is 0
        for field, value in mine.items():
            if field not in theirs:
                continue
            result['fieldsCompared'] += 1
            if same(value, theirs[field]):
                result['equal17'] += 1
                continue
            row = {'at': where, 'id': ident, 'name': new.get('name'), 'field': field, 'pack': value, 'installed17': theirs[field]}
            if not preview:
                row['installed16_3'] = old.get(field)
            if preview or (field in old and same(value, old[field])):
                result['stale'].append(row)
            else:
                result['packValueDiffersFromBothPatches'].append(row)
    result['idsNotInstalled'] = sorted(missing)
    return result


GATHER_FIELD = re.compile(r'resource_gatherer_ext/gather_types/gather_target(?:\[(\d+)\])?/(gather_rate|resource_carry_capacity|resource_sub_type/[$]PBGNAME)$')
PACK_SOURCE = {'tree': 'wood', 'farm': 'farm', 'herded_animal': 'sheep', 'berries': 'berries', 'hunted_animal': 'deer', 'hunted_animal_danger': 'boar',
               'gold': 'gold', 'stone': 'stone', 'fish': 'shore_fish'}
RACE = {'french': 'french', 'mongol': 'mongols', 'malian': 'malian', 'japanese': 'japanese', 'scots': 'scots', 'vikings': 'vikings'}


def check_start_and_gather(pack, civ, new):
    """Villager gather table, villager speed and start state against the installed 17.0 villager and army records."""
    rows, compared = [], 0

    def cmp(what, pack_value, installed, source):
        nonlocal compared
        compared += 1
        if pack_value != installed:
            rows.append({'what': what, 'pack': pack_value, 'installed17': installed, 'source': source})

    v = pack['villager']
    files = list(new.decoded.rglob(v['id'] + '.json'))
    if files:
        leaves, _ = flatten(json.loads(files[0].read_text(encoding='utf-8')))
        source = 'raw:' + files[0].relative_to(new.decoded).with_suffix('').as_posix()
        targets = defaultdict(dict)
        for key, value in leaves.items():
            m = GATHER_FIELD.match(key)
            if m:
                targets[int(m.group(1) or 0)][m.group(2).split('/')[0]] = value
        seen = {}
        for i, t in sorted(targets.items()):
            name = PACK_SOURCE.get(t.get('resource_sub_type'))
            if name and name not in seen:
                seen[name] = (i, t)
        for name, g in v['gather'].items():
            if not isinstance(g, dict) or g.get('rate') is None or name not in seen:
                continue
            i, t = seen[name]
            cmp(f'villager gather rate: {name}', g['rate'], t.get('gather_rate'), f'{source}#resource_gatherer_ext/gather_types/gather_target[{i}]/gather_rate')
            cmp(f'villager carry: {name}', g.get('carry'), t.get('resource_carry_capacity'), f'{source}#resource_gatherer_ext/gather_types/gather_target[{i}]/resource_carry_capacity')
        if 'speedEngineUnits' in v:
            cmp('villager speed (engine units)', v['speedEngineUnits'], leaves.get('moving_ext/speed_scaling_table/default_speed'), f'{source}#moving_ext/speed_scaling_table/default_speed')
    kind, army = new.find(f'army/standard_mode/normal_{RACE[civ]}')
    if army:
        record = rgd_json(army, '17.0') if kind == 'rgd' else json.loads(army.read_text(encoding='utf-8'))
        leaves, _ = flatten(record or {})
        source = f'raw:army/standard_mode/normal_{RACE[civ]}.rgd'
        for r in RES:
            cmp(f'starting {r}', pack['start']['resources'].get(r, 0), leaves.get(f'army_bag/resource_starting_amount/{r}', 0), f'{source}#army_bag/resource_starting_amount/{r}')
        units = Counter(value for key, value in leaves.items() if key.startswith('army_bag/starting_units/') and key.endswith('/$PBGNAME'))
        cmp('starting villagers', pack['start'].get('villagers'), sum(n for u, n in units.items() if 'villager' in u), f'{source}#army_bag/starting_units')
        packed = {u['id']: u['count'] for u in pack['start'].get('units', []) if 'villager' not in u['id']}   # villagers are compared above
        cmp('starting units other than villagers', dict(sorted(packed.items())), dict(sorted((u, n) for u, n in units.items() if 'villager' not in u)), f'{source}#army_bag/starting_units')
    return {'compared': compared, 'different': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old-catalog-rev', default=OLD_CATALOG_REV)
    args = ap.parse_args()
    old_text = subprocess.run(['git', 'show', f'{args.old_catalog_rev}:data/game-catalog.json'], cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
    old_catalog, new_catalog = json.loads(old_text), json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    if not old_catalog['provenance']['patch'].startswith('16.3') or not new_catalog['provenance']['patch'].startswith('17.0'):
        sys.exit(f"unexpected catalogs: {old_catalog['provenance']['patch']} / {new_catalog['provenance']['patch']}")
    index = lambda cat: {g: {r['id']: r for r in cat[g]} for g in ('units', 'buildings', 'technologies')}
    flat = lambda cat: {r['id']: r for g in ('units', 'buildings', 'technologies') for r in cat[g]}
    old, new = Extract(OLD_X), Extract(NEW_X)
    report = {'schemaVersion': 1, 'from': {'patch': old_catalog['provenance']['patch'], 'steamBuildId': old_catalog['provenance']['steamBuildId'], 'catalogRevision': args.old_catalog_rev},
              'to': {'patch': new_catalog['provenance']['patch'], 'steamBuildId': new_catalog['provenance']['steamBuildId']},
              'rawUnpack17': new.raw.exists(), 'packs': {}}
    for civ in STANDARD + PREVIEW:
        pack = json.loads((PACKS / f'{civ}.json').read_text(encoding='utf-8'))
        preview = civ in PREVIEW
        entry = {'packPatch': pack.get('patch')}
        entry['references'] = check_references(pack, index(old_catalog), index(new_catalog), old, new)
        entry['values'] = check_values(pack, flat(old_catalog), flat(new_catalog), preview)
        entry['startAndGather'] = check_start_and_gather(pack, civ, new)
        report['packs'][civ] = entry
        r, v, g = entry['references'], entry['values'], entry['startAndGather']
        print(f"{civ:9} refs {r['checked']} checked, {r['unchanged']} unchanged, {len(r['changed'])} changed, {len(r['notMachineCheckable'])} not machine-checkable | "
              f"values {v['fieldsCompared']} compared, {v['equal17']} equal to 17.0, {len(v['stale'])} stale, {len(v['packValueDiffersFromBothPatches'])} differ from both, "
              f"{len(v['idsNotInstalled'])} ids not installed | start and gather {g['compared']} compared, {len(g['different'])} different")
    report['applied'] = APPLIED
    report['notCompared'] = NOT_COMPARED
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('->', OUT)


if __name__ == '__main__':
    main()
