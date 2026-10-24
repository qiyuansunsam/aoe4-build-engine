"""On-demand public match summaries for the local Games collection."""
import json
import math
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

RES=('food','wood','gold','stone')
CIV={'abbasid_dynasty':'abbasid','holy_roman_empire':'hre','delhi_sultanate':'delhi','mongol':'mongols','malian':'malians','templar':'knights_templar'}
MAX_DOWNLOAD=10*1024*1024

class TimelineError(Exception):
    def __init__(self,code,message,status=400):
        self.code,self.message,self.status=code,message,status
        super().__init__(message)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def fetch_summary(url):
    try:
        request=Request(url,headers={'Accept':'application/json','User-Agent':'AoE-Build-Crafter/1 (on-demand public match timeline)'})
        with build_opener(NoRedirect()).open(request,timeout=25) as response:
            raw=response.read(MAX_DOWNLOAD+1)
        if len(raw)>MAX_DOWNLOAD:raise TimelineError('timeline_size','The provider timeline is too large.',502)
        return json.loads(raw)
    except HTTPError as exc:
        if exc.code==429:raise TimelineError('provider_rate_limit','The timeline provider is busy. Try again later.',429) from exc
        if exc.code in (400,401,403,404):raise TimelineError('timeline_unavailable','This timeline is not publicly available from the provider.',404) from exc
        raise TimelineError('provider_error','The timeline provider could not complete the request.',502) from exc
    except (URLError,TimeoutError) as exc:raise TimelineError('provider_timeout','The timeline download failed or timed out. Try again.',504) from exc
    except (ValueError,UnicodeError) as exc:raise TimelineError('invalid_timeline','The provider did not return a valid timeline.',502) from exc

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    try:
        tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def public_summary(summary,game_id):
    """Expose only match statistics, never provider internals or local source paths."""
    if not isinstance(summary,dict) or summary.get('gameId')!=game_id or not isinstance(summary.get('players'),list):
        raise TimelineError('invalid_summary','The saved summary does not match this game.',502)
    def number(value):
        return value if type(value) in (int,float) and math.isfinite(value) else None
    def numbers(value):
        return {str(k):number(v) for k,v in value.items() if not str(k).startswith('_')} if isinstance(value,dict) else {}
    def series(value):
        return {str(k):[number(v) for v in values] for k,values in value.items() if not str(k).startswith('_') and isinstance(values,list)} if isinstance(value,dict) else {}
    result={k:summary[k] for k in ('gameId','duration','winReason','startedAt','finishedAt','mapName','mapId','leaderboard','summaryVersion','analysisVersion') if isinstance(summary.get(k),(str,int,float))}
    result['players']=[]
    for player in summary['players']:
        if not isinstance(player,dict):continue
        clean={k:player[k] for k in ('profileId','name','civilization','team','teamName','result','apm') if isinstance(player.get(k),(str,int,float))}
        for key in ('scores','totalResourcesGathered','totalResourcesSpent'):clean[key]=numbers(player.get(key))
        clean['resources']=series(player.get('resources'))
        actions=player.get('actions') or {}
        clean['actions']=series({k:actions[k] for k in ('feudalAge','castleAge','imperialAge') if k in actions})
        clean['buildOrder']=[]
        for row in player.get('buildOrder') or []:
            if not isinstance(row,dict):continue
            item={k:row[k] for k in ('name','type','icon','pbgid') if isinstance(row.get(k),(str,int))}
            item.update(series({k:row[k] for k in ('finished','constructed','destroyed','transformed','packed','unpacked') if k in row}))
            clean['buildOrder'].append(item)
        result['players'].append(clean)
    return result

def saved_summary(root,library,match):
    """Read known cache/source records only; the request never supplies a path."""
    paths=[root/'data/downloaded-summaries'/f'{match.get("gameId")}.json']
    for game in library.get('games',[]):
        if game.get('id') in match.get('perspectiveIds',[]) and game.get('gameId')==match.get('gameId'):
            source=game.get('source') or {}
            if isinstance(source,dict) and isinstance(source.get('localFile'),str):paths.append(Path(source['localFile']))
    invalid=False
    for path in dict.fromkeys(paths):
        try:
            if not path.is_file():continue
            return public_summary(read(path),match.get('gameId'))
        except (OSError,ValueError,TimelineError):invalid=True
    if invalid:raise TimelineError('invalid_summary','The saved summary could not be read. Download it again.',502)
    raise TimelineError('summary_not_downloaded','Download the match summary to view its statistics.',404)

def normalize(summary,match,records,raw_path):
    gid=match['gameId']
    if not isinstance(summary,dict) or summary.get('gameId')!=gid or not isinstance(summary.get('players'),list) or not 1<=len(summary['players'])<=16:
        raise TimelineError('invalid_timeline','The provider returned a different or incomplete match.',502)
    output=[]
    for player in summary['players']:
        if not isinstance(player,dict):raise TimelineError('invalid_timeline','The provider returned invalid player data.',502)
        pid=player.get('profileId')
        if type(pid) is not int or pid<=0 or not isinstance(player.get('buildOrder'),list) or not isinstance(player.get('resources'),dict):
            raise TimelineError('invalid_timeline','The provider response is missing player timeline data.',502)
        rows=player['buildOrder'];series=player['resources'];events=[];completion=[]
        for row in rows:
            if not isinstance(row,dict):continue
            if row.get('type') not in ('Building','Upgrade','Unit'):continue
            label=records.get(str(row.get('pbgid')),{}).get('name') or row.get('name') or row.get('icon','Unknown').split('/')[-1].replace('_',' ').title()
            cleaned={key:[t for t in (row.get(key) if isinstance(row.get(key),list) else []) if isinstance(t,(int,float)) and math.isfinite(t) and t>=0] for key in ('finished','constructed','destroyed','transformed')}
            times=cleaned['constructed'] if row['type']=='Building' and cleaned['constructed'] else cleaned['finished']
            if times:events.append({'t':min(times),'kind':{'Building':'building','Upgrade':'technology','Unit':'unit'}[row['type']],'label':label,'pbgid':row.get('pbgid'),'type':row['type'],'meaning':'first recorded completion'})
            completion.append({'pbgid':row.get('pbgid'),'name':label,'type':row['type'],**cleaned})
        for name,label in [('feudalAge','Feudal Age'),('castleAge','Castle Age'),('imperialAge','Imperial Age')]:
            for t in (player.get('actions') or {}).get(name,[]):
                if isinstance(t,(int,float)) and math.isfinite(t) and t>=0:events.append({'t':t,'kind':'age','label':label,'meaning':'recorded action'})
        ts=series.get('timestamps',[]);ts=ts if isinstance(ts,list) else [];snapshots=[];last=-60
        # Provider fields named <res>Gathered are cumulative spending (they end at or below totalResourcesSpent);
        # expose them as inferred spending only when that endpoint check holds for every resource.
        spent_total=player.get('totalResourcesSpent') if isinstance(player.get('totalResourcesSpent'),dict) else {}
        def _series_ok(r):
            values=series.get(r+'Gathered');total=spent_total.get(r)
            return isinstance(values,list) and values and isinstance(values[-1],(int,float)) and isinstance(total,(int,float)) and values[-1]<=total
        spending_ok=all(_series_ok(r) for r in RES)
        for i,t in enumerate(ts):
            if not isinstance(t,(int,float)) or not math.isfinite(t) or t<0:continue
            if t-last<60 and i!=len(ts)-1:continue
            last=t
            def value(key):
                values=series.get(key,[]);v=values[i] if isinstance(values,list) and i<len(values) else None
                return v if isinstance(v,(int,float)) and math.isfinite(v) else None
            snapshots.append({'t':t,'stock':{r:value(r) for r in RES},'income':{r:value(r+'PerMin') for r in RES},'spent':{r:value(r+'Gathered') for r in RES} if spending_ok else None,'resourcesGathered':None,'population':None,'armyValue':None})
        if not events and not snapshots:continue
        key=f'aoe4world-{gid}-{pid}';civilization=CIV.get(player.get('civilization'),player.get('civilization') or 'unknown')
        output.append({'id':key,'matchId':match['id'],'title':player.get('name','Unknown')+' · '+match.get('map','Recorded match'),'playerName':player.get('name','Unknown'),'profileId':pid,'gameId':gid,'sourceType':'observed','civilization':civilization,'patch':match.get('patch','unknown'),'duration':summary.get('duration') or match.get('duration'),'map':match.get('map','Recorded match'),'mode':match.get('mode','unknown'),'result':player.get('result','unknown'),'source':{'url':f'https://aoe4world.com/players/{pid}/games/{gid}','localFile':str(raw_path),'summaryVersion':summary.get('summaryVersion'),'analysisVersion':summary.get('analysisVersion')},'events':sorted(events,key=lambda e:e['t']),'snapshots':snapshots,'completionRows':completion,'totalResourcesGathered':player.get('totalResourcesGathered'),'totalResourcesSpent':player.get('totalResourcesSpent'),'snapshotCount':len(snapshots),'eventCount':len(events),'detailsLoaded':True,'caveats':['Recorded completions, not decoded commands or an executable build order.','Resource snapshots use original timestamps sampled at least one minute apart plus the last snapshot.','Spending is inferred from provider fields named *Gathered that end at or below the final resources spent; per-time gathered totals, population, army value and worker splits are not recorded and the app derives labelled estimates at view time.']})
    if not output:raise TimelineError('timeline_unavailable','No usable player timeline is available for this match.',404)
    return output

class TimelineDownloader:
    def __init__(self,root,transport=fetch_summary):
        self.root=Path(root);self.transport=transport;self.lock=threading.Lock();self.cooldown=0
    def summary(self,match_id):
        try:library=read(self.root/'data/game-library.json')
        except (OSError,ValueError) as exc:raise TimelineError('library_unavailable','The local match collection is unavailable.',503) from exc
        match=next((m for m in library.get('matches',[]) if m.get('id')==match_id),None)
        if not match:raise TimelineError('match_not_found','This match is not in the local collection.',404)
        return saved_summary(self.root,library,match)
    def download(self,body):
        if not isinstance(body,dict) or not isinstance(body.get('matchId'),str):raise TimelineError('invalid_match','Select a match from Games.')
        if set(body)-{'matchId','profileId'}:raise TimelineError('invalid_request','Only matchId and profileId are accepted.')
        with self.lock:
            try:library=read(self.root/'data/game-library.json')
            except (OSError,ValueError) as exc:raise TimelineError('library_unavailable','The local match collection is unavailable.',503) from exc
            match=next((m for m in library.get('matches',[]) if m.get('id')==body['matchId']),None)
            if not match:raise TimelineError('match_not_found','This match is not in the local collection.',404)
            if match.get('sourceType')!='online' or type(match.get('gameId')) is not int:raise TimelineError('local_match','Local replay timelines cannot be downloaded from the online provider.')
            available={p.get('profileId') for p in match.get('players',[]) if type(p.get('profileId')) is int and p['profileId']>0}
            pid=body.get('profileId')
            if pid is None:pid=next(iter(sorted(available)),None)
            if type(pid) is not int or pid not in available:raise TimelineError('invalid_player','Choose a player from this match.')
            known=[g for g in library.get('games',[]) if g.get('id') in match.get('perspectiveIds',[])]
            selected=next((g for g in known if g.get('profileId')==pid),None)
            try:saved_summary(self.root,library,match);has_summary=True
            except TimelineError:has_summary=False
            if selected and has_summary:
                if not selected.get('detailUrl'):return {'match':match,'perspectives':known,'cached':True}
                path=self.root/'data/game-perspectives'/(selected['id']+'.json')
                if path.exists():
                    atomic_json(self.root/'site/dist/game-perspectives'/(selected['id']+'.json'),read(path))
                    return {'match':match,'perspectives':known,'cached':True}
            if time.monotonic()<self.cooldown:raise TimelineError('download_cooldown','Please wait a few seconds before another timeline download.',429)
            url=f'https://aoe4world.com/players/{pid}/games/{match["gameId"]}/summary?camelize=true'
            self.cooldown=time.monotonic()+3
            try:summary=self.transport(url)
            except TimelineError as exc:
                if exc.status==429:self.cooldown=time.monotonic()+60
                raise
            raw_path=self.root/'data/downloaded-summaries'/f'{match["gameId"]}.json'
            catalog=read(self.root/'data/game-catalog.json');records={str(r.get('source',{}).get('pbgid')):r for k in ('units','buildings','technologies') for r in catalog.get(k,[])}
            try:details=normalize(summary,match,records,raw_path)
            except (TypeError,KeyError,AttributeError,ValueError) as exc:raise TimelineError('invalid_timeline','The provider returned incomplete timeline data.',502) from exc
            if not any(g['profileId']==pid for g in details):raise TimelineError('player_unavailable','The selected player has no usable timeline in this download.',404)
            atomic_json(raw_path,summary)
            by_id={g['id']:g for g in library['games']}
            for g in details:
                # Keep existing curated/accepted identities and their prior evidence unchanged.
                if g['id'] not in by_id or (not by_id[g['id']].get('buildId') and not (self.root/'data/game-perspectives'/(g['id']+'.json')).exists()):
                    for base in (self.root/'data/game-perspectives',self.root/'site/dist/game-perspectives'):atomic_json(base/(g['id']+'.json'),g)
                    lean={k:v for k,v in g.items() if k not in ('completionRows','totalResourcesGathered','totalResourcesSpent','caveats')}
                    lean.update(detailUrl='game-perspectives/'+g['id']+'.json',detailsLoaded=False,events=[],snapshots=[])
                    if g['id'] in by_id:library['games'][library['games'].index(by_id[g['id']])]=lean
                    else:library['games'].append(lean)
                    by_id[g['id']]=lean
                if g['id'] not in match['perspectiveIds']:match['perspectiveIds'].append(g['id'])
                player=next((p for p in match['players'] if p.get('profileId')==g['profileId']),None)
                if not player:
                    player={'profileId':g['profileId'],'name':g['playerName'],'civilization':g['civilization'],'result':g['result']};match['players'].append(player)
                player['perspectiveId']=g['id']
            match['timelineDownloadedAt']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            coverage=library.setdefault('coverage',{});coverage.update(downloadedOnlineMatches=sum(m.get('sourceType')=='online' and bool(m.get('perspectiveIds')) for m in library['matches']),onlinePerspectives=sum(g.get('gameId') is not None for g in library['games']),metadataOnlyMatches=sum(not m.get('perspectiveIds') for m in library['matches']))
            atomic_json(self.root/'data/game-library.json',library)
            return {'match':match,'perspectives':[by_id[key] for key in match['perspectiveIds'] if key in by_id],'cached':False}
