"""Aggregate the Relic match rows (scripts/collect_relic_matches.py) into civilization win rates.

Output: data/winrates.json (window.WINRATES in the app; no player ids or names leave the raw store).

Counting rules, all applied to the match rows as Relic recorded them:
  * a match counts when it is ranked 1v1/2v2/3v3/4v4 on a target build, has two full teams, one team recorded
    as winner and the other as loser, and ran for MIN_DURATION seconds or longer (shorter matches are drops);
  * rank band: the average of every player's rating before the match (Relic's rating for that ladder) falls in
    the band. Diamond+ is 1200 and higher, the Diamond floor;
  * a civilization's games are its player appearances and its wins are the appearances on the winning team.
    1v1 mirror matches cannot say anything about the civilization and are left out of its win rate; they still
    count toward its pick rate;
  * "team" adds 2v2, 3v3 and 4v4 together; "solo" is 1v1.

Usage: python -X utf8 scripts/build_winrates.py
"""
import json, re, sys, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'winrates'
GAMES = RAW / 'relic-games.jsonl'
RACES = RAW / 'relic-races.json'
OUT = ROOT / 'data' / 'winrates.json'
EXTRACT = Path('C:/Users/Sam/projects/games/kb/aoe4/extract/installed-26400362')

PATCH = {'label': '17.0', 'builds': [12182, 12260], 'liveSince': '2026-10-29'}
PATCH_START = int(datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp())
MIN_DURATION = 300
MODES = {1: 'solo', 2: '2v2', 3: '3v3', 4: '4v4'}
BANDS = [{'id': 'diamond_plus', 'label': 'Diamond+', 'minRating': 1200, 'maxRating': None}]
ASCII_NAME = re.compile(r"^[A-Za-z0-9 '&.\-]+$")
CJK = re.compile(r'[\u4e00-\u9fff]')
KANA_HANGUL = re.compile(r'[\u3040-\u30ff\uac00-\ud7af]')


def races():
    """Relic race id -> catalog civilization id (the race name Relic publishes, lower-cased)."""
    if not RACES.exists():
        req = urllib.request.Request('https://aoe-api.worldsedgelink.com/community/leaderboard/getAvailableLeaderboards?title=age4',
                                     headers={'User-Agent': 'mcaoe4-build-crafter/1.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = json.loads(r.read().decode('utf-8'))['races']
        RACES.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    return {r['id']: r['name'].lower() for r in json.loads(RACES.read_text(encoding='utf-8'))}


def ucs(path):
    table = {}
    if path.exists():
        for line in path.read_text(encoding='utf-16').splitlines():
            key, _, text = line.partition('\t')
            if key.strip().isdigit():
                table[int(key)] = text.strip()
    return table


def valid(row, race_to_civ):
    size = row['mt']
    players = row['players']
    if len(players) != 2 * size or row['dur'] < MIN_DURATION:
        return None
    if row['build'] is None:
        if row['start'] < PATCH_START:
            return None
    elif row['build'] not in PATCH['builds']:
        return None
    teams = defaultdict(list)
    for p in players:
        if p[2] not in race_to_civ:
            return None
        teams[p[1]].append(p)
    if len(teams) != 2 or any(len(t) != size for t in teams.values()):
        return None
    outcomes = [{p[3] for p in t} for t in teams.values()]
    if any(len(o) != 1 for o in outcomes) or {next(iter(o)) for o in outcomes} != {0, 1}:
        return None
    return sum(p[4] for p in players) / len(players)


def main():
    race_to_civ = races()
    catalog = {c['id'] for c in json.loads((ROOT / 'data/game-catalog.json').read_text(encoding='utf-8'))['civilizations']}
    missing = sorted(set(race_to_civ.values()) - catalog)
    if missing:
        sys.exit(f'Relic races with no catalog civilization: {missing}')

    rows, seen = [], set()
    with GAMES.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if row['id'] not in seen:
                    seen.add(row['id'])
                    rows.append(row)

    def bucket():
        return {'games': 0, 'mirrors': 0, 'civs': defaultdict(lambda: [0, 0, 0]), 'maps': defaultdict(lambda: {'games': 0, 'civs': defaultdict(lambda: [0, 0, 0])})}

    out_ranks, map_names, builds, dropped = {}, defaultdict(Counter), Counter(), Counter()
    span = [None, None]
    rated = []
    for row in rows:
        average = valid(row, race_to_civ)
        if average is None:
            dropped['short' if row['dur'] < MIN_DURATION else 'incomplete'] += 1
            continue
        rated.append((row, average))
        if row.get('mapName'):
            map_names[row['map']][row['mapName'].strip()] += 1

    for band in BANDS:
        modes = {m: bucket() for m in ['solo', 'team', '2v2', '3v3', '4v4']}
        counted = 0
        for row, average in rated:
            if average < band['minRating'] or (band['maxRating'] is not None and average >= band['maxRating']):
                continue
            counted += 1
            builds[str(row['build'] or 'unknown')] += 1
            span[0] = row['start'] if span[0] is None else min(span[0], row['start'])
            span[1] = row['start'] if span[1] is None else max(span[1], row['start'])
            mode = MODES[row['mt']]
            civs = [race_to_civ[p[2]] for p in row['players']]
            mirror = mode == 'solo' and civs[0] == civs[1]
            for target in ([mode] if mode == 'solo' else [mode, 'team']):
                for scope in (modes[target], modes[target]['maps'][row['map']]):
                    scope['games'] += 1
                    for p, civ in zip(row['players'], civs):
                        cell = scope['civs'][civ]
                        cell[2] += 1                    # picks: every appearance
                        if not mirror:
                            cell[0] += 1                # games that count toward the win rate
                            cell[1] += p[3]             # wins
                if mirror:
                    modes[target]['mirrors'] += 1
        out_ranks[band['id']] = {'games': counted, 'modes': {
            m: {'games': b['games'], 'mirrors': b['mirrors'],
                'civs': {c: v for c, v in sorted(b['civs'].items())},
                'maps': {s: {'games': mv['games'], 'civs': {c: v for c, v in sorted(mv['civs'].items())}}
                         for s, mv in sorted(b['maps'].items(), key=lambda kv: -kv[1]['games'])}}
            for m, b in modes.items()}}

    en, zh = ucs(EXTRACT / 'LocaleEnglish/en/cardinal.en.ucs'), ucs(EXTRACT / 'LocaleSimplifiedChinese/zh-hans/cardinal.zh-hans.ucs')
    by_text = defaultdict(list)
    for key, text in en.items():
        by_text[text].append(key)
    maps = {}
    for slug, names in map_names.items():
        latin = [n for n, c in names.most_common() if ASCII_NAME.match(n)]
        english = [n for n in latin if n in by_text]    # the creator's client language decides the recorded name
        name = (english or latin or [slug.replace('_', ' ').title()])[0]
        official = [zh[k] for k in by_text.get(name, []) if zh.get(k) and CJK.search(zh[k])]
        if official:
            chinese = Counter(official).most_common(1)[0][0]
        else:
            seen_cjk = [(n, c) for n, c in names.most_common() if CJK.search(n) and not KANA_HANGUL.search(n)]
            chinese = seen_cjk[0][0] if seen_cjk else None
        maps[slug] = {'name': name, 'zh': chinese}

    result = {
        'schemaVersion': 1,
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': {'name': "Relic community API (the game's own match service)", 'url': 'https://aoe-api.worldsedgelink.com/community/leaderboard',
                   'calls': ['getLeaderBoard2', 'getRecentMatchHistory']},
        'patch': PATCH,
        'rules': {'minDurationSeconds': MIN_DURATION, 'ratingField': 'average player rating before the match, as Relic recorded it for that ladder',
                  'soloMirrorsExcluded': True, 'teamModes': ['2v2', '3v3', '4v4']},
        'sample': {'matchesStored': len(rows), 'matchesCounted': sum(r['games'] for r in out_ranks.values()), 'dropped': dict(dropped), 'builds': dict(builds),
                   'firstMatch': span[0] and datetime.fromtimestamp(span[0], timezone.utc).strftime('%Y-%m-%d'),
                   'lastMatch': span[1] and datetime.fromtimestamp(span[1], timezone.utc).strftime('%Y-%m-%d')},
        'bands': BANDS,
        'maps': maps,
        'ranks': out_ranks,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for band in BANDS:
        r = out_ranks[band['id']]
        print(band['label'], r['games'], 'matches;', {m: v['games'] for m, v in r['modes'].items()})
        for mode in ('solo', 'team'):
            top = sorted(((v[1] / v[0], c, v[0]) for c, v in r['modes'][mode]['civs'].items() if v[0] >= 50), reverse=True)
            print(' ', mode, ' | '.join(f'{c} {100 * w:.1f}% ({n})' for w, c, n in top[:6]), '...', ' | '.join(f'{c} {100 * w:.1f}% ({n})' for w, c, n in top[-3:]))
    print('maps', {s: (m['name'], m['zh']) for s, m in maps.items()})
    print('builds', dict(builds), 'dropped', dict(dropped), 'stored', len(rows), '->', OUT, OUT.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main()
