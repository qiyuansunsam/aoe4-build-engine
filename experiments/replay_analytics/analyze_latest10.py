import json
from pathlib import Path

from tactical_probe import own_match

ROOT = Path(__file__).resolve().parent / "data"
AXES = ['Fighting efficiency', 'Aggression', 'Map control', 'Growth', 'Harassment', 'Timing', 'Multitasking', 'Reaction']


def main():
    manifest = json.loads((ROOT/'latest10-manifest.json').read_text(encoding='utf8'))
    reports = []
    by_player = {pid:[] for pid in manifest['players']}
    for entry in manifest['unique_games']:
        game = entry['game']['game_id']
        if not (ROOT/f'summary-{game}.txt').exists() or not (ROOT/f'replay-{game}.parsed.json').exists():
            continue
        report = own_match(game, f'summary-{game}.txt')
        report['players'] = [p for p in report['players'] if game in manifest['players'][str(p['profile_id'])]]
        reports.append(report)
        for p in report['players']:
            by_player[str(p['profile_id'])].append({'game_id':game, **p})
        print('Analyzed',game,flush=True)
    result = {'matches':reports,'players':{pid:{
        'requested_games':manifest['players'][pid], 'analyzed_games':[m['game_id'] for m in matches],
        'name': matches[0]['name'] if matches else pid,
        'radar':{'axes':AXES,'scores':[None]*len(AXES),
                 'status':'Not scored: own-match game-state recording and benchmark calibration pending'},
        'enemy_villagers_killed':None,
        'enemy_villager_kill_status':'Requires hostile attacker-to-victim attribution; own losses are not substituted',
        'matches':matches} for pid,matches in by_player.items()},
        'normalization_plan':'Use transparent per-metric reference ranges matched by civ, map/mode and phase; report raw values and sample counts. No benchmark population acquired yet.',
        'missing_policy':'Keep original latest ten slots, mark missing; never silently substitute older games or score missing metrics as zero'}
    (ROOT/'latest10-analysis.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('Coverage',{pid:len(ms) for pid,ms in by_player.items()},flush=True)


if __name__ == '__main__':
    main()
