"""Add a player's latest ranked games to the manifest (e.g. a reference pro: Sam, 2026-10-27, "EL.loueMT ... like 5
games from him"). The player joins manifest['players'] with those game ids and manifest['roles'][pid] = role.

Usage: python -X utf8 add_player_games.py PROFILE_ID [--count 5] [--role reference] [--min-seconds 600]
Then collect_latest10.py, record_batch.py, skill_metrics.py.
"""
import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
PATCH = 11308


def fetch(url):
    req = Request(url, headers={'User-Agent': 'AoE-Build-Crafter/1 (on-demand personal analysis)', 'Accept': 'application/json'})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('profile', type=int)
    ap.add_argument('--count', type=int, default=5)
    ap.add_argument('--role', default='reference')
    ap.add_argument('--min-seconds', type=int, default=600)
    ap.add_argument('--team-only', action='store_true', help='ranked team games only (2v2, 3v3, 4v4)')
    ap.add_argument('--kinds', nargs='*', default=None, help='only these game kinds, e.g. rm_4v4')
    args = ap.parse_args()
    manifest = json.loads((DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    # Replace the player's previous selection: drop games only this player requested.
    previous = set(manifest['players'].get(str(args.profile), []))
    manifest['unique_games'] = [g for g in manifest['unique_games'] if not (g['game']['game_id'] in previous and g['requested_by'] == [args.profile])]
    for g in manifest['unique_games']:
        if g['game']['game_id'] in previous and args.profile in g['requested_by'] and len(g['requested_by']) > 1:
            g['requested_by'].remove(args.profile)
    known = {g['game']['game_id']: g for g in manifest['unique_games']}
    profile = fetch(f'https://aoe4world.com/api/v0/players/{args.profile}')
    name = profile.get('name') or str(args.profile)
    chosen = []
    for page in range(1, 11):
        raw = fetch(f'https://aoe4world.com/api/v0/players/{args.profile}/games?page={page}&limit=40&include_alts=false')
        for g in raw.get('games') or []:
            if g.get('ongoing') or g.get('patch') != PATCH or (g.get('duration') or 0) < args.min_seconds or not str(g.get('kind', '')).startswith('rm_'):
                continue
            if args.team_only and g.get('kind') == 'rm_1v1':
                continue
            if args.kinds and g.get('kind') not in args.kinds:
                continue
            chosen.append(g)
            if len(chosen) >= args.count:
                break
        if len(chosen) >= args.count or raw.get('next_page') is None:
            break
        time.sleep(1)
    for g in chosen:
        gid = g['game_id']
        if gid in known:
            if args.profile not in known[gid]['requested_by']:
                known[gid]['requested_by'].append(args.profile)
        else:
            entry = {'profile_for_download': args.profile, 'requested_by': [args.profile], 'game': g, 'selection': f'{args.role}:{name}'}
            manifest['unique_games'].append(entry); known[gid] = entry
        print(' ', gid, g.get('started_at'), g.get('kind'), g.get('map'), f"{g['duration']//60}:{g['duration']%60:02d}")
    manifest['players'][str(args.profile)] = [g['game_id'] for g in chosen]
    manifest.setdefault('roles', {})[str(args.profile)] = args.role
    manifest.setdefault('names', {})[str(args.profile)] = name
    manifest['extended_at'] = datetime.now(timezone.utc).isoformat()
    for path in (DATA / 'latest10-manifest.json', HERE / 'evidence' / 'latest10-manifest.json'):
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'{name} #{args.profile}: {len(chosen)} games added as {args.role}; manifest now {len(manifest["unique_games"])} games')


if __name__ == '__main__':
    main()
