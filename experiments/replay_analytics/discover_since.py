"""List (and with --apply add to the manifest) every finished game of the four friends since a date.

Sam, 2026-11-12: "get all of our recent games since dlc came out through record analyser" (Update 17.0, 2026-10-29).

Usage: python -X utf8 discover_since.py [--since 2026-10-29] [--min-seconds 600] [--apply]
Reads each friend's games from the AoE4 World API (newest first, stops at the first game before --since), keeps finished
games of any kind at or after --since, and with --apply appends the new ones to data/ + evidence/ latest10-manifest.json
(unique_games, requested_by = the friends in the game; each friend's id list in manifest['players'] gains the game).
Raw listing is cached in data/discover-since.json. Then collect_latest10.py, record_batch.py, skill_metrics.py.
"""
import argparse, json, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
FRIENDS = [7195780, 1588970, 7999822, 18518902]


def fetch(url):
    req = Request(url, headers={'User-Agent': 'AoE-Build-Crafter/1 (on-demand personal analysis)', 'Accept': 'application/json'})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--since', default='2026-10-29')
    ap.add_argument('--min-seconds', type=int, default=600)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    games = {}
    for pid in FRIENDS:
        for page in range(1, 16):
            raw = fetch(f'https://aoe4world.com/api/v0/players/{pid}/games?page={page}&limit=50&include_alts=false')
            rows = raw.get('games') or []
            older = False
            for g in rows:
                if (g.get('started_at') or '') < args.since:
                    older = True
                    continue
                games.setdefault(g['game_id'], g)
            if older or not rows or raw.get('next_page') is None:
                break
            time.sleep(1)
        time.sleep(1)
    (DATA / 'discover-since.json').write_text(json.dumps(list(games.values()), ensure_ascii=False), encoding='utf-8')
    manifest = json.loads((DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    known = {g['game']['game_id']: g for g in manifest['unique_games']}
    chosen, skipped = [], Counter()
    for g in sorted(games.values(), key=lambda x: x['started_at']):
        present = [p['player']['profile_id'] for t in g.get('teams') or [] for p in t if p['player']['profile_id'] in FRIENDS]
        dur = g.get('duration') or 0
        # Free-for-all has no team sides, which the side / pressure / aggression measures need.
        why = ('ongoing' if g.get('ongoing') or not g.get('duration') else 'short' if dur < args.min_seconds
               else 'ffa' if 'ffa' in str(g.get('kind')) else None)
        print(g['started_at'][:16], g['game_id'], g.get('patch'), f"{g.get('kind'):8}", f"{dur // 60}:{dur % 60:02d}", (g.get('map') or '')[:18].ljust(18),
              len(present), 'KNOWN' if g['game_id'] in known else '', why or '')
        if why:
            skipped[why] += 1
            continue
        chosen.append((g, present))
    print(len(games), 'games since', args.since, '| usable', len(chosen), '| skipped', dict(skipped),
          '| by patch', dict(Counter(g.get('patch') for g, _ in chosen)), '| by kind', dict(Counter(g.get('kind') for g, _ in chosen)),
          '| new', sum(1 for g, _ in chosen if g['game_id'] not in known))
    if not args.apply:
        return
    for g, present in chosen:
        gid = g['game_id']
        if gid in known:
            for pid in present:
                if pid not in known[gid]['requested_by']:
                    known[gid]['requested_by'].append(pid)
        else:
            entry = {'profile_for_download': present[0], 'requested_by': present, 'game': g, 'selection': f'since:{args.since}'}
            manifest['unique_games'].append(entry)
            known[gid] = entry
        for pid in present:
            ids = manifest['players'].setdefault(str(pid), [])
            if gid not in ids:
                ids.append(gid)
    manifest['extended_at'] = datetime.now(timezone.utc).isoformat()
    for path in (DATA / 'latest10-manifest.json', HERE / 'evidence' / 'latest10-manifest.json'):
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print('manifest now', len(manifest['unique_games']), 'games')


if __name__ == '__main__':
    main()
