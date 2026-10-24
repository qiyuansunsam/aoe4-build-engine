"""Bounded, cached, user-requested AoE4 World player and match lookups."""
import copy
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from timeline_download import TimelineError, NoRedirect, read, atomic_json, CIV

def fetch_api(url):
    try:
        request=Request(url,headers={'Accept':'application/json','User-Agent':'AoE-Build-Crafter/1 (on-demand public player search)'})
        with build_opener(NoRedirect()).open(request,timeout=20) as response:raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:raise TimelineError('provider_size','The player provider response is too large.',502)
        return json.loads(raw)
    except HTTPError as exc:
        status=429 if exc.code==429 else 404 if exc.code==404 else 502
        raise TimelineError('player_provider_error','AoE4 World could not return this player data. Try again later.',status) from exc
    except (URLError,TimeoutError) as exc:raise TimelineError('player_provider_timeout','AoE4 World did not respond in time. Try again.',504) from exc
    except (ValueError,UnicodeError) as exc:raise TimelineError('invalid_player_data','AoE4 World returned invalid player data.',502) from exc

def profile(player):
    pid=player.get('profile_id')
    if type(pid) is not int or pid<=0:return None
    boards=player.get('leaderboards') or {}
    ranked=[(mode,boards.get(mode) or {}) for mode in ('rm_team','rm_solo')]
    mode,rank=next(((mode,rank) for mode,rank in ranked if rank.get('rating') is not None),ranked[0])
    return {'profileId':pid,'name':player.get('name') or str(pid),'country':player.get('country'),'rankLevel':rank.get('rank_level'),'rating':rank.get('rating'),'rankMode':mode}

def match_record(raw,pid):
    gid=raw.get('game_id')
    if type(gid) is not int or gid<=0:return None
    players=[]
    for team,items in enumerate(raw.get('teams') or []):
        for entry in items:
            p=entry.get('player',entry)
            if type(p.get('profile_id')) is not int:continue
            civ=CIV.get(p.get('civilization'),p.get('civilization') or 'unknown')
            players.append({'profileId':p['profile_id'],'name':p.get('name') or str(p['profile_id']),'civilization':civ,'team':team,'result':p.get('result'),'rating':p.get('rating'),'rankLevel':p.get('rank_level'),'perspectiveId':None})
    return {'id':f'online-{gid}','gameId':gid,'sourceType':'online','map':raw.get('map') or 'Unknown map','duration':raw.get('duration'),'mode':raw.get('kind') or raw.get('leaderboard') or 'unknown','patch':str(raw.get('patch') or 'unknown'),'startedAt':raw.get('started_at'),'source':{'url':f'https://aoe4world.com/players/{pid}/games/{gid}'},'players':players,'perspectiveIds':[],'civilizations':sorted({p['civilization'] for p in players})}

class PlayerSearch:
    def __init__(self,root,lock,transport=fetch_api):self.root=root;self.lock=lock;self.transport=transport;self.cache={}
    def request(self,path,params,ttl):
        url='https://aoe4world.com/api/v0/'+path+('?' + urlencode(params) if params else '')
        cached=self.cache.get(url)
        if cached and time.monotonic()-cached[0]<ttl:return copy.deepcopy(cached[1])
        data=self.transport(url)
        if not isinstance(data,dict):raise TimelineError('invalid_player_data','AoE4 World returned incomplete player data.',502)
        if len(self.cache)>256:self.cache.clear()
        self.cache[url]=(time.monotonic(),data)
        return copy.deepcopy(data)
    def search(self,query):
        query=query.strip()
        if not 3<=len(query)<=100 and not query.isdecimal():raise TimelineError('invalid_query','Enter at least three characters or an exact profile ID.')
        if len(query)>100:raise TimelineError('invalid_query','The player query is too long.')
        if query.isdecimal():
            pid=int(query)
            if not 0<pid<2**63:raise TimelineError('invalid_profile','Enter a valid profile ID.')
            raw=self.request(f'players/{pid}',{},300);rows=[raw]
        else:
            raw=self.request('players/search',{'query':query},300);rows=raw.get('players',[])
        players=[p for row in rows[:50] if isinstance(row,dict) for p in [profile(row)] if p]
        players.sort(key=lambda p:(p['name'].casefold()!=query.casefold(),p['name'].casefold(),p['profileId']))
        return {'query':query,'players':players}
    def games(self,pid,page=1):
        if type(pid) is not int or not 0<pid<2**63:raise TimelineError('invalid_profile','Enter a valid profile ID.')
        if type(page) is not int or not 1<=page<=10000:raise TimelineError('invalid_page','Choose a valid games page.')
        raw=self.request(f'players/{pid}/games',{'page':page,'limit':40,'include_alts':'false'},60)
        if not isinstance(raw.get('games'),list):raise TimelineError('invalid_player_data','AoE4 World returned incomplete games data.',502)
        matches=[m for row in raw['games'][:40] if isinstance(row,dict) for m in [match_record(row,pid)] if m]
        with self.lock:
            try:library=read(self.root/'data/game-library.json')
            except (OSError,ValueError) as exc:raise TimelineError('library_unavailable','The local game collection could not be updated.',503) from exc
            known={m['id']:m for m in library.get('matches',[])}
            for i,match in enumerate(matches):
                old=known.get(match['id'])
                if old:
                    old_players={p.get('profileId'):p for p in old.get('players',[])}
                    for p in match['players']:
                        p['perspectiveId']=old_players.get(p['profileId'],{}).get('perspectiveId')
                    match={**old,**match,'perspectiveIds':old.get('perspectiveIds',[])}
                    old.update(match);matches[i]=old
                else:library.setdefault('matches',[]).append(match);known[match['id']]=match
            coverage=library.setdefault('coverage',{});coverage['onlineMatches']=sum(m.get('sourceType')=='online' for m in library['matches']);coverage['metadataOnlyMatches']=sum(not m.get('perspectiveIds') for m in library['matches'])
            atomic_json(self.root/'data/game-library.json',library)
        more=raw.get('next_page') is not None if 'next_page' in raw else len(raw['games'])>=40
        return {'profileId':pid,'matches':matches,'page':page,'limit':40,'hasMore':more}
