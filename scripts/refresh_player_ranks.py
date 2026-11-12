"""Refresh the ladder ranks in data/player-profiles.json from the AoE4 World API (Sam, 2026-11-13: "auto rank update
from aoe4 world", "rank update for every push").

One profile call per player already in the snapshot; only the ladder block (modes: rating, rank, rank level, games,
win rate, history), name, avatar, country and last-game time are replaced. Recent games, roles and everything else stay.
A player whose call fails keeps the previous numbers. scripts/deploy_live.py runs this before every build; the page
also reads the same numbers live when a Players page opens (site/players.js, refreshLiveRanks).

Usage: python -X utf8 scripts/refresh_player_ranks.py
"""
import json, pathlib, sys, time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from player_profiles import normalize_profile  # noqa: E402
from player_search import fetch_api  # noqa: E402


def main():
    path = ROOT / 'data/player-profiles.json'
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    updated = 0
    for player in snapshot['players']:
        pid = player['profileId']
        try:
            fresh = normalize_profile(fetch_api(f'https://aoe4world.com/api/v0/players/{pid}'))
        except Exception as error:  # keep the previous ranks for this player
            print(f'{player.get("name")} #{pid}: kept previous ranks ({error})')
            continue
        before = (player.get('modes', {}).get('rm_team') or {}).get('rating')
        player['modes'] = fresh['modes']
        for key in ('name', 'country', 'avatar'):
            if fresh.get(key):
                player[key] = fresh[key]
        if fresh.get('lastGameAt') and str(fresh['lastGameAt']) > str(player.get('lastGameAt') or ''):
            player['lastGameAt'] = fresh['lastGameAt']
        player['modeSnapshotAsOf'] = now
        player['modeSnapshotUnchanged'] = False
        team = fresh['modes'].get('rm_team') or {}
        print(f'{player["name"]} #{pid}: team {before} -> {team.get("rating")} {team.get("rankLevel")}')
        updated += 1
        time.sleep(1)
    if updated:
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        temporary.replace(path)
    print(f'ranks refreshed for {updated} of {len(snapshot["players"])} players')


if __name__ == '__main__':
    main()
