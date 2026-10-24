"""Export four downloaded 4v4 perspectives without inventing population or gather curves."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ('food','wood','gold','stone')


def export():
    builds = json.loads((ROOT/'data/build-library.json').read_text(encoding='utf-8'))['builds']
    catalog = json.loads((ROOT/'data/game-catalog.json').read_text(encoding='utf-8'))
    records = {str(r['source']['pbgid']):r for kind in ('units','buildings','technologies') for r in catalog[kind]}
    existing=json.loads((ROOT/"data/game-library.json").read_text(encoding="utf-8"))
    by_build={g.get("buildId"):g for g in existing.get("games",[]) if g.get("buildId")}
    by_id={g["id"]:g for g in existing.get("games",[])}
    games=[]
    for build in builds:
        source = next(s for s in build['sources'] if s.get('path','').endswith('.json') and 'summaries' in s['path'])
        data=json.loads(Path(source['path']).read_text(encoding='utf-8'))
        profile_id=int(source['note'].split()[1]);player=next(p for p in data['players'] if p['profileId']==profile_id)
        rows=player['buildOrder'];series=player['resources'];events=[]
        known_names={str(r['pbgid']):r['name'] for r in build['steps']}
        special={181026:'Packed Capital Town Center',181324:'Packed Ger',181326:'Packed Blacksmith',181336:'Packed The Silver Tree',181337:'Packed Steppe Redoubt',2138188:'Dropped melee banner'}
        completion=[]
        def name(row):
            return special.get(row['pbgid']) or records.get(str(row['pbgid']),{}).get('name') or known_names.get(str(row['pbgid'])) or row.get('icon','Unknown').split('/')[-1].replace('_',' ').title()
        for row in rows:
            if row['type'] not in ('Building','Upgrade','Unit'):continue
            kind='Object' if row['pbgid']==2138188 else row['type']
            clean={key:list(row.get(key,[])) for key in ('finished','constructed','destroyed','transformed','packed','unpacked')}
            completion.append({'pbgid':row['pbgid'],'name':name(row),'type':kind,'sourceType':row['type'],**clean})
            times=row['constructed'] if row['type']=='Building' and row['constructed'] else row['finished']
            for t in sorted(set(times)):
                count=times.count(t)
                events.append({'t':t,'kind':{'Building':'building','Upgrade':'technology','Unit':'unit'}.get(kind,'other'),
                               'label':name(row),'pbgid':row['pbgid'],'type':kind,'count':count,'phase':'complete',
                               'meaning':'recorded completion' if row['pbgid'] not in special else 'recorded object state; not proof of new production'})
        for label in ('feudalAge','castleAge','imperialAge'):
            for t in player['actions'].get(label,[]):events.append({'t':t,'kind':'age','label':{'feudalAge':'Feudal Age','castleAge':'Castle Age','imperialAge':'Imperial Age'}[label],'type':'Age','meaning':'recorded action'})
        warnings=['Downloaded historical match perspective, not a simulated plan.',
                  'Per-time fields labelled *Gathered match or precede final resources spent in these downloads. Spending interpretation is inferred from endpoint checks; never plot these fields as gathered.',
                  'Population, army value, gathered resources and worker split are calculated in the app from recorded completions, losses, upgrades, bank, income and spending with installed catalog facts and the engine gather-rate model. They are not recorded game values.',
                  'Unit balances exclude unclassified transformations and are not certified standing armies.']
        accounting={r:{'lastReportedAccounting':series[r+'Gathered'][-1], 'finalSpent':player['totalResourcesSpent'][r],
                       'finalGathered':player['totalResourcesGathered'][r],
                       'sampleToFinalSpentDifference':player['totalResourcesSpent'][r]-series[r+'Gathered'][-1]} for r in RES}
        assert all(v['sampleToFinalSpentDifference']>=0 for v in accounting.values()),'Source accounting interpretation needs review'
        snapshots=[]
        for i,t in enumerate(series['timestamps']):
            units=[]
            for row in rows:
                if row['type']!='Unit' or row['pbgid']==2138188:continue
                produced=sum(v<=t for v in row['finished']);lost=sum(v<=t for v in row['destroyed'])
                if produced or lost:
                    units.append({'pbgid':row['pbgid'],'name':name(row),'produced':produced,'lost':lost,'balance':produced-lost,'countMeaning':'recorded completions minus losses; tier transfers unresolved'})
            vill=[r for r in units if 'villager' in r['name'].lower()]
            snapshots.append({'t':t,'stock':{r:series[r][i] for r in RES},'income':{r:series[r+'PerMin'][i] for r in RES},
                'spent':{r:series[r+'Gathered'][i] for r in RES},'resourcesGathered':None,'population':None,'armyValue':None,
                'villagersObservedBalance':sum(r['balance'] for r in vill) if vill else None,'unitCounts':units})
        games.append({'id':f'aoe4world-{data["gameId"]}-{profile_id}','buildId':build['id'],'title':build['title'],
            'sourceType':'observed','civilization':build['civilization'],'patch':build['patch'],'gameId':data['gameId'],'profileId':profile_id,
            'duration':data['duration'],'map':data['mapName'],'mode':data['leaderboard'],'result':player['result'],
            'source':{'url':f'https://aoe4world.com/players/{profile_id}/games/{data["gameId"]}',
                      'localFile':source['path'],'summaryVersion':data.get('summaryVersion'),'analysisVersion':data.get('analysisVersion')},
            'events':sorted(events,key=lambda e:e['t']),'snapshots':snapshots,'totalResourcesGathered':player['totalResourcesGathered'],'totalResourcesSpent':player['totalResourcesSpent'],'completionRows':completion,'detailsLoaded':True,
            'caveats':warnings,'resourceAccountingEvidence':accounting,'seriesEvidence':{'stock':'resources.<resource>','income':'resources.<resource>PerMin',
                'spent':'resources.<resource>Gathered; inferred spending from endpoint comparisons, not exact gathered','unitCounts':'buildOrder.finished minus buildOrder.destroyed'}})
    for game in games:
        old=by_build.get(game['buildId']) or by_id.get(game['id'])
        if old:
            old.update(game)
            old.pop('detailUrl',None)
        else:existing.setdefault('games',[]).append(game)
        build=next(b for b in builds if b['id']==game['buildId'])
        build['sourceGameId']=game['id']
        build['steps']=[{'timeSeconds':e['t'],'name':e['label'],'type':e.get('type','Age'),'pbgid':e.get('pbgid'),
                         'count':e.get('count',1),'note':e['meaning']} for e in game['events']]
        build['validation']={'kind':'observed-source-audit','engineSupported':False,'timeline':'All recorded completion timestamps. Starts are calculated in the app as completion minus installed base duration; worker allocations are calculated from recorded income and per-villager gather rates.',
            'catalogCoverage':'All trainable units resolved. Packed Mongol buildings and dropped Japanese banner are object states, not additional units.',
            'resourceSeries':'Bank and income directly recorded; spending inferred from provider endpoint checks; per-time gathered derived as bank + spending - starting bank.',
            'armyCounts':'Production-minus-loss balances with completed tier upgrades merged into the current tier. Population (including units in training) and army value use installed population and base costs.'}
    (ROOT/'data/game-library.json').write_text(json.dumps(existing,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    build_data=json.loads((ROOT/'data/build-library.json').read_text(encoding='utf-8'));build_data['builds']=builds
    (ROOT/'data/build-library.json').write_text(json.dumps(build_data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'gamesUpdated':len(games),'preservedCollectionMatches':len(existing.get('matches',[])),
        'snapshots':sum(len(g['snapshots']) for g in games),'events':sum(len(g['events']) for g in games)}))
    return existing


if __name__=='__main__':export()
