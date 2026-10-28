"""Extend the analysis set beyond the latest ten: games where all four tracked players played together, and more of
epsilon's wins (Sam, 2026-10-27: "more winning games by epsilon ... it can be a little skewed to epsilon").

Usage: python -X utf8 select_games.py [--pages 5] [--max-new 12] [--min-seconds 600] [--dry-run]
Reads the tracked players' recent games from the AoE4 World API (a few pages per player, user-requested), keeps
completed team games on the installed patch (11308) longer than --min-seconds (short games are disconnects), ranks:
all four together first, then epsilon wins, newest first; appends the chosen games to data/latest10-manifest.json
(unique_games, with requested_by = the tracked players in the game; per-player lists untouched, aggregates use every
recorded appearance) and records the selection in data/selection.json. Then run collect_latest10.py, record_batch.py.
"""
import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
PATCH = 11308
EPSILON = 7195780


def fetch(url):
    req = Request(url, headers={'User-Agent': 'AoE-Build-Crafter/1 (on-demand personal four-player analysis)', 'Accept': 'application/json'})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pages', type=int, default=5)
    ap.add_argument('--max-new', type=int, default=12)
    ap.add_argument('--min-seconds', type=int, default=600)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--min-present', type=int, default=0,
                    help='instead of all-four/epsilon-win: every game with at least N of the four friends (Sam, 2026-10-28: more '
                         'games for the four; each shared game adds N friend appearances), most friends first, newest first')
    args = ap.parse_args()
    manifest = json.loads((DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    tracked = [int(p) for p in manifest['players'] if manifest.get('roles', {}).get(p) != 'tracked']  # the four friends
    known = {g['game']['game_id'] for g in manifest['unique_games']}
    games = {}
    for pid in tracked:
        for page in range(1, args.pages + 1):
            raw = fetch(f'https://aoe4world.com/api/v0/players/{pid}/games?page={page}&limit=40&include_alts=false')
            rows = raw.get('games') or []
            for g in rows:
                if g.get('ongoing') or g.get('patch') != PATCH or (g.get('duration') or 0) < args.min_seconds or not str(g.get('kind', '')).startswith('rm_'):
                    continue
                games[g['game_id']] = g
            if raw.get('next_page') is None or len(rows) < 40:
                break
            time.sleep(1)
    candidates = []
    for gid, g in games.items():
        if gid in known:
            continue
        members = {p['player']['profile_id']: p['player'] for team in g.get('teams', []) for p in team}
        present = [pid for pid in tracked if pid in members]
        eps_win = EPSILON in members and members[EPSILON].get('result') == 'win'
        if (args.min_present and len(present) >= args.min_present) or (not args.min_present and (len(present) == 4 or eps_win)):
            candidates.append({'game_id': gid, 'started_at': g.get('started_at'), 'duration': g.get('duration'), 'kind': g.get('kind'), 'map': g.get('map'), 'present': present, 'allFour': len(present) == 4, 'epsilonWin': eps_win, 'raw': g})
    candidates.sort(key=lambda c: (not c['allFour'], not c['epsilonWin'], c['started_at'] or ''), reverse=False)
    # all-four first (newest first within), then epsilon wins newest first
    all_four = sorted([c for c in candidates if c['allFour']], key=lambda c: c['started_at'] or '', reverse=True)
    wins = sorted([c for c in candidates if not c['allFour'] and c['epsilonWin']], key=lambda c: c['started_at'] or '', reverse=True)
    chosen = (all_four + wins)[:args.max_new]
    if args.min_present:
        chosen = sorted(candidates, key=lambda c: (-len(c['present']), c['started_at'] or ''), reverse=False)
        chosen = sorted(chosen, key=lambda c: (len(c['present']), c['started_at'] or ''), reverse=True)[:args.max_new]
    print(f'candidates: {len(all_four)} with all four, {len(wins)} other epsilon wins; choosing {len(chosen)}')
    for c in chosen:
        print(' ', c['game_id'], c['started_at'], c['kind'], c['map'], f"{(c['duration'] or 0)//60}:{(c['duration'] or 0)%60:02d}", f"{len(c['present'])} friends" if args.min_present else 'all four' if c['allFour'] else 'epsilon win', c['present'])
    if args.dry_run:
        return
    for c in chosen:
        raw = dict(c['raw'])
        manifest['unique_games'].append({'profile_for_download': EPSILON if EPSILON in c['present'] else c['present'][0], 'requested_by': c['present'], 'game': raw, 'selection': f"{len(c['present'])}-friends" if args.min_present else 'all-four' if c['allFour'] else 'epsilon-win'})
    manifest['extended_at'] = datetime.now(timezone.utc).isoformat()
    (DATA / 'latest10-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (HERE / 'evidence' / 'latest10-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (DATA / f'selection-{datetime.now().strftime("%Y%m%d-%H%M")}.json').write_text(json.dumps({'selected_at': manifest['extended_at'], 'rule': (f'at least {args.min_present} of the four friends, most friends first, newest first' if args.min_present else 'all four tracked players together first, then epsilon wins') + '; completed ranked team games on patch 11308 longer than %d s' % args.min_seconds, 'chosen': [{k: v for k, v in c.items() if k != 'raw'} for c in chosen]}, indent=2), encoding='utf-8')
    print('manifest extended:', len(manifest['unique_games']), 'games')


if __name__ == '__main__':
    main()
