"""Bounded, resumable official-match collection and headless command rankings."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import re
import struct
import subprocess
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from vendor import recfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/rankings'
BASE = 'https://aoe-api.worldsedgelink.com/community/leaderboard/'
UA = 'mcaoe4/1.0 (headless patch statistics; github.com/qiyuansunsam/aoe4-build-engine)'
MODES = {'rm_1v1': 1, 'rm_2v2': 2, 'rm_3v3': 3, 'rm_4v4': 4}
PARSER_VERSION = 4


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temp.replace(path)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class RateLimited(RuntimeError):
    pass


class Client:
    def __init__(self, delay=1.0, refresh=False):
        self.delay, self.refresh, self.last = delay, refresh, 0
        self.lock = threading.Lock()

    def fetch(self, url, limit=32 * 1024 * 1024):
        with self.lock:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
            self.last = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=35) as response:
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise ValueError('Response exceeds size limit')
                return raw
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise RateLimited('Official service rate limited collection; cached progress is preserved.') from None
            raise

    def api(self, endpoint, **params):
        query = urllib.parse.urlencode({'title': 'age4', **params})
        digest = hashlib.sha256(query.encode()).hexdigest()[:20]
        path = CACHE / 'api' / f'{endpoint}-{digest}.json'
        if path.exists() and not self.refresh and time.time() - path.stat().st_mtime < 21600:
            return read(path)
        result = json.loads(self.fetch(BASE + endpoint + '?' + query))
        if result.get('result', {}).get('code') != 0:
            raise ValueError(f'{endpoint}: unsuccessful result envelope')
        write(path, result)
        return result


def match_patch(match):
    patches = {int(m.group(1)) for row in match.get('matchurls', [])
               if (m := re.search(r'/replay/windows/[^/]+/(\d+)/', row.get('url', '')))}
    return next(iter(patches)) if len(patches) == 1 else None


def eligible_match(match, modes):
    reports = match.get('matchhistoryreportresults', [])
    mode = next((k for k in modes if MODES[k] == match.get('matchtype_id')), None)
    if not mode or match.get('completiontime', 0) <= match.get('startgametime', 0):
        return False
    expected = MODES[mode] * 2
    if len(reports) != expected or len({p['profile_id'] for p in reports}) != expected:
        return False
    teams = collections.defaultdict(set)
    for p in reports:
        if p.get('resulttype') not in (0, 1):
            return False
        teams[p['teamid']].add(p['resulttype'])
    return len(teams) == 2 and {tuple(x) for x in teams.values()} == {(0,), (1,)}


def discover(client, modes, profiles_per_stratum, merge_cache=False):
    discovery = client.api('getAvailableLeaderboards')
    profiles, sampling = set(), []
    for mode in modes:
        boards = [b for b in discovery['leaderboards'] if b['name'].lower() == f'Slot1_{MODES[mode]}v{MODES[mode]}Ranked'.lower()]
        if len(boards) != 1:
            raise ValueError(f'Cannot resolve official leaderboard for {mode}')
        board = boards[0]
        if MODES[mode] not in {x['matchtype_id'] for x in board['leaderboardmap']}:
            raise ValueError('Leaderboard/match type mapping changed')
        for start in (1, 1001, 5001, 15001, 30001, 60001):
            page = client.api('getLeaderBoard2', leaderboard_id=board['id'], start=start,
                              count=max(10, profiles_per_stratum), sortBy=1)
            groups = {x['id']: x for x in page.get('statGroups', [])}
            candidates = sorted(page.get('leaderboardStats', []), key=lambda x: x.get('lastmatchdate', 0), reverse=True)
            selected = []
            for stat in candidates[:profiles_per_stratum]:
                selected.extend(x['profile_id'] for x in groups.get(stat['statgroup_id'], {}).get('members', []))
            profiles.update(selected)
            sampling.append({'mode': mode, 'rankStart': start, 'profiles': selected})
    matches, aliases, errors = {}, {}, []
    if merge_cache and (CACHE / 'manifest.json').exists():
        previous = read(CACHE / 'manifest.json')
        matches = {m['id']: m for m in previous['matches'] if eligible_match(m, modes)}
        aliases.update({str(k): v for k, v in previous['aliases'].items()})
        sampling = previous['sampling'] + sampling
    profile_list = sorted(profiles)
    for index in range(0, len(profile_list), 4):
        batch = profile_list[index:index + 4]
        try:
            history = client.api('getRecentMatchHistory', profile_ids=json.dumps(batch))
            for p in history.get('profiles', []):
                aliases[str(p['profile_id'])] = p.get('alias', '')
            for m in history.get('matchHistoryStats', []):
                if eligible_match(m, modes):
                    matches[m['id']] = m
            print(json.dumps({'stage': 'history', 'profiles': min(index + 4, len(profiles)), 'of': len(profiles), 'matches': len(matches)}), flush=True)
        except RateLimited:
            raise
        except (OSError, ValueError) as exc:
            errors.append({'profileIds': batch, 'error': safe_error(exc)})
    if not matches:
        raise ValueError('No completed ranked matches discovered')
    latest = next((m for m in sorted(matches.values(), key=lambda x: x['startgametime'], reverse=True) if match_patch(m)), None)
    if latest is None:
        raise ValueError('No official patch metadata found')
    manifest = {'generatedAt': now(), 'latestPatch': match_patch(latest), 'sampling': sampling,
                'modes': modes, 'races': discovery['races'], 'aliases': aliases,
                'matches': list(matches.values()), 'errors': errors}
    write(CACHE / 'manifest.json', manifest)
    return manifest


def safe_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f'HTTP {exc.code}'
    return str(exc).split('https://')[0][:200]


def expand(client, manifest, patch, limit):
    seeds = {p for s in manifest['sampling'] for p in s['profiles']}
    candidates = {}
    for match in manifest['matches']:
        if match_patch(match) != patch:
            continue
        for member in match.get('matchhistorymember', []):
            if member['profile_id'] not in seeds:
                candidates[member['profile_id']] = member.get('oldrating')
    bands = [[], [], []]
    for pid, rating in candidates.items():
        bands[0 if rating is None or rating < 1000 else 1 if rating < 1400 else 2].append(pid)
    for band in bands:
        band.sort(key=lambda p: hashlib.sha256(str(p).encode()).hexdigest())
    selected = []
    while any(bands) and len(selected) < limit:
        for band in bands:
            if band and len(selected) < limit:
                selected.append(band.pop())
    matches = {m['id']: m for m in manifest['matches']}
    aliases = {str(k): v for k, v in manifest['aliases'].items()}
    for start in range(0, len(selected), 4):
        batch = selected[start:start + 4]
        try:
            history = client.api('getRecentMatchHistory', profile_ids=json.dumps(batch))
            for p in history.get('profiles', []):
                aliases[str(p['profile_id'])] = p.get('alias', '')
            for match in history.get('matchHistoryStats', []):
                if eligible_match(match, manifest['modes']):
                    matches[match['id']] = match
            manifest['sampling'].append({'kind': 'current-patch-participant-expansion', 'profiles': batch})
            print(json.dumps({'stage': 'expand', 'profiles': min(start + 4, len(selected)), 'of': len(selected), 'matches': len(matches)}), flush=True)
        except RateLimited:
            raise
        except (OSError, ValueError) as exc:
            manifest['errors'].append({'profiles': batch, 'error': safe_error(exc)})
        manifest.update(matches=list(matches.values()), aliases=aliases, generatedAt=now())
        write(CACHE / 'manifest.json', manifest)
    return manifest


def replay_sample(matches, limit):
    queues = collections.defaultdict(list)
    for match in matches:
        queues[match['matchtype_id']].append(match)
    for queue in queues.values():
        queue.sort(key=lambda m: hashlib.sha256(str(m['id']).encode()).hexdigest(), reverse=True)
    selected = []
    while any(queues.values()) and len(selected) < limit:
        for mode in sorted(queues):
            if queues[mode] and len(selected) < limit:
                selected.append(queues[mode].pop())
    return selected


def import_history(manifest):
    matches = {m['id']: m for m in manifest['matches']}
    aliases = {str(k): v for k, v in manifest['aliases'].items()}
    files = list((CACHE / 'history-refresh').glob('*.json'))
    for path in files:
        history = read(path)
        aliases.update({str(k): v for k, v in history['aliases'].items()})
        for match in history['matches']:
            if eligible_match(match, manifest['modes']):
                matches[match['id']] = match
    manifest.update(matches=list(matches.values()), aliases=aliases, generatedAt=now())
    manifest['sampling'].append({'kind': 'active-Diamond-plus-official-ladder-crawl', 'profiles': [], 'historyFiles': len(files)})
    write(CACHE / 'manifest.json', manifest)
    print(json.dumps({'stage': 'import', 'historyFiles': len(files), 'matches': len(matches)}), flush=True)
    return manifest


def unpack(raw):
    if raw[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = [f for f in archive.infolist() if not f.is_dir()]
            if len(files) != 1 or files[0].file_size > 128 * 1024 * 1024:
                raise ValueError('Unexpected replay archive')
            raw = archive.read(files[0])
    if raw[:2] == b'\x1f\x8b':
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(128 * 1024 * 1024 + 1)
    if len(raw) > 128 * 1024 * 1024 or raw[4:11] != b'AOE4_RE':
        raise ValueError('Invalid replay payload')
    return raw


def download(client, match):
    path = CACHE / 'replays' / f"{match['id']}.rec"
    if path.exists():
        return path
    participants = [r['profile_id'] for r in match.get('matchurls', []) if r.get('datatype') == 0]
    participants = list(dict.fromkeys(participants))[:2]
    if not participants:
        raise ValueError('No replay profile available')
    last_error = None
    for pid in participants:
        url = 'https://api.ageofempires.com/api/GameStats/AgeIV/GetMatchReplay/?' + urllib.parse.urlencode({'matchId': match['id'], 'profileId': pid})
        try:
            raw = unpack(client.fetch(url))
            if int.from_bytes(raw[2:4], 'little') != match_patch(match):
                raise ValueError('Replay header does not match official patch metadata')
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.tmp')
            temp.write_bytes(raw)
            temp.replace(path)
            return path
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (403, 404):
                raise
    raise last_error or ValueError('Replay unavailable')


def parse(path):
    parsed_path = CACHE / 'parsed' / (path.stem + '.json')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if parsed_path.exists():
        saved = read(parsed_path)
        if saved.get('parserVersion') == PARSER_VERSION and saved.get('sha256') == digest:
            return saved
    replay = recfile.load(path)
    commands, counts = [], collections.Counter()
    known_players = {p.pid for p in replay.players}
    for tick in replay.ticks():
        for _, payload in tick.blocks:
            offset = 0
            while offset < len(payload):
                if offset + 2 > len(payload):
                    raise ValueError('Truncated command length')
                length = struct.unpack_from('<H', payload, offset)[0]
                if length < 3 or offset + length > len(payload):
                    raise ValueError('Invalid command boundary')
                command = payload[offset:offset + length]
                offset += length
                code = command[2]
                counts[str(code)] += 1
                kind = 'research' if code == 0x82 else recfile.COMMAND_KINDS.get(code)
                if kind is None:
                    continue
                if len(command) < 35:
                    raise ValueError('Truncated choice command')
                pid = struct.unpack_from('<I', command, 20)[0] - 1000
                dtype, data = recfile.command_data(command)
                if pid not in known_players:
                    raise ValueError('Unrecognized choice command player')
                if len(data) < 5 or data[0] != 1:
                    commands.append([pid, kind, 0, tick.tick])
                    continue
                commands.append([pid, kind, struct.unpack_from('<I', data, 1)[0], tick.tick])
    if not commands or len(known_players) != len(replay.players):
        raise ValueError('Replay has no choices or ambiguous player IDs')
    result = {'parserVersion': PARSER_VERSION, 'sha256': digest, 'patch': replay.version,
              'duration': replay.duration_seconds, 'players': [vars(p) for p in replay.players],
              'commands': commands, 'commandTypes': dict(counts)}
    write(parsed_path, result)
    return result


def bind_players(parsed, match, aliases, race_ids):
    reports = match['matchhistoryreportresults']
    if len(parsed['players']) != len(reports):
        raise ValueError('Replay participant count differs from official results')
    bound = {}
    for p in parsed['players']:
        same_seat = [r for r in reports if race_ids.get(r['civilization_id']) == p['civ'] and r['teamid'] == p['team']]
        candidates = [r for r in same_seat if aliases.get(str(r['profile_id']), aliases.get(r['profile_id'])) == p['name']]
        if not candidates and len(same_seat) == 1:
            candidates = same_seat
        if len(candidates) != 1 or candidates[0]['profile_id'] in bound.values():
            raise ValueError('Cannot uniquely join replay player to official result')
        bound[p['pid']] = candidates[0]['profile_id']
    return bound


def catalog_index(catalog):
    index = {}
    for record in catalog['records']:
        command_kind = record.get('commandKind') or {'units': 'train', 'nonmilitary': 'train', 'technologies': 'research', 'buildings': 'build', 'landmarks': 'build'}[record['kind']]
        index[(command_kind, int(record['pbgid']))] = record
    return index


def export(manifest, patch, catalog):
    idx = catalog_index(catalog)
    race_ids = {x['id']: x['name'].lower() for x in manifest['races']}
    civ_names = {c['id']: c['name'] for c in catalog['civilizations']}
    matches = [m for m in manifest['matches'] if match_patch(m) == patch]
    observations, unknowns, errors, used_items = [], collections.Counter(), [], {}
    coverage = {'matches': len(matches), 'playerGames': 0, 'replays': 0, 'parsedReplays': 0, 'failedReplays': 0,
                'mappedUnitPlayerGames': 0, 'mappedTechnologyPlayerGames': 0, 'mappedLandmarkPlayerGames': 0,
                'excludedOtherPatchOrUnknown': len(manifest['matches']) - len(matches)}
    for match in matches:
        gid = match['id']
        parsed = bound = None
        path = CACHE / 'replays' / f'{gid}.rec'
        if path.exists():
            coverage['replays'] += 1
            try:
                parsed = parse(path)
                if parsed['patch'] != patch:
                    raise ValueError('Replay patch mismatch')
                bound = bind_players(parsed, match, manifest['aliases'], race_ids)
                coverage['parsedReplays'] += 1
            except (ValueError, OSError, IndexError, struct.error) as exc:
                errors.append({'gameId': gid, 'error': safe_error(exc)})
                parsed = bound = None
                coverage['failedReplays'] += 1
        ratings = {p['profile_id']: p.get('oldrating') for p in match.get('matchhistorymember', [])}
        rows = {}
        for report in match['matchhistoryreportresults']:
            pid = report['profile_id']
            rows[pid] = {'gameId': gid, 'profileId': pid, 'civ': race_ids.get(report['civilization_id'], str(report['civilization_id'])),
                         'mode': next(k for k, v in MODES.items() if v == match['matchtype_id']),
                         'rating': ratings.get(pid), 'result': 'win' if report['resulttype'] == 1 else 'loss',
                         'duration': match['completiontime'] - match['startgametime'], 'startedAt': match['startgametime'],
                         'choicesAvailable': parsed is not None, 'unitChoicesAvailable': parsed is not None,
                         'technologyChoicesAvailable': parsed is not None, 'landmarkChoicesAvailable': parsed is not None,
                         'units': {}, 'technologies': [], 'landmarks': []}
        if parsed:
            for player, kind, pbgid, tick in parsed['commands']:
                row = rows[bound[player]]
                record = idx.get((kind, pbgid))
                if record is None:
                    unknowns[(kind, pbgid)] += 1
                    if kind == 'train':
                        row['unitChoicesAvailable'] = False
                    elif kind == 'research':
                        row['technologyChoicesAvailable'] = False
                        row['landmarkChoicesAvailable'] = False
                    else:
                        row['unitChoicesAvailable'] = False
                        row['landmarkChoicesAvailable'] = False
                    continue
                category = record['kind']
                if category not in ('units', 'technologies', 'landmarks'):
                    continue
                item_id = record['id']
                item = used_items.setdefault((category, item_id), {'id': item_id, 'name': record['name'], 'civs': set(), 'age': record.get('age'), 'icon': record.get('icon'), 'catalogId': record.get('catalogId')})
                item['civs'].add(row['civ'])
                if category == 'units':
                    row['units'][item_id] = row['units'].get(item_id, 0) + 1
                elif item_id not in row[category]:
                    row[category].append(item_id)
        for row in rows.values():
            coverage['mappedUnitPlayerGames'] += row['unitChoicesAvailable']
            coverage['mappedTechnologyPlayerGames'] += row['technologyChoicesAvailable']
            coverage['mappedLandmarkPlayerGames'] += row['landmarkChoicesAvailable']
            observations.append(row)
    coverage['playerGames'] = len(observations)
    status_path = CACHE / 'collection-status.json'
    status = read(status_path) if status_path.exists() else {}
    match_ids = {m['id'] for m in matches}
    failures = {e['gameId'] for e in status.get('errors', []) if e['gameId'] in match_ids
                and not (CACHE / 'replays' / f"{e['gameId']}.rec").exists()}
    coverage['unavailableReplays'] = len(failures)
    coverage['unattemptedReplays'] = max(0, len(matches) - coverage['replays'] - len(failures))
    items = {k: [] for k in ('units', 'technologies', 'landmarks')}
    for (category, item_id), item in used_items.items():
        declared = {c for r in catalog['records'] if r['kind'] == category and r['id'] == item_id for c in r.get('civs', []) if c != 'common'}
        item['civs'] = sorted(item['civs'] | declared)
        items[category].append(item)
    for values in items.values():
        values.sort(key=lambda x: x['name'])
    data = {'schemaVersion': 1, 'generatedAt': now(), 'patch': {'id': patch, 'label': f'Build {patch}', 'verified': True},
            'provenance': {'results': 'Official World\u2019s Edge match history', 'choices': 'Official replay commands',
                           'patch': 'Official match replay URL build; downloaded headers cross-checked',
                           'metadata': catalog.get('provenance'), 'discoveredAt': manifest['generatedAt'],
                           'sampling': manifest['sampling'], 'parserVersion': PARSER_VERSION},
            'coverage': coverage,
            'notes': ['Unit composition is the count share of military production orders (training plus field construction), not completed production. Cancelled or unpaid orders remain included; automatic/free units are not counted.',
                      'Technologies and landmarks mean ordered at least once, not completed. Research and construction may be cancelled.',
                      'A choice wins when its player wins the match. These associations do not measure causal strength or individual combat wins.',
                      'Sampled recent histories from six ladder-rank bands, optionally expanded through current-patch participants. This is not a complete ladder census or a random sample. Shared matches are deduplicated.',
                      'Civilisation results include all patch-identified sampled matches. Choice rankings use only successfully parsed and mapped player-games; replay availability can bias them.',
                      'Unknown blueprint IDs exclude that player-game from the affected choice category. Missing data is never a loss or zero usage.',
                      'Blueprint identities and classifications come from the installed 17.0.12260 catalog. No AoE4 World data or summaries are requested.',
                      'Each player-game is one observation. Teammates and repeated players are correlated; displayed intervals are descriptive and not cluster-adjusted.',
                      'Late-game technology and landmark choices depend on surviving long enough. Win rates are descriptive, not controlled estimates of their benefit.'],
            'civilizations': [{'id': key, 'name': civ_names.get(key, key.replace('_', ' ').title())} for key in sorted(set(race_ids.values()))],
            'items': items, 'observations': observations,
            'audit': {'unknownBlueprints': [{'commandKind': k, 'pbgid': p, 'orders': n} for (k, p), n in unknowns.most_common()], 'parseErrors': errors,
                      'downloadErrors': status.get('errors', []), 'discoveryErrors': manifest['errors']}}
    write(CACHE / 'observations.json', data)
    write(ROOT / 'data/tierlists.json', aggregate_public(data))
    print(json.dumps({'stage': 'export', **coverage, 'items': {k: len(v) for k, v in items.items()}, 'unknownBlueprints': len(unknowns)}), flush=True)
    return data


def aggregate_public(data):
    def category():
        return {'games': 0, 'wins': 0, 'items': {}}

    groups = {}
    mode_games = collections.defaultdict(set)
    parsed_games = collections.defaultdict(set)
    for row in data['observations']:
        rating = row['rating']
        band = 'unknown' if rating is None else 'under1000' if rating < 1000 else '1000-1399' if rating < 1400 else '1400plus'
        key = (row['mode'], row['civ'], band)
        group = groups.setdefault(key, {'mode': key[0], 'civ': key[1], 'ratingBand': band, 'games': 0, 'wins': 0,
                                       'units': category(), 'technologies': category(), 'landmarks': category()})
        won = row['result'] == 'win'
        group['games'] += 1
        group['wins'] += won
        mode_games[row['mode']].add(row['gameId'])
        if row['choicesAvailable']:
            parsed_games[row['mode']].add(row['gameId'])
        for kind, available in [('units', 'unitChoicesAvailable'), ('technologies', 'technologyChoicesAvailable'), ('landmarks', 'landmarkChoicesAvailable')]:
            if not row[available]:
                continue
            total = sum(row['units'].values()) if kind == 'units' else 1
            if not total:
                continue
            scope = group[kind]
            scope['games'] += 1
            scope['wins'] += won
            for item_id in row[kind]:
                item = scope['items'].setdefault(item_id, {'uses': 0, 'wins': 0})
                item['uses'] += 1
                item['wins'] += won
                if kind == 'units':
                    share = row['units'][item_id] / total
                    for metric, value in [('shareSum', share), ('winShareSum', share if won else 0), ('lossShareSum', 0 if won else share)]:
                        item[metric] = item.get(metric, 0) + value
                    bins = item.setdefault('bands', [{'games': 0, 'wins': 0, 'shareSum': 0} for _ in range(5)])
                    index = next(i for i in range(5) if share <= (i + 1) / 5)
                    bins[index]['games'] += 1
                    bins[index]['wins'] += won
                    bins[index]['shareSum'] += share
    public = {k: data[k] for k in ('generatedAt', 'patch', 'notes', 'civilizations', 'items')}
    public['schemaVersion'] = 2
    public['patch']['label'] = '17.0.' + str(data['patch']['id'])
    public['coverage'] = dict(data['coverage'])
    public['coverage']['byMode'] = {mode: {'matches': len(ids), 'parsedReplays': len(parsed_games[mode]),
                                           'playerGames': sum(g['games'] for g in groups.values() if g['mode'] == mode)} for mode, ids in mode_games.items()}
    public['provenance'] = {k: v for k, v in data['provenance'].items() if k != 'sampling'}
    public['audit'] = {'unknownBlueprints': data['audit']['unknownBlueprints'], 'parseFailures': len(data['audit']['parseErrors']),
                       'downloadFailures': len(data['audit']['downloadErrors']), 'discoveryFailures': len(data['audit']['discoveryErrors'])}
    public['groups'] = list(groups.values())
    return public


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--modes', default='rm_1v1,rm_2v2,rm_3v3,rm_4v4')
    ap.add_argument('--patch', type=int)
    ap.add_argument('--profiles-per-stratum', type=int, default=4)
    ap.add_argument('--max-replays', type=int, default=0, help='Replay budget; 0 processes every discovered match in the selected build.')
    ap.add_argument('--workers', type=int, default=4, help='Concurrent downloads; request starts remain globally spaced by --delay.')
    ap.add_argument('--expand-profiles', type=int, default=0, help='Bounded expansion through current-patch participants, balanced across three rating bands.')
    ap.add_argument('--delay', type=float, default=1)
    ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--merge-cache', action='store_true', help='Retain previously collected official matches in the requested modes.')
    ap.add_argument('--resume', action='store_true', help='Reuse the existing manifest and its modes, instead of running discovery.')
    ap.add_argument('--export-only', action='store_true', help='Export the existing manifest and its modes without network requests.')
    ap.add_argument('--build-site', action='store_true', help='Rebuild the local app after exporting the ranking snapshot.')
    ap.add_argument('--import-history', action='store_true', help='Merge compact metadata from collect_relic_matches.py --save-replay-metadata.')
    args = ap.parse_args()
    modes = args.modes.split(',')
    if any(m not in MODES for m in modes) or args.max_replays < 0 or not 1 <= args.workers <= 4 or not 0 <= args.expand_profiles <= 200 or not 1 <= args.profiles_per_stratum <= 20 or args.delay < 0.5:
        ap.error('Invalid modes, replay bound, profile count or delay (minimum 0.5s)')
    client = Client(args.delay, args.refresh)
    manifest = read(CACHE / 'manifest.json') if args.resume or args.export_only else discover(client, modes, args.profiles_per_stratum, args.merge_cache)
    if args.import_history:
        manifest = import_history(manifest)
    patch = args.patch or manifest['latestPatch']
    if args.expand_profiles and not args.export_only:
        manifest = expand(client, manifest, patch, args.expand_profiles)
    catalog_path = ROOT / 'data/tier-catalog.json'
    if not args.export_only:
        matches = [m for m in manifest['matches'] if match_patch(m) == patch]
        matches = replay_sample(matches, args.max_replays or len(matches))
        status = {'startedAt': now(), 'patch': patch, 'target': len(matches), 'attempted': 0, 'downloaded': 0, 'errors': []}
        with ThreadPoolExecutor(args.workers) as pool:
            jobs = {pool.submit(download, client, match): match for match in matches}
            for future in as_completed(jobs):
                match = jobs[future]
                try:
                    path = future.result()
                    parse(path)
                    status['downloaded'] += 1
                except RateLimited as exc:
                    status['stoppedReason'] = str(exc)
                    write(CACHE / 'collection-status.json', status)
                    for job in jobs:
                        job.cancel()
                    break
                except (OSError, ValueError, IndexError, struct.error) as exc:
                    status['errors'].append({'gameId': match['id'], 'error': safe_error(exc)})
                status['attempted'] += 1
                status['updatedAt'] = now()
                write(CACHE / 'collection-status.json', status)
                if status['attempted'] % 20 == 0:
                    print(json.dumps({'stage': 'replays', 'attempted': status['attempted'], 'target': status['target'], 'downloaded': status['downloaded'], 'errors': len(status['errors'])}), flush=True)
                if status['attempted'] % 100 == 0 and catalog_path.exists():
                    export(manifest, patch, read(catalog_path))
                    if args.build_site:
                        subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'site/build.py')], cwd=ROOT, check=True)
        status['finishedAt'] = now()
        write(CACHE / 'collection-status.json', status)
    if catalog_path.exists():
        export(manifest, patch, read(catalog_path))
        if args.build_site:
            subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'site/build.py')], cwd=ROOT, check=True)
    else:
        print('Collection cached. Build data/tier-catalog.json then rerun --export-only.', flush=True)


if __name__ == '__main__':
    main()
