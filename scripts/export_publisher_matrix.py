"""Refresh supported profile matrix rows from publisher summaries; preserve tactical scores.

The publisher summary has age times, but no continuous positions, damage, queues or
command responses required by the tactical radar. Those existing scores are retained.
"""
import argparse
import copy
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT.parent / 'games/kb/aoe4/extract/batch1000-20261111/independent-profiles/player-games.json'
DEFAULT_IDS = [7195780, 1588970, 7999822, 18518902, 8354416]
METRICS = {'growth.ages.feudal': 'age2Seconds', 'growth.ages.castle': 'age3Seconds'}
SOURCE_LABEL = 'Official publisher statistical summary; decoded headlessly'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temporary.replace(path)


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def source_rows(path):
    if path.suffix == '.jsonl':
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    yield from row['players'] if isinstance(row, dict) and 'players' in row else [row]
    else:
        data = read(path)
        yield from data if isinstance(data, list) else data['playerGames']


def refresh_components(rows):
    """Mean per player, then percentile across players with >=2 measured games."""
    by_player = defaultdict(list)
    for row in rows:
        by_player[int(row['profileId'])].append(row)
    pool = {}
    for metric, field in METRICS.items():
        pool[metric] = [statistics.mean(values) for group in by_player.values()
                        if len(values := [r[field] for r in group if isinstance(r.get(field), (int, float)) and 0 < r[field] <= r['durationSeconds']]) >= 2]
    result = {}
    for pid, group in by_player.items():
        metrics = {}
        for metric, field in METRICS.items():
            measured = [r for r in group if isinstance(r.get(field), (int, float)) and 0 < r[field] <= r['durationSeconds']]
            value = statistics.mean(r[field] for r in measured) if measured else None
            values = pool[metric]
            percentile = round(100 * (sum(v > value for v in values) + .5 * sum(v == value for v in values)) / len(values), 1) if value is not None and values else None
            metrics[metric] = {'value': round(value, 3) if value is not None else None, 'percentile': percentile,
                'n': len(values), 'games': len(measured), 'source': SOURCE_LABEL,
                'firstMatch': timestamp(min(r['startedAt'] for r in measured)) if measured else None,
                'lastMatch': timestamp(max(r['startedAt'] for r in measured)) if measured else None,
                'includedInRadarScore': False}
        result[pid] = {'games': len(group), 'metrics': metrics}
    return result


def official_recent(history_path, selected, names):
    races = {r['id']: r['name'].lower() for r in read(ROOT / 'data/winrates/relic-races.json')}
    by_player = defaultdict(dict)
    with history_path.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            match = json.loads(line)
            if match.get('build') not in (12182, 12260) or match.get('mt') not in (1, 2, 3, 4):
                continue
            members = match.get('players', [])
            for member in members:
                if member[0] not in selected or member[3] not in (0, 1):
                    continue
                players = [{'profileId': m[0], 'name': names.get(m[0], str(m[0])), 'civilization': races.get(m[2], str(m[2])),
                            'team': m[1], 'result': 'win' if m[3] == 1 else 'loss' if m[3] == 0 else None,
                            'rating': m[4], 'ratingDiff': m[5] - m[4] if m[4] is not None and m[5] is not None else None} for m in members]
                by_player[member[0]][match['id']] = {'gameId': match['id'], 'matchId': 'online-' + str(match['id']),
                    'startedAt': timestamp(match['start']), 'duration': match['dur'], 'map': match.get('mapName') or match.get('map'),
                    'mode': f"rm_{match['mt']}v{match['mt']}", 'leaderboard': 'rm_solo' if match['mt'] == 1 else 'rm_team',
                    'patch': str(match['build']), 'civilization': races.get(member[2], str(member[2])),
                    'result': 'win' if member[3] else 'loss', 'rating': member[4],
                    'ratingDiff': member[5] - member[4] if member[4] is not None and member[5] is not None else None,
                    'team': member[1], 'players': players, 'source': 'Official publisher match history'}
    return {pid: sorted(matches.values(), key=lambda m: m['startedAt'], reverse=True) for pid, matches in by_player.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--history', type=Path, default=ROOT / 'data/winrates/relic-games.jsonl')
    parser.add_argument('--profiles', nargs='+', type=int)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    config = ROOT / 'data/tracked-player-ids.json'
    configured = read(config) if config.exists() else DEFAULT_IDS
    if isinstance(configured, dict):
        configured = configured.get('profileIds', configured.get('players', DEFAULT_IDS))
    selected = set(args.profiles or configured)
    if len(selected) != 5:
        raise ValueError('Exactly five profile IDs are required')
    profiles = read(ROOT / 'data/player-profiles.json')
    analysis = read(ROOT / 'data/player-analysis.json')
    selected_profiles = [p for p in profiles['players'] if p['profileId'] in selected]
    if len(selected_profiles) != 5:
        raise ValueError('Every selected profile must exist in the identity snapshot')
    names = {p['profileId']: p['name'] for p in profiles['players']}
    rows, identities = [], set()
    for row in source_rows(args.source):
        if row['durationSeconds'] < 600:
            continue
        identity = (row['gameId'], row['profileId'])
        if identity in identities:
            raise ValueError(f'Duplicate source row: {identity}')
        identities.add(identity)
        rows.append({key: row.get(key) for key in ['gameId', 'profileId', 'civilization', 'durationSeconds', 'startedAt', *METRICS.values()]})
    overall = refresh_components(rows)
    by_civ = {}
    for civ in sorted({r['civilization'] for r in rows}):
        by_civ[civ] = refresh_components([r for r in rows if r['civilization'] == civ])
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    recent = official_recent(args.history, selected, names)
    previous_snapshot = profiles['generatedAt']
    profiles['players'] = selected_profiles
    profiles['generatedAt'] = now
    profiles['source'] = 'Official publisher recent matches; cached identities and ladder snapshots retained'
    for profile in profiles['players']:
        matches = recent.get(profile['profileId'], [])
        profile['recentGames'] = matches[:80]
        profile['recentGamesWindow'] = {'source': 'Official publisher match history', 'patchMatchesKnown': len(matches), 'displayed': min(80, len(matches))}
        profile['publisherMatchCount'] = len(matches)
        profile['modeSnapshotUnchanged'] = True
        profile.setdefault('modeSnapshotAsOf', previous_snapshot)
        if matches:
            profile['lastGameAt'] = matches[0]['startedAt']
    analysis['players'] = {key: value for key, value in analysis['players'].items() if int(key) in selected}
    analysis['roles'] = {str(pid): 'tracked' for pid in sorted(selected)}
    for pid, player in analysis['players'].items():
        numeric = int(pid)
        baseline = copy.deepcopy(player.get('radar'))
        player['publisherRefresh'] = {'generatedAt': now, 'source': SOURCE_LABEL,
            **overall.get(numeric, {'games': 0, 'metrics': {}}),
            'byCiv': {civ: values[numeric] for civ, values in by_civ.items() if numeric in values},
            'radarPreserved': True}
        assert player.get('radar') == baseline
    analysis['publisherRefresh'] = {'generatedAt': now, 'source': SOURCE_LABEL,
        'sourceGames': len({r['gameId'] for r in rows}), 'playerGames': len(rows), 'updatedMetrics': list(METRICS),
        'tacticalRadarStatus': 'Preserved recorded-telemetry scores; publisher summaries cannot refresh damage, positions, vision, queues, idle time or command-response metrics.'}
    write(args.output_dir / 'player-profiles.json', profiles)
    write(args.output_dir / 'player-analysis.json', analysis)
    print(json.dumps({'profiles': [p['profileId'] for p in selected_profiles], 'sourceGames': analysis['publisherRefresh']['sourceGames'],
        'supportedMetrics': list(METRICS), 'publisherGames': {pid: p['publisherRefresh']['games'] for pid, p in analysis['players'].items()},
        'radar': 'preserved'}))


if __name__ == '__main__':
    main()
