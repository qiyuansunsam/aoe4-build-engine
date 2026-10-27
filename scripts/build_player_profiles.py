"""Refresh data/player-profiles.json: profiles and the last 80 games of the reference-game players
from the AoE4 World public API (a handful of user-requested calls, nothing crawled).

Usage: python -X utf8 scripts/build_player_profiles.py [--only PROFILE_ID ...] [--pages N]
Then rebuild the site (python -X utf8 site/build.py) so the page embeds the new snapshot.
"""
import argparse, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from player_profiles import write_snapshot  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--only', type=int, nargs='*', default=None)
parser.add_argument('--pages', type=int, default=2)
args = parser.parse_args()
snapshot = write_snapshot(ROOT, pages=args.pages, only=set(args.only) if args.only else None)
for p in snapshot['players']:
    team = p['modes'].get('rm_team') or {}
    print(f"{p['name']} #{p['profileId']} {p['country']} team {team.get('rating')} {team.get('rankLevel')} games {len(p['recentGames'])} {'tracked' if p.get('tracked') else 'reference ' + str((p.get('reference') or {}).get('buildId'))}")
print('written data/player-profiles.json at', snapshot['generatedAt'])
