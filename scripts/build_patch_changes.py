"""Build data/patch-changes.json: what changed between two installed game builds, read from the game files themselves.

Both sides are catalogs normalized from an installed Attrib.sga by scripts/populate_game_catalog.py:
  before  the catalog committed for the previous installed patch (git blob BEFORE_BLOB, 16.3.11308, Steam build 24231237)
  after   data/game-catalog.json (the installed patch)
Nothing here comes from patch notes. A change is a field of a record that holds a different value in the two
catalogs: health, cost, train / build / research time, armor, speed, population, a weapon's damage, range, attack
timings and bonus damage, what a building trains or researches, an upgrade's modifier values, and tooltip values or
text. Renamed target classes whose bonus value did not move are not changes. Records that exist only in the newer
catalog are listed as new.

Output (window.PATCH_CHANGES):
  records   {record id: [change]}                      every changed record, for its Library page
  added     [record id]                                records new in the newer build
  families  [{civ, kind, name, id, ids, changes}]      tiers of one unit merged ("190/230/270 -> 200/240/280"), for
                                                       the overview on top of the Library
  shared    [{kind, name, civs, id, changes}]          a family changed identically in many civilizations
change = {l: label, o: before, n: after} with o or n null when the value did not exist on that side.

Usage: python -X utf8 scripts/build_patch_changes.py
"""
import json, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEFORE_BLOB = 'e9e7591:data/game-catalog.json'
OUT = ROOT / 'data/patch-changes.json'
KINDS = ('units', 'buildings', 'technologies')
TIER_PREFIX = re.compile(r'^(?:Early|Hardened|Veteran|Elite|Vanguard) ')
SHARED_MIN = 8       # a family changed identically in this many civilizations is reported once as shared
RES = ('food', 'wood', 'gold', 'stone')


def pretty(key):
    return re.sub(r'\s+', ' ', str(key).replace('_', ' ')).strip().capitalize()


def num(v):
    if isinstance(v, float):
        v = round(v, 4)
        return int(v) if v == int(v) else v
    return v


def weapon_changes(old, new):
    out, seen = [], set()
    before = {w['id']: w for w in old.get('weapon') or []}

    def add(label, o, n):
        key = (label, json.dumps(o), json.dumps(n))
        if o != n and key not in seen:
            seen.add(key)
            out.append({'l': label, 'o': o, 'n': n})

    for w in new.get('weapon') or []:
        b = before.get(w['id'])
        if not b:
            continue
        name = w.get('name') or pretty(w['id'])

        def damage(x):
            lo, hi = num(x.get('damageMin')), num(x.get('damageMax'))
            return lo if lo == hi else f'{lo}-{hi}'
        add(f'{name} damage', damage(b), damage(w))
        add(f'{name} range', num((b.get('range') or {}).get('max')), num((w.get('range') or {}).get('max')))
        for field, label in (('windupSeconds', 'wind-up'), ('winddownSeconds', 'wind-down')):
            add(f'{name} {label} (s)', num(b.get(field)), num(w.get(field)))
        cb, cw = b.get('cooldownSeconds') or {}, w.get('cooldownSeconds') or {}
        add(f'{name} cooldown (s)', num(cb.get('max')), num(cw.get('max')))
        bo = {x['unit_type']: num(x['base_damage_modifier']) for x in b.get('bonuses') or []}
        bn = {x['unit_type']: num(x['base_damage_modifier']) for x in w.get('bonuses') or []}
        gone = {k: v for k, v in bo.items() if k not in bn}
        came = {k: v for k, v in bn.items() if k not in bo}
        for k in list(gone):                       # a class renamed with the same bonus is not a change
            match = next((c for c, v in came.items() if v == gone[k]), None)
            if match:
                del gone[k], came[match]
        for k in bo:
            if k in bn:
                add(f'{name} bonus vs {pretty(k).lower()}', bo[k], bn[k])
        for k, v in gone.items():
            add(f'{name} bonus vs {pretty(k).lower()}', v, None)
        for k, v in came.items():
            add(f'{name} bonus vs {pretty(k).lower()}', None, v)
    return out


def tooltip_changes(old, new):
    """Tooltip arguments and text. A template with one argument type is filled positionally so the line reads in context."""
    out = []
    ta, tb = old.get('descriptionTemplate') or '', new.get('descriptionTemplate') or ''
    aa, ab = old.get('descriptionArguments') or {}, new.get('descriptionArguments') or {}

    def fill(template, args):
        if len(args) != 1:
            return None
        values = next(iter(args.values()))
        values = values if isinstance(values, list) else [values]
        text = template
        for i, v in enumerate(values, 1):
            text = text.replace(f'%{i}%', str(num(v)))
        return text.replace('%%', '%')

    if ta or tb:
        fa, fb = fill(ta, aa), fill(tb, ab)
        if fa is not None and fb is not None:
            if fa != fb:
                sa, sb = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', fa) if s.strip()], [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', fb) if s.strip()]
                o = ' '.join(s for s in sa if s not in sb) or None
                n = ' '.join(s for s in sb if s not in sa) or None
                out.append({'l': 'Tooltip', 'o': o, 'n': n, 't': 1})
        elif aa != ab or ta != tb:
            flat = lambda a: [num(v) for vs in a.values() for v in (vs if isinstance(vs, list) else [vs]) if not isinstance(v, (dict, str))]
            va, vb = flat(aa), flat(ab)
            if va != vb:
                out.append({'l': 'Tooltip values', 'o': '/'.join(map(str, va)) or None, 'n': '/'.join(map(str, vb)) or None})
            elif ta != tb:
                out.append({'l': 'Tooltip', 'o': ta.replace('\n', ' ').strip() or None, 'n': tb.replace('\n', ' ').strip() or None, 't': 1})
    elif (old.get('description') or '') != (new.get('description') or ''):
        la, lb = [s.strip() for s in (old.get('description') or '').split('\n') if s.strip()], [s.strip() for s in (new.get('description') or '').split('\n') if s.strip()]
        o = ' '.join(s for s in la if s not in lb) or None
        n = ' '.join(s for s in lb if s not in la) or None
        if o or n:
            out.append({'l': 'Tooltip', 'o': o, 'n': n, 't': 1})
    return out


def record_changes(kind, old, new, names):
    out = []

    def add(label, o, n):
        o, n = num(o), num(n)
        if o != n:
            out.append({'l': label, 'o': o, 'n': n})

    add('Health', old.get('hp'), new.get('hp'))
    co, cn = old.get('displayCost') or old.get('cost') or {}, new.get('displayCost') or new.get('cost') or {}
    labels = {**(old.get('costLabels') or {}), **(new.get('costLabels') or {})}
    for res in sorted(set(co) | set(cn), key=lambda r: (RES.index(r) if r in RES else 9, r)):
        if (co.get(res) or 0) != (cn.get(res) or 0):
            add(f'Cost · {str(labels.get(res) or res).lower()}', co.get(res) or 0, cn.get(res) or 0)
    for field, label in (('trainTimeSeconds', 'Train time (s)'), ('buildTimeSeconds', 'Build time (s)'), ('researchTimeSeconds', 'Research time (s)'),
                         ('speedEngineUnits', 'Speed'), ('population', 'Population')):
        add(label, old.get(field), new.get(field))
    for channel in ('Melee', 'Ranged', 'Fire'):
        add(f'{channel} armor', (old.get('armor') or {}).get(channel), (new.get('armor') or {}).get(channel))
    if kind == 'units':
        out += weapon_changes(old, new)
    if kind == 'buildings':
        for field, label in (('trainableUnits', 'Trains'), ('researchableTechnologies', 'Researches')):
            # compared by name: a record that only changed its id still trains or researches the same thing
            a = list(dict.fromkeys(names.get(x) or pretty(x) for x in old.get(field) or [] if x))
            b = list(dict.fromkeys(names.get(x) or pretty(x) for x in new.get(field) or [] if x))
            came, gone = [x for x in b if x not in a], [x for x in a if x not in b]
            if came:
                out.append({'l': f'{label} (added)', 'o': None, 'n': ', '.join(came)})
            if gone:
                out.append({'l': f'{label} (removed)', 'o': ', '.join(gone), 'n': None})
    if kind == 'technologies':
        mo = {m.get('property'): m.get('value') for m in old.get('modifiers') or [] if not isinstance(m.get('value'), (dict, list))}
        mn = {m.get('property'): m.get('value') for m in new.get('modifiers') or [] if not isinstance(m.get('value'), (dict, list))}
        for prop in sorted(set(mo) | set(mn), key=str):
            add(f'Effect · {pretty(prop).lower()}', mo.get(prop), mn.get(prop))
    out += tooltip_changes(old, new)
    return out


def main():
    blob = subprocess.run(['git', '-C', str(ROOT), 'show', BEFORE_BLOB], capture_output=True)
    if blob.returncode:
        sys.exit(blob.stderr.decode('utf-8', 'replace'))
    before = json.loads(blob.stdout.decode('utf-8'))
    after = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    if before['provenance']['patch'] == after['provenance']['patch']:
        sys.exit('before and after are the same patch')
    names = {r['id']: r['name'] for k in KINDS for r in after[k]} | {r['id']: r['name'] for k in KINDS for r in before[k]}
    civs = {c['id'] for c in after['civilizations']}

    records, added, kind_of, record_of = {}, [], {}, {}
    for kind in KINDS:
        old = {r['id']: r for r in before[kind]}
        for r in after[kind]:
            kind_of[r['id']], record_of[r['id']] = kind, r
            if r['id'] not in old:
                added.append(r['id'])
                continue
            changes = record_changes(kind, old[r['id']], r, names)
            if changes:
                records[r['id']] = changes

    def tier(r):
        m = re.search(r'_(\d)(?:_|$)', r['id'])
        return (r.get('age') or (int(m.group(1)) if m else 9), r['id'])

    grouped = defaultdict(list)
    for rid in records:
        r = record_of[rid]
        grouped[(r['civilization'], kind_of[rid], TIER_PREFIX.sub('', r['name']))].append(r)
    families = []
    for (civ, kind, name), members in grouped.items():
        members.sort(key=tier)
        by_label = defaultdict(list)
        for r in members:
            for c in records[r['id']]:
                by_label[c['l']].append(c)
        changes = []
        for label, cs in by_label.items():
            pairs = list(dict.fromkeys((json.dumps(c['o']), json.dumps(c['n'])) for c in cs))
            if len(pairs) == 1 or cs[0].get('t'):
                changes.append(cs[0])
            else:
                show = lambda v: '?' if v is None else str(v)
                steps = [(json.loads(o), json.loads(n)) for o, n in pairs]     # one step per distinct tier value, in tier order
                changes.append({'l': label, 'o': '/'.join(show(o) for o, _ in steps), 'n': '/'.join(show(n) for _, n in steps)})
        families.append({'civ': civ, 'kind': kind[:-1] if kind != 'technologies' else 'technology', 'name': name, 'id': members[0]['id'],
                         'ids': [r['id'] for r in members], 'changes': changes})

    same = defaultdict(list)
    for f in families:
        same[(f['kind'], f['name'], json.dumps(f['changes'], sort_keys=True))].append(f)
    shared, in_shared = [], set()
    for (kind, name, _), fs in same.items():
        owners = sorted({f['civ'] for f in fs if f['civ'] in civs})
        if len(owners) >= SHARED_MIN:
            rep = next((f for f in fs if f['civ'] == 'english'), fs[0])
            shared.append({'kind': kind, 'name': name, 'civs': owners, 'id': rep['id'], 'changes': rep['changes']})
            in_shared |= {id(f) for f in fs}
    for f in families:
        if id(f) in in_shared:
            f['shared'] = True
    order = {'unit': 0, 'building': 1, 'technology': 2}
    families.sort(key=lambda f: (f['civ'], order[f['kind']], f['name']))
    shared.sort(key=lambda s: (order[s['kind']], s['name']))

    new_counts = defaultdict(Counter)
    for rid in added:
        new_counts[record_of[rid]['civilization']][kind_of[rid]] += 1
    result = {
        'schemaVersion': 1,
        'from': {'patch': before['provenance']['patch'], 'steamBuildId': before['provenance']['steamBuildId'], 'source': 'git ' + BEFORE_BLOB},
        'to': {'patch': after['provenance']['patch'], 'steamBuildId': after['provenance']['steamBuildId'], 'source': 'data/game-catalog.json'},
        'counts': {'recordsChanged': len(records), 'recordsAdded': len(added), 'families': len(families), 'shared': len(shared),
                   'changes': sum(len(c) for c in records.values())},
        'newByCiv': {c: dict(v) for c, v in sorted(new_counts.items())},
        'shared': shared, 'families': families, 'records': records, 'added': sorted(added),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(OUT, OUT.stat().st_size // 1024, 'KB', result['from']['patch'], '->', result['to']['patch'], result['counts'])
    print('new', {c: dict(v) for c, v in new_counts.items()})
    print('labels', Counter(re.sub(r'^.* (damage|range|cooldown \(s\)|wind-up \(s\)|wind-down \(s\)|bonus vs .*)$', r'weapon \1', c['l']).split(' vs ')[0] for cs in records.values() for c in cs).most_common(30))
    show = lambda c: f"{c['l']}: {c['o']} -> {c['n']}"
    for s in shared:
        print('SHARED', s['kind'], s['name'], len(s['civs']), '|', '; '.join(show(c) for c in s['changes'])[:200])
    for f in families:
        if not f.get('shared') and f['civ'] in ('byzantine', 'french_ha_01', 'ottoman', 'templar'):
            print(f['civ'], f['kind'], f['name'], len(f['ids']), '|', '; '.join(show(c) for c in f['changes'])[:260])


if __name__ == '__main__':
    main()
