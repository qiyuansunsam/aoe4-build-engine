"""Build ranking identities offline from the committed installed-game catalog."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def slug(value):
    text = unicodedata.normalize('NFKD', value.casefold()).translate(str.maketrans({'ð': 'd', 'þ': 'th', 'æ': 'ae', 'ø': 'o'}))
    text = ''.join(c for c in text if not unicodedata.combining(c)).replace("'", '')
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


def family_name(value):
    name = ' '.join(value.split())
    name = re.sub(r'^(Elite|Veteran|Hardened|Early|Vanguard) ', '', name)
    return re.sub(r"^(Jeanne's )Elite ", r'\1', name)


def technology_name(row):
    name = ' '.join(row['name'].split())
    if name.startswith('Upgrade to'):
        target = re.search(r'\b(?:to|into)\s+([^\n.]+)', row.get('description', ''))
        if target:
            return 'Upgrade to ' + target.group(1).strip()
        if name in ('Upgrade to Elite', 'Upgrade to Veteran', 'Upgrade to Hardened'):
            return name + ' (' + row['id'].replace('_', ' ') + ')'
    return name


def military(classes):
    return bool(set(classes) & {'military', 'scar_military', 'land_military', 'naval_military'})


def classify(group, row):
    if group == 'units':
        if not row.get('classes'):
            return None
        return 'units' if military(row['classes']) else 'nonmilitary'
    if group == 'buildings':
        return 'landmarks' if row['id'].startswith('building_landmark_') else 'buildings'
    return 'landmarks' if re.match(r'upgrade_add_\w+_wing', row['id']) else 'technologies'


def build(local):
    patch = local['provenance']['patch']
    index, omitted = {}, []
    references = defaultdict(set)
    for building in local['buildings']:
        civ = building.get('civilization')
        if civ and civ != 'common':
            for key in ('trainableUnits', 'researchableTechnologies'):
                for blueprint in building.get(key, []):
                    references[blueprint].add(civ)
    for group in ('units', 'buildings', 'technologies'):
        command = {'units': 'train', 'buildings': 'build', 'technologies': 'research'}[group]
        for row in local[group]:
            source = row.get('source', {})
            pbgid = source.get('pbgid')
            kind = classify(group, row)
            if not pbgid or kind is None:
                omitted.append({'blueprint': row['id'], 'pbgid': pbgid, 'reason': 'Missing blueprint ID or unit classification'})
                continue
            name = family_name(row['name']) if group == 'units' else technology_name(row) if group == 'technologies' else ' '.join(row['name'].split())
            civs = set(references[row['id']])
            if row.get('civilization') and row['civilization'] != 'common':
                civs.add(row['civilization'])
            record = {'pbgid': int(pbgid), 'id': kind + ':' + slug(name), 'name': name,
                      'civs': sorted(civs), 'kind': kind, 'commandKind': command,
                      'age': row.get('age'), 'blueprint': row['id'], 'catalogId': row['id'],
                      'icon': row.get('icon'), 'source': source,
                      'identitySource': 'installed-' + patch, 'identityPatch': patch,
                      'identityPatchVerified': True}
            key = (command, int(pbgid))
            if key in index and index[key]['id'] != record['id']:
                raise ValueError(f'Conflicting blueprint identity: {key}')
            index[key] = record
    candidates = defaultdict(list)
    for row in local['units']:
        entity = row.get('entitySource', {}).get('pbgid')
        squad = row.get('source', {}).get('pbgid')
        if entity and ('train', squad) in index:
            candidates[int(entity)].append((index[('train', squad)], row['entitySource']))
    for entity, rows in candidates.items():
        if len({record['id'] for record, _ in rows}) != 1:
            omitted.append({'commandKind': 'build', 'pbgid': entity, 'reason': 'Ambiguous shared unit entity identity',
                            'families': sorted({record['id'] for record, _ in rows})})
            continue
        source, evidence = rows[0]
        key = ('build', entity)
        if key in index and index[key]['id'] != source['id']:
            raise ValueError(f'Conflicting unit construction identity: {key}')
        index[key] = dict(source, pbgid=entity, commandKind='build',
                          civs=sorted({c for record, _ in rows for c in record['civs']}),
                          identitySource='installed-' + patch + '-unit-entity',
                          unitSourcePbgid=source['pbgid'], entitySource=evidence)
    names = defaultdict(set)
    for record in index.values():
        names[record['id']].add(record['name'])
    conflicts = {key: sorted(value) for key, value in names.items() if len(value) > 1}
    if conflicts:
        raise ValueError(f'Conflicting normalized family names: {conflicts}')
    civilizations = [{'id': c['id'], 'name': c['name']} for c in local['civilizations']]
    return civilizations, sorted(index.values(), key=lambda x: (x['commandKind'], x['pbgid'])), omitted


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalog', type=Path, default=ROOT / 'data/game-catalog.json')
    ap.add_argument('--output', type=Path, default=ROOT / 'data/tier-catalog.json')
    args = ap.parse_args()
    local = read(args.catalog)
    civilizations, records, omitted = build(local)
    source = local['provenance']
    result = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(), 'provenance': {
        'purpose': 'Installed blueprint identity and classification only; no match outcomes.',
        'source': 'data/game-catalog.json', 'catalogSha256': hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        'localCatalogPatch': source['patch'], 'identityPatchVerified': True,
        'steamBuildId': source.get('steamBuildId'), 'archiveSha256': source.get('sha256'),
        'extractedAt': source.get('extractedAt'), 'networkDependencies': [],
        'notes': [
            'All blueprint IDs, classes, names and civilization references come from the installed-game catalog. No AoE4 World or other web dataset is used.',
            'Military families group identical installed names after removing leading age-tier prefixes. Ghillie remains distinct from Scout; Jeanne\'s Elite Champion and Rider join their non-Elite families.',
            'Military includes scouts and monks where installed classes mark them military. Workers, traders, livestock and fishing boats are excluded.',
            'Unit entitySource IDs identify field-construction orders in the build namespace. Field and workshop units with the same family name are combined. Ambiguous entity identities remain unknown.',
            'Landmarks include building_landmark blueprints and House of Wisdom wing research. Capital TCs, House of Wisdom construction, ordinary buildings and victory wonders are excluded.',
            'Technology commands include both entity research and player upgrades such as Ottoman Vizier choices; the collector decodes the two command codes.',
            'Civ availability comes from explicit catalog ownership and installed building menu references. The collector adds observed access, including mercenaries.',
            'Unknown blueprint IDs must remain unknown; they cannot be counted as absent choices.',
        ]}, 'civilizations': civilizations, 'records': records, 'omittedIdentities': omitted}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(args.output)
    print(json.dumps({'output': str(args.output), 'patch': source['patch'], 'records': len(records),
                      'civilizations': len(civilizations), 'omitted': len(omitted)}))


if __name__ == '__main__':
    main()
