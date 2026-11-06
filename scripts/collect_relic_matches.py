"""Collect ranked match results for the current patch straight from Relic's public community API.

Source: https://aoe-api.worldsedgelink.com/community/leaderboard (the service the game client itself uses).
  getLeaderBoard2          ranked ladders 1..4 (1v1, 2v2, 3v3, 4v4): rating, last match date per player
  getRecentMatchHistory    one player's last ten matches per match type: map, civilizations, teams, outcome,
                           each player's rating before and after the match, and the replay URLs, whose path
                           names the game build the match was played on

Step 1 (seeds): every player rated SEED_MIN_RATING or higher on a ranked ladder who has played since the patch
went live. A game whose average rating reaches the Diamond floor must contain at least one such player.
Step 2 (matches): fetch those players' recent matches in random order (fixed seed, so a capped run is an unbiased
sample of the seed list) and append every ranked match of a target build to data/winrates/relic-games.jsonl.

The run is resumable and incremental: fetched players and stored match ids are remembered in
data/winrates/relic-state.json, so a later run only adds newer matches.

Usage: python -X utf8 scripts/collect_relic_matches.py [--max-profiles N] [--workers 4] [--refresh-seeds]
Then:  python -X utf8 scripts/build_winrates.py
"""
import argparse, base64, json, random, re, sys, threading, time, urllib.error, urllib.parse, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'winrates'
GAMES = OUT / 'relic-games.jsonl'
STATE = OUT / 'relic-state.json'
API = 'https://aoe-api.worldsedgelink.com/community/leaderboard'
UA = 'mcaoe4-build-crafter/1.0 (ranked win-rate aggregation; github.com/qiyuansunsam/aoe4-build-engine)'

# Update 17.0 went live 2026-10-29 (build 12182); the 2026-11-04 hotfix is build 12260.
TARGET_BUILDS = (12182, 12260)
PATCH_START = int(datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp())
RANKED = {1: '1v1', 2: '2v2', 3: '3v3', 4: '4v4'}   # leaderboard id == match type id for the ranked ladders
SEED_MIN_RATING = 1200                               # Diamond floor
BUILD_RE = re.compile(r'/replay/[^/]+/[^/]+/(\d+)/')

lock = threading.Lock()


def get(path, params, timeout=90, tries=4):
    url = f'{API}/{path}?' + urllib.parse.urlencode(params)
    delay = 5
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            wait = int(e.headers.get('Retry-After') or delay) if e.code == 429 else delay
            if attempt == tries - 1 or e.code in (400, 401, 403, 404):
                raise
            time.sleep(min(wait, 120))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(delay)
        delay *= 2


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding='utf-8'))
    return {'seeds': {}, 'seedsAt': None, 'fetched': {}, 'runs': []}


def save_state(state):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, separators=(',', ':')), encoding='utf-8')
    tmp.replace(STATE)


def collect_seeds(board):
    """Players rated >= SEED_MIN_RATING on one ranked ladder, active since the patch."""
    found, start, total_seen = {}, 1, 0
    while True:
        d = get('getLeaderBoard2', {'title': 'age4', 'leaderboard_id': board, 'start': start, 'count': 200, 'sortBy': 1})
        stats = d.get('leaderboardStats') or []
        if not stats:
            break
        owner = {}
        for g in d.get('statGroups') or []:
            members = g.get('members') or []
            if len(members) == 1:
                owner[g['id']] = members[0]['profile_id']
        low = None
        for s in stats:
            low = s['rating'] if low is None else min(low, s['rating'])
            total_seen += 1
            pid = owner.get(s['statgroup_id'])
            if pid and s['rating'] >= SEED_MIN_RATING and s.get('lastmatchdate', 0) >= PATCH_START:
                found[pid] = s['rating']
        if low is None or low < SEED_MIN_RATING or len(stats) < 200:
            break
        start += 200
    print(f'  ladder {RANKED[board]}: {len(found)} active players rated {SEED_MIN_RATING}+ ({total_seen} rows read)', flush=True)
    return board, found


def decode_options(raw):
    try:
        text = zlib.decompress(base64.b64decode(raw)).decode('utf-8', 'replace').strip('\x00')
        text = text[:text.rindex('}') + 1]
        return json.loads(text)
    except Exception:
        return {}


def compact(match):
    """One stored row per ranked match of a target build; None for anything else."""
    kind = match.get('matchtype_id')
    if kind not in RANKED:
        return None
    start, end = match.get('startgametime') or 0, match.get('completiontime') or 0
    builds = {int(b) for u in match.get('matchurls') or [] for b in BUILD_RE.findall(u.get('url') or '')}
    build = max(builds) if builds else None
    if build is None:
        if start < PATCH_START:
            return None
    elif build not in TARGET_BUILDS:
        return None
    members = match.get('matchhistorymember') or []
    if not members:
        return None
    options = decode_options(match.get('options') or '')
    return {
        'id': match['id'], 'mt': kind, 'start': start, 'dur': max(0, end - start), 'build': build,
        'map': options.get('mapName') or match.get('mapname'), 'mapName': options.get('localizedMapName'),
        'players': [[m['profile_id'], m['teamid'], m['civilization_id'], m['outcome'], m['oldrating'], m['newrating']] for m in members],
    }


def fetch_profile(pid):
    d = get('getRecentMatchHistory', {'title': 'age4', 'profile_ids': f'[{pid}]'})
    return pid, [row for row in (compact(m) for m in d.get('matchHistoryStats') or []) if row]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-profiles', type=int, default=4000, help='players to fetch in this run')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--refresh-seeds', action='store_true', help='re-read the ladders even if seeds are stored')
    ap.add_argument('--refetch-after-hours', type=float, default=20, help='fetch a player again once this old')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = load_state()

    if args.refresh_seeds or not state['seeds']:
        print('Reading ranked ladders', flush=True)
        seeds = {}
        with ThreadPoolExecutor(4) as pool:
            for board, found in pool.map(collect_seeds, RANKED):
                for pid, rating in found.items():
                    seeds.setdefault(str(pid), {})[RANKED[board]] = rating
        state['seeds'], state['seedsAt'] = seeds, int(time.time())
        save_state(state)
    print(f'{len(state["seeds"])} seed players', flush=True)

    seen = set()
    if GAMES.exists():
        with GAMES.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    seen.add(json.loads(line)['id'])
    now = time.time()
    stale = now - args.refetch_after_hours * 3600
    todo = [int(p) for p in state['seeds'] if state['fetched'].get(p, 0) < stale]
    random.Random(17).shuffle(todo)
    todo = todo[:args.max_profiles]
    print(f'{len(seen)} matches stored; fetching {len(todo)} players with {args.workers} workers', flush=True)

    added = done = failed = 0
    began = time.time()
    with GAMES.open('a', encoding='utf-8') as out, ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(fetch_profile, pid) for pid in todo]
        for fut in as_completed(futures):
            try:
                pid, rows = fut.result()
            except Exception as e:
                failed += 1
                if failed <= 20:
                    print('  failed:', repr(e)[:160], flush=True)
                continue
            with lock:
                for row in rows:
                    if row['id'] not in seen:
                        seen.add(row['id'])
                        out.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                        added += 1
                state['fetched'][str(pid)] = int(time.time())
                done += 1
                if done % 100 == 0:
                    out.flush()
                    save_state(state)
                    rate = done / max(1, time.time() - began)
                    print(f'  {done}/{len(todo)} players, {added} new matches, {len(seen)} stored, {failed} failed, {rate:.2f}/s', flush=True)
    state['runs'].append({'at': int(time.time()), 'players': done, 'added': added, 'failed': failed})
    save_state(state)
    print(f'Done: {done} players, {added} new matches, {len(seen)} stored, {failed} failed', flush=True)


if __name__ == '__main__':
    sys.exit(main())
