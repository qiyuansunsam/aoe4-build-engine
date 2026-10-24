"""Check restored metadata completeness and perspective/source integrity."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
data=read(ROOT/'data/game-library.json')
matches=data['matches'];games=data['games'];by_id={g['id']:g for g in games}
assert len(matches)>=5822 and len({m['id'] for m in matches})==len(matches)
assert len(games)>=816 and len(by_id)==len(games)
assert {p.stem for p in (ROOT/'data/game-perspectives').glob('*.json')}<=set(by_id), 'every sidecar is indexed'
assert sum(m['sourceType']=='online' for m in matches)>=5812
assert sum(not m['perspectiveIds'] for m in matches)>=5600
assert len([g for g in games if g.get('buildId')])==4
assert sum(g['gameId'] is None for g in games)==60
for m in matches:
    for pid in m['perspectiveIds']:
        assert pid in by_id and by_id[pid]['matchId']==m['id']
    assert {p['perspectiveId'] for p in m['players'] if p.get('perspectiveId')}==set(m['perspectiveIds'])
    if m['sourceType']=='local':assert m['startedAt'] is None and m['patch']=='unknown'
RES=('food','wood','gold','stone')
for g in games:
    if g.get('detailUrl'):
        path=ROOT/'data'/g['detailUrl'];full=read(path)
        assert full['id']==g['id'] and full['detailsLoaded'] is True
        assert len(full['events'])==g['eventCount'] and len(full['snapshots'])==g['snapshotCount']
        assert g['events']==[] and g['snapshots']==[]
        assert full['events']==sorted(full['events'],key=lambda e:e['t'])
        assert all(s.get('resourcesGathered') is None for s in full['snapshots'])
        spent_total=full.get('totalResourcesSpent') or {}
        with_spent=[s for s in full['snapshots'] if s.get('spent') is not None]
        if with_spent:
            last=with_spent[-1]['spent']  # provider series can dip (refunds); only the endpoint must stay at or below the final spent
            assert all(last[r] is None or last[r]<=spent_total[r] for r in RES), 'inferred spending endpoint above final spent'
        source=read(Path(full['source']['localFile']))
        if full['gameId']:
            player=next(p for p in source['players'] if p['profileId']==full['profileId'])
            for snapshot in full['snapshots']:
                i=player['resources']['timestamps'].index(snapshot['t'])
                assert snapshot['stock']['food']==player['resources']['food'][i]
        else:assert full['source']['commandsDecoded'] is False
print(f"Restored collection: {sum(m['sourceType']=='online' for m in matches):,} online + {sum(m['sourceType']=='local' for m in matches)} local matches; {len(games)} valid perspectives; sidecars and sampled resources source-checked")
