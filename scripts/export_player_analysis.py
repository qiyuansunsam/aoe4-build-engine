"""Export the replay skill analysis for the site: experiments/replay_analytics/data/skill-analysis.json ->
data/player-analysis.json (embedded by site/build.py as window.PLAYER_ANALYSIS).

Tracked players keep their full per-match evidence (fights, kills, villager kills, threats and responses, Town Center
rows, villager series); every other player of those matches keeps metrics and radar only, so the pool percentiles stay
explainable without shipping every opponent's event lists.

Usage: python -X utf8 scripts/export_player_analysis.py
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'experiments/replay_analytics/data/skill-analysis.json'
MANIFEST = ROOT / 'experiments/replay_analytics/evidence/latest10-manifest.json'
OUT = ROOT / 'data/player-analysis.json'
EVIDENCE = ('fightList', 'kills')
LIST_FIELDS = {'harassment': ('villagerKills', 'raidList'), 'reaction': ('threatList',), 'growth': ('villagerSeries', 'armySeries', 'armyPercentileByMinute'), 'efficiency': ('townCenters',), 'timing': ('armySeries',), 'pressure': ('episodeList',)}


def slim(player):
    p = {k: v for k, v in player.items() if k not in EVIDENCE}
    for section, fields in LIST_FIELDS.items():
        p[section] = {k: v for k, v in p[section].items() if k not in fields}
    return p


def main():
    analysis = json.loads(SRC.read_text(encoding='utf-8'))
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    games = {g['game']['game_id']: g for g in manifest['unique_games']}
    matches = []
    for match in analysis['matches']:
        meta = games.get(match['gameId'], {}).get('game', {})
        matches.append({**match, 'startedAt': meta.get('started_at'), 'mode': meta.get('kind'), 'mapName': meta.get('map'), 'requestedBy': games.get(match['gameId'], {}).get('requested_by', []),
                        'players': [p if p.get('tracked') else slim(p) for p in match['players']]})
    out = {k: v for k, v in analysis.items() if k != 'matches'}
    out['matches'] = matches
    out['manifestFetchedAt'] = manifest.get('fetched_at')
    out['roles'] = manifest.get('roles', {})
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('wrote', OUT, OUT.stat().st_size // 1024, 'KB', len(matches), 'matches')


if __name__ == '__main__':
    main()
