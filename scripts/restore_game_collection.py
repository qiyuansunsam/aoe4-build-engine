"""Restore old match metadata and downloaded perspectives without altering sources."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'mcaoe/data'
RES=('food','wood','gold','stone')
CIV={'abbasid_dynasty':'abbasid','holy_roman_empire':'hre','delhi_sultanate':'delhi','mongol':'mongols','malian':'malians','templar':'knights_templar'}
def civ(x): return CIV.get(x,x or 'unknown')
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def stamp(x):
    return datetime.fromtimestamp(x,timezone.utc).isoformat().replace('+00:00','Z') if isinstance(x,(int,float)) else x

def export():
    existing=read(ROOT/'data/game-library.json')
    curated=[g for g in existing['games'] if g.get('buildId') in {'french-observed-4v4','mongols-observed-4v4','malians-observed-4v4','japanese-observed-4v4'}]
    assert len(curated)==4
    catalog=read(ROOT/'data/game-catalog.json')
    records={str(r['source']['pbgid']):r for k in ('units','buildings','technologies') for r in catalog[k]}
    metadata={d['game_id']:d for d in map(json.loads,(OLD/'strategy/metadata.jsonl').read_text(encoding='utf-8').splitlines())}
    strategy_ids=set(metadata)
    con=sqlite3.connect((OLD/'engine/feed/feed.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    for (payload,) in con.execute('select payload from games'):
        d=json.loads(payload);metadata.setdefault(d['game_id'],d)
    con.close()
    matches={}
    for gid,d in metadata.items():
        players=[{'profileId':p.get('profile_id'),'name':p.get('name','Unknown'),'civilization':civ(p.get('civilization')),'team':team,'rating':p.get('rating'),'rankLevel':p.get('rank_level'),'result':p.get('result','unknown'),'perspectiveId':None} for team,items in enumerate(d.get('teams',[])) for item in items for p in [item.get('player',item)]]
        matches[gid]={'id':f'online-{gid}','gameId':gid,'sourceType':'online','map':d.get('map','Unknown map'),'duration':d.get('duration'),'mode':d.get('kind') or d.get('leaderboard') or 'unknown','patch':str(d.get('patch') or 'unknown'),'startedAt':stamp(d.get('started_at')),'source':{'url':f'https://aoe4world.com/players/{players[0]["profileId"]}/games/{gid}' if players else f'https://aoe4world.com/games/{gid}','localFile':str(OLD/('strategy/metadata.jsonl' if gid in strategy_ids else 'engine/feed/feed.sqlite3'))},'players':players,'perspectiveIds':[],'civilizations':sorted({p['civilization'] for p in players})}
    # Keep matches that were downloaded at runtime through the local API (not in the old mcaoe metadata).
    for m in existing.get('matches',[]):
        if m.get('gameId') is not None and m['gameId'] not in matches and m.get('sourceType')=='online':
            m=dict(m);m['perspectiveIds']=[]
            for pl in m.get('players',[]):pl['perspectiveId']=None
            matches[m['gameId']]=m
    games=list(curated);by_id={g['id']:g for g in games}
    summary_paths=sorted(list((OLD/'strategy/summaries').glob('*.json'))+list((ROOT/'data/downloaded-summaries').glob('*.json')),key=lambda x:x.name)
    skipped=0
    for path in summary_paths:
        d=read(path);gid=d['gameId'];match=matches.get(gid)
        if match is None:skipped+=1;continue
        for p in d.get('players',[]):
            pid=p['profileId'];key=f'aoe4world-{gid}-{pid}';rows=p.get('buildOrder',[]);series=p.get('resources',{})
            def label(row):return records.get(str(row.get('pbgid')),{}).get('name') or row.get('icon','Unknown').split('/')[-1].replace('_',' ').title()
            if key not in by_id:
                events=[];completion=[]
                for row in rows:
                    if row.get('type') not in ('Building','Upgrade','Unit'):continue
                    times=row.get('constructed') if row['type']=='Building' and row.get('constructed') else row.get('finished',[])
                    kind={'Building':'building','Upgrade':'technology','Unit':'unit'}[row['type']]
                    if times:events.append({'t':min(times),'kind':kind,'label':label(row),'pbgid':row.get('pbgid'),'type':row['type'],'meaning':'first recorded completion'})
                    completion.append({'pbgid':row.get('pbgid'),'name':label(row),'type':row['type'],'finished':row.get('finished',[]),'constructed':row.get('constructed',[]),'destroyed':row.get('destroyed',[]),'transformed':row.get('transformed',[])})
                for name,title in [('feudalAge','Feudal Age'),('castleAge','Castle Age'),('imperialAge','Imperial Age')]:
                    for t in p.get('actions',{}).get(name,[]):events.append({'t':t,'kind':'age','label':title,'meaning':'recorded action'})
                ts=series.get('timestamps',[]);indices=[];last=-60
                for i,t in enumerate(ts):
                    if t-last>=60 or i==len(ts)-1:indices.append(i);last=t
                snapshots=[]
                # Provider fields named <res>Gathered end at or below totalResourcesSpent in every checked summary:
                # they are cumulative spending, exposed as inferred spending only when that endpoint check holds.
                spent_total=p.get('totalResourcesSpent') or {}
                spending_ok=all(isinstance(series.get(r+'Gathered'),list) and series[r+'Gathered'] and isinstance(spent_total.get(r),(int,float)) and series[r+'Gathered'][-1]<=spent_total[r] for r in RES)
                for i in indices:
                    value=lambda key:series.get(key,[])[i] if i<len(series.get(key,[])) else None
                    snapshots.append({'t':ts[i],'stock':{r:value(r) for r in RES},'income':{r:value(r+'PerMin') for r in RES},'spent':{r:value(r+'Gathered') for r in RES} if spending_ok else None,'resourcesGathered':None,'population':None,'armyValue':None})
                g={'id':key,'matchId':match['id'],'title':p.get('name','Unknown')+' · '+match['map'],'playerName':p.get('name','Unknown'),'profileId':pid,'gameId':gid,'sourceType':'observed','civilization':civ(p.get('civilization')),'patch':match['patch'],'duration':d.get('duration'),'map':match['map'],'mode':match['mode'],'result':p.get('result','unknown'),'source':{'url':f'https://aoe4world.com/players/{pid}/games/{gid}','localFile':str(path),'summaryVersion':d.get('summaryVersion'),'analysisVersion':d.get('analysisVersion')},'events':sorted(events,key=lambda e:e['t']),'snapshots':snapshots,'completionRows':completion,'totalResourcesGathered':p.get('totalResourcesGathered'),'totalResourcesSpent':p.get('totalResourcesSpent'),'caveats':['Recorded completions, not decoded commands or an executable build order.','Resource snapshots use original timestamps sampled at least one minute apart plus the last snapshot.','Spending is inferred from provider fields named *Gathered that end at or below the final resources spent; per-time gathered totals, population, army value and worker splits are not recorded and the app calculates them at view time.']}
                games.append(g);by_id[key]=g
            g=by_id[key];g['matchId']=match['id'];g['playerName']=p.get('name','Unknown')
            mp=next((x for x in match['players'] if x['profileId']==pid),None)
            if not mp:
                mp={'profileId':pid,'name':p.get('name','Unknown'),'civilization':civ(p.get('civilization')),'team':p.get('team'),'result':p.get('result','unknown')};match['players'].append(mp)
            mp['perspectiveId']=key;match['perspectiveIds'].append(key)
        match['civilizations']=sorted({p['civilization'] for p in match['players']})
    local=[]
    for path in sorted((OLD/'replays/reports').glob('*.json')):
        d=read(path);mid=d['id'];match={'id':mid,'gameId':None,'sourceType':'local','map':'Local replay','duration':d.get('duration'),'mode':'local','patch':'unknown','startedAt':None,'source':{'localFile':str(path),'fileName':d.get('source',{}).get('fileName'),'sha256':d.get('source',{}).get('sha256'),'dateNote':d.get('source',{}).get('dateNote')},'players':[],'perspectiveIds':[],'civilizations':[]}
        for p in d.get('players',[]):
            key=mid+'-'+str(p['id']);events=[{'t':e['time'],'kind':{'upgrade':'technology'}.get(e.get('type'),e.get('type','other')),'label':e.get('name','Unknown'),'pbgid':e.get('pbgid'),'meaning':'recorded stats event'} for e in p.get('events',[]) if e.get('time') is not None]
            snapshots=[{'t':r['time'],'stock':{k:r.get('stock',{}).get(k) for k in RES},'income':{k:r.get('income',{}).get(k) for k in RES},'spent':None,'resourcesGathered':None,'population':None,'armyValue':None} for r in p.get('resourceTimeline',[])]
            pid=p.get('profileId');games.append({'id':key,'matchId':mid,'gameId':None,'profileId':pid,'playerName':p.get('name','Unknown'),'title':p.get('name','Unknown')+' · Local replay','sourceType':'observed','civilization':civ(p.get('civilization')),'patch':'unknown','duration':d.get('duration'),'map':'Local replay','mode':'local','result':p.get('result','unknown'),'source':{'localFile':str(path),'kind':'local-stats','commandsDecoded':False},'events':sorted(events,key=lambda e:e['t']),'snapshots':snapshots,'caveats':['Local stats-derived events, not decoded replay commands.','Match start date, patch, exact worker splits and per-time spending are unknown.']})
            match['players'].append({'profileId':pid,'name':p.get('name','Unknown'),'civilization':civ(p.get('civilization')),'team':p.get('team'),'result':p.get('result','unknown'),'perspectiveId':key});match['perspectiveIds'].append(key)
        match['civilizations']=sorted({p['civilization'] for p in match['players']});local.append(match)
    # Reconstruct matches/perspectives that exist only as sidecars (downloaded at runtime through the local API).
    details=ROOT/'data/game-perspectives';details.mkdir(exist_ok=True)
    indexed={g['id'] for g in games}
    for path in sorted(details.glob('aoe4world-*.json')):
        if path.stem in indexed:continue
        d=read(path)
        if d.get('gameId') is None or not d.get('matchId'):continue
        gid=d['gameId'];match=matches.get(gid)
        if match is None:
            src=d.get('source') if isinstance(d.get('source'),dict) else {}
            match={'id':d['matchId'],'gameId':gid,'sourceType':'online','map':d.get('map','Unknown map'),'duration':d.get('duration'),'mode':d.get('mode','unknown'),'patch':str(d.get('patch') or 'unknown'),'startedAt':None,'source':{'url':src.get('url') or f'https://aoe4world.com/games/{gid}','localFile':str(path),'note':'reconstructed from a runtime-downloaded perspective sidecar'},'players':[],'perspectiveIds':[],'civilizations':[]}
            matches[gid]=match
        g=dict(d);games.append(g);by_id[g['id']]=g;indexed.add(g['id'])
        mp=next((x for x in match['players'] if x.get('profileId')==d.get('profileId')),None)
        if not mp:
            mp={'profileId':d.get('profileId'),'name':d.get('playerName','Unknown'),'civilization':d.get('civilization','unknown'),'team':None,'result':d.get('result','unknown')};match['players'].append(mp)
        mp['perspectiveId']=g['id'];match['perspectiveIds'].append(g['id'])
        match['civilizations']=sorted({p['civilization'] for p in match['players']})
    # Keep browsing metadata small. Timelines are loaded only when a player is inspected/crafted.
    for g in games:
        if g.get('buildId'):continue
        g['snapshotCount']=len(g['snapshots']);g['eventCount']=len(g['events'])
        payload={**g,'detailsLoaded':True}
        (details/(g['id']+'.json')).write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        g['detailUrl']='game-perspectives/'+g['id']+'.json';g['detailsLoaded']=False
        g['events']=[];g['snapshots']=[]
        for key in ('completionRows','totalResourcesGathered','totalResourcesSpent','caveats'):g.pop(key,None)
    ordered=sorted(matches.values(),key=lambda m:m.get('startedAt') or '',reverse=True)+local
    result={'schemaVersion':2,'coverage':{'onlineMatches':len(matches),'localMatches':len(local),'downloadedOnlineMatches':sum(bool(m['perspectiveIds']) for m in matches.values()),'onlinePerspectives':sum(g.get('gameId') is not None for g in games),'localPerspectives':sum(g.get('gameId') is None for g in games),'metadataOnlyMatches':sum(not m['perspectiveIds'] for m in matches.values()),'source':'Existing mcaoe collection; no network download performed'},'matches':ordered,'games':games}
    output=ROOT/'data/game-library.json';output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print(json.dumps({**result['coverage'],'bytes':output.stat().st_size}))
    return result
if __name__=='__main__':export()

