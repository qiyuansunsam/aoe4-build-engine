"""Count concurrent recorded TC structures, retaining packed structures as owned."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'games/kb/aoe4/extract/batch1000-20261111/publisher-parsed'


def calculate(records):
    changes = defaultdict(int)
    for record in records:
        for timestamp in record['constructed']:
            changes[timestamp] += 1
        for timestamp in record['destroyed']:
            changes[timestamp] -= 1
    count = maximum = 0
    milestones = {}
    underflow = False
    # Event order is not available within a timestamp; net simultaneous changes
    # avoid claiming a transient extra TC when one is replaced in the same tick.
    for timestamp, delta in sorted(changes.items()):
        count += delta
        underflow |= count < 0
        if count > maximum:
            for n in range(maximum + 1, count + 1):
                milestones[str(n)] = timestamp
            maximum = count
    return maximum, milestones, underflow


def main():
    catalog = json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))
    tc = {b['source']['pbgid']: b['id'] for b in catalog['buildings'] if 'town_center' in b['id']}
    rows = {}
    coverage = Counter()
    for path in sorted(SOURCE.glob('*.json')):
        game = json.loads(path.read_text(encoding='utf-8'))
        if 'gameId' not in game or 'players' not in game:
            continue
        coverage['games'] += 1
        for player in game['players']:
            records = [b for b in player['buildOrder'] if b['pbgid'] in tc]
            unknown = [b['pbgid'] for b in player['buildOrder'] if b['pbgid'] not in tc and ('town_center' in b.get('icon', '') or 'town_centre' in b.get('icon', ''))]
            maximum, milestones, underflow = calculate(records)
            has_capital = any('capital' in tc[r['pbgid']] and r['constructed'] for r in records)
            unknown_events = any(r.get('unknown') for r in records)
            status = 'verified-timeline' if has_capital and not unknown and not underflow and not unknown_events else 'incomplete'
            row = {'maximum': maximum if status == 'verified-timeline' else None, 'milestones': milestones,
                   'status': status, 'hasCapital': has_capital, 'underflow': underflow,
                   'unknownIds': unknown, 'unknownEvents': unknown_events,
                   'constructions': sum(len(r['constructed']) for r in records),
                   'destructions': sum(len(r['destroyed']) for r in records),
                   'packedEvents': sum(len(r['packed']) for r in records),
                   'unpackedEvents': sum(len(r['unpacked']) for r in records),
                   'sourceSha256': game['source']['sha256']}
            rows[f"{game['gameId']}:{player['profileId']}"] = row
            coverage[status] += 1
            coverage['replacementAffected'] += row['maximum'] is not None and row['constructions'] > row['maximum']
    target = ROOT / '.cache/tc-milestones.json'
    target.parent.mkdir(exist_ok=True)
    result = {'method': 'Maximum concurrent TC structures from constructed minus destroyed events, netted at equal timestamps. Packed TCs remain owned and unpacking does not create another TC. Incomplete timelines are excluded.',
              'catalogSha256': hashlib.sha256((ROOT / 'data/game-catalog.json').read_bytes()).hexdigest(),
              'coverage': dict(coverage), 'rows': rows}
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    assert calculate([{'constructed': [0, 100, 300], 'destroyed': [200]}])[0] == 2
    assert calculate([{'constructed': [0, 100], 'destroyed': [100]}])[0] == 1
    assert calculate([{'constructed': [0], 'destroyed': [100, 200]}])[2]
    print(json.dumps(dict(coverage)))


if __name__ == '__main__':
    main()
