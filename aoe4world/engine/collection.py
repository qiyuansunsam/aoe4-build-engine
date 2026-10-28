"""Resumable single-worker public metadata feed and bounded summary sample.

Run: python -m engine.collection --daemon
Stop gracefully: create data/strategy/STOP (worker removes it on exit).
"""
import argparse
import collections
import datetime as dt
import email.utils
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from .strategy import DIRECTORY, ROOT, refresh, utcnow, write_json

UA='AoE4TrueStats/0.2 (local community analytics; cached bounded public sample)'
MIN_INTERVAL=15
HOURLY_BUDGET=24
FRESH_BUDGET=20
TRACKED_BUDGET=4
FEED_PAGES=4
MODES=('rm_1v1','rm_2v2','rm_3v3','rm_4v4')


class Paused(Exception):
    pass


def read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (ValueError,OSError):
        return default


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch,dt.timezone.utc).isoformat() if epoch else None


def normalize_url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='aoe4world.com':
        raise ValueError('Only https://aoe4world.com player game URLs are accepted')
    match=re.fullmatch(r'/players/(\d+)(?:-[^/]+)?/games/(\d+)(?:/summary)?/?',parsed.path)
    if not match:
        raise ValueError('Expected a player/game URL')
    params={'camelize':'true'}
    sig=urllib.parse.parse_qs(parsed.query).get('sig',[None])[0]
    if sig:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,256}',sig):
            raise ValueError('Invalid signature')
        params['sig']=sig
    return int(match[2]), f'https://aoe4world.com/players/{match[1]}/games/{match[2]}/summary?'+urllib.parse.urlencode(params)


def retry_delay(value, fallback):
    try:
        return max(15,float(value))
    except (TypeError,ValueError):
        try:
            return max(15,email.utils.parsedate_to_datetime(value).timestamp()-time.time())
        except (TypeError,ValueError,AttributeError):
            return fallback


def select_sample(games,limit=FRESH_BUDGET):
    """Round-robin modes, then prefer less represented observed civs, never wins."""
    candidates={g['game_id']:g for g in games if not g.get('ongoing') and g.get('state')=='processed' and g.get('kind') in MODES}
    picked=[];civ_counts=collections.Counter()
    def civs(game):
        return {p.get('player',p).get('civilization') for team in game.get('teams',[]) for p in team}-{None}
    while candidates and len(picked)<limit:
        for mode in MODES:
            options=[g for g in candidates.values() if g['kind']==mode]
            if not options:
                continue
            game=min(options,key=lambda g:(sum(civ_counts[c] for c in civs(g))/max(1,len(civs(g))),hashlib.sha256(str(g['game_id']).encode()).hexdigest()))
            picked.append(game);candidates.pop(game['game_id']);civ_counts.update(civs(game))
            if len(picked)>=limit:
                break
    return picked


class Collector:
    def __init__(self,directory=DIRECTORY):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        for name in ('summaries','queue'):
            (self.directory/name).mkdir(exist_ok=True)
        self.state=read(self.directory/'state.json',{})
        self.state.setdefault('requests',[])
        self.state.setdefault('summarySources',[])
        self.state.setdefault('trackedProfiles',[7999822])
        self.state.setdefault('failures',0)
        self.state.setdefault('skipped',0)
        self.state.setdefault('cooldownUntil',0)
        self.state.setdefault('lastRequest',0)
        if self.state.get('samplingVersion',0)<2:
            self.state['samplingVersion']=2
            self.state['nextFeedSample']=0
            self.state['nextFeed']=0
        self.db=sqlite3.connect(self.directory/'collection.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS games (game_id INTEGER PRIMARY KEY,payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS queue (game_id INTEGER PRIMARY KEY,url TEXT,status TEXT,attempts INTEGER DEFAULT 0,error TEXT,source TEXT)')
        self.started=time.time()
        self.phase='idle'
        self.error=None

    def persist(self):
        write_json(self.directory/'state.json',self.state)
        self.status()

    def status(self,running=True):
        counts=dict(self.db.execute('SELECT status,count(*) FROM queue GROUP BY status').fetchall())
        output=dict(running=running,pid=os.getpid(),heartbeat=utcnow(),startedAt=iso(self.started),source='Recent metadata feed + bounded public summary sample',trackedProfiles=self.state['trackedProfiles'],queued=counts.get('queued',0),downloaded=len(list((self.directory/'summaries').glob('*.json')))+len(list((ROOT/'data/samples').glob('*.json'))),failed=counts.get('failed',0),skipped=counts.get('skipped',0),feedGames=self.db.execute('SELECT count(*) FROM games').fetchone()[0],lastSuccess=self.state.get('lastSuccess'),nextRun=iso(max(time.time(),self.state.get('nextFeed',0))) if self.phase=='idle' else iso(max(time.time(),self.state.get('lastRequest',0)+MIN_INTERVAL,self.state['cooldownUntil'])),rateLimitedUntil=iso(self.state['cooldownUntil']) if self.state['cooldownUntil']>time.time() else None,intervalSeconds=MIN_INTERVAL,summaryBudgetPerHour=HOURLY_BUDGET,summaryRequestsLastHour=len([t for t in self.state['requests'] if t>time.time()-3600]),coverageComplete=False,lastError=self.error or self.state.get('lastError'),phase=self.phase,coverageGaps=self.state.get('coverageGaps',[]),sampling='Initial 20 tracked matches; up to 4 recent-feed candidates/hour; 24 summary requests/hour total; no exhaustive summary crawl')
        output['sampling']='20 fresh-feed summary attempts/hour across modes and civilizations + 4 tracked; 24/hour total; metadata cursor resumes up to 4 pages per cycle'
        output['summaryBudgets']={'fresh':FRESH_BUDGET,'tracked':TRACKED_BUDGET,'total':HOURLY_BUDGET}
        output['feedPagesPerCycle']=FEED_PAGES
        output['feedCursor']=self.state.get('feedCursor')
        output['paused']=read(self.directory/'control.json',{}).get('paused',False)
        output['backfill']=read(self.directory/'backfill.json',None)
        population=read(ROOT/'data/engine/coverage.json',{})
        output['populationGames']=population.get('games',0)
        output['populationFrom']=population.get('periodStart')
        output['populationTo']=population.get('periodEnd')
        output['downloaded']=len({p.stem for folder in (self.directory/'summaries',ROOT/'data/samples') for p in folder.glob('*.json')})
        output['summaryNextRun']=iso(max(time.time(),min(self.state['requests'])+3600)) if len([t for t in self.state['requests'] if t>time.time()-3600])>=HOURLY_BUDGET else iso(max(time.time(),self.state['lastRequest']+MIN_INTERVAL,self.state['cooldownUntil']))
        write_json(self.directory/'status.json',output)
        return output

    def request(self,url,summary=False,source=None):
        if read(self.directory/'control.json',{}).get('paused'):
            raise Paused
        wait=max(0,self.state['lastRequest']+MIN_INTERVAL-time.time(),self.state['cooldownUntil']-time.time())
        if wait:
            self.phase='cooldown' if self.state['cooldownUntil']>time.time() else 'waiting'
            self.status()
            # Short waits permit STOP handling and a fresh heartbeat.
            deadline=time.time()+wait
            while time.time()<deadline:
                if (self.directory/'STOP').exists():
                    raise KeyboardInterrupt
                if read(self.directory/'control.json',{}).get('paused'):
                    raise Paused
                time.sleep(min(5,deadline-time.time()))
                self.status()
        self.state['lastRequest']=time.time()
        if summary:
            self.state['requests']=[t for t in self.state['requests'] if t>time.time()-3600]+[time.time()]
            self.state['summarySources']=[r for r in self.state['summarySources'] if r['at']>time.time()-3600]+[dict(at=time.time(),source=source)]
        self.persist()
        self.phase='downloading' if summary else 'syncing'
        self.status()
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'}),timeout=30) as response:
                body=response.read(10*1024*1024+1)
                if len(body)>10*1024*1024:
                    raise ValueError('Provider response exceeds 10 MB')
                payload=json.loads(body)
            self.state['failures']=0
            self.state['lastSuccess']=utcnow()
            self.state['lastError']=None
            self.error=None
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code==429 or exc.code>=500:
                self.state['failures']+=1
                self.state['cooldownUntil']=time.time()+retry_delay(exc.headers.get('Retry-After'),min(21600,60*2**self.state['failures']))
            elif exc.code==403:
                self.state['cooldownUntil']=time.time()+3600
            self.state['lastError']=f'Provider HTTP {exc.code}; cached data retained'
            self.persist()
            raise
        finally:
            self.persist()

    def enqueue(self,url,source):
        game_id,url=normalize_url(url)
        if (self.directory/'summaries'/f'{game_id}.json').exists() or (ROOT/'data/samples'/f'{game_id}.json').exists():
            return
        self.db.execute('INSERT OR IGNORE INTO queue(game_id,url,status,source) VALUES (?,?,?,?)',(game_id,url,'queued',source))
        self.db.commit()

    def imports(self):
        changed=False
        for path in (self.directory/'queue').glob('*.json'):
            item=read(path,{})
            try:
                if item.get('url'):
                    self.enqueue(item['url'],'explicit URL')
                elif item.get('gameId') and isinstance(item.get('players'),list):
                    write_json(self.directory/'summaries'/f'{int(item["gameId"])}.json',item)
                    changed=True
                path.unlink()
            except (ValueError,TypeError):
                path.rename(path.with_suffix('.invalid'))
        if changed:
            refresh(self.directory)

    def tracked(self):
        if self.state.get('nextTracked',0)>time.time():
            return
        initial=not self.state.get('trackedInitialized')
        for profile in self.state['trackedProfiles']:
            query={'limit':20 if initial else 4}
            since=self.state.get(f'profileSince:{profile}')
            if since:
                query['since']=since
            payload=self.request(f'https://aoe4world.com/api/v0/players/{profile}/games?'+urllib.parse.urlencode(query))
            for game in payload.get('games',[]):
                self.save_metadata(game)
                if not game.get('ongoing') and game.get('state')=='processed':
                    self.enqueue(f'https://aoe4world.com/players/{profile}/games/{game["game_id"]}','tracked history')
            if payload.get('games'):
                self.state[f'profileSince:{profile}']=max(g['started_at'] for g in payload['games'])
        self.state['trackedInitialized']=True
        self.state['nextTracked']=time.time()+3600
        self.db.commit()
        self.persist()

    def save_metadata(self,game):
        if str(game.get('started_at','')).startswith('2026-') and game.get('kind') in ('rm_1v1','rm_2v2','rm_3v3','rm_4v4'):
            self.db.execute('INSERT OR REPLACE INTO games VALUES (?,?)',(game['game_id'],json.dumps(game,separators=(',',':'))))

    def feed(self):
        if self.state.get('nextFeed',0)>time.time():
            return
        cursor=self.state.get('feedCursor') or {}
        since=cursor.get('since') or self.state.get('feedSince') or iso(time.time()-900)
        page=cursor.get('nextPage',1)
        high=cursor.get('maxSeen')
        if dt.datetime.fromisoformat(since.replace('Z','+00:00')).timestamp()<time.time()-7200:
            self.state.setdefault('coverageGaps',[]).append(dict(at=utcnow(),reason='Worker offline over two hours; recent feed resumed. Seasonal dumps cover older population.'))
            since=iso(time.time()-7200)
            page=1;high=None
        games=[]
        for _ in range(FEED_PAGES):
            payload=self.request('https://aoe4world.com/api/v0/games?'+urllib.parse.urlencode({'order':'updated_at','updated_since':since,'per_page':50,'page':page}))
            batch=payload.get('games',[])
            if not isinstance(batch,list):
                raise ValueError('Expected games array; feed cursor retained')
            games.extend(batch)
            for game in batch:
                self.save_metadata(game)
                stamp=game.get('updated_at') or game['started_at']
                high=max(high or stamp,stamp)
            self.db.commit()
            next_page=payload.get('next_page')
            exhausted=not batch or not next_page
            if next_page and int(next_page)>20:
                exhausted=True
                self.state.setdefault('coverageGaps',[]).append(dict(at=utcnow(),reason='Provider 20-page boundary reached; resumed from latest observed timestamp with overlap.'))
            if exhausted:
                self.state['feedSince']=iso(dt.datetime.fromisoformat(high.replace('Z','+00:00')).timestamp()-60) if high else since
                self.state['feedCursor']=dict(since=self.state['feedSince'],nextPage=1,maxSeen=None)
            else:
                page=int(next_page)
                self.state['feedCursor']=dict(since=since,nextPage=page,maxSeen=high)
            # Commit each page so restart/cooldown resumes the same window.
            self.persist()
            if exhausted:
                break
        self.state['coverageGaps']=self.state.get('coverageGaps',[])[-20:]
        if self.state.get('nextFeedSample',0)<=time.time():
            # Avoid selecting existing/imported/failed IDs into the hourly batch.
            known={r[0] for r in self.db.execute('SELECT game_id FROM queue')}
            known.update(int(p.stem) for folder in (self.directory/'summaries',ROOT/'data/samples') for p in folder.glob('*.json') if p.stem.isdigit())
            selected=select_sample([g for g in games if g['game_id'] not in known])
            for game in selected:
                player=next((p.get('player',p) for team in game.get('teams',[]) for p in team if p.get('player',p).get('profile_id')),None)
                if player:
                    self.enqueue(f'https://aoe4world.com/players/{player["profile_id"]}/games/{game["game_id"]}','recent feed sample')
            self.state['nextFeedSample']=time.time()+3600
        export=self.directory/'metadata.jsonl'
        with export.with_suffix('.tmp').open('w',encoding='utf-8') as handle:
            for (record,) in self.db.execute('SELECT payload FROM games ORDER BY game_id'):
                handle.write(record+'\n')
        export.with_suffix('.tmp').replace(export)
        self.state['nextFeed']=time.time()+300
        self.persist()

    def summary(self):
        recent=[t for t in self.state['requests'] if t>time.time()-3600]
        if len(recent)>=HOURLY_BUDGET:
            self.phase='hourly budget'
            self.status()
            return False
        sources=collections.Counter(r['source'] for r in self.state['summarySources'] if r['at']>time.time()-3600)
        rows=self.db.execute("SELECT game_id,url,attempts,source FROM queue WHERE status='queued' ORDER BY CASE source WHEN 'explicit URL' THEN 0 WHEN 'tracked history' THEN 1 ELSE 2 END,game_id DESC").fetchall()
        row=next((r for r in rows if r[3]=='explicit URL' or (r[3]=='tracked history' and sources[r[3]]<TRACKED_BUDGET) or (r[3]=='recent feed sample' and sources[r[3]]<FRESH_BUDGET)),None)
        if not row:
            return False
        game_id,url,attempts,source=row
        try:
            payload=self.request(url,summary=True,source=source)
            if payload.get('gameId')!=game_id or not isinstance(payload.get('players'),list):
                raise ValueError('Expected camelCase game summary')
            write_json(self.directory/'summaries'/f'{game_id}.json',payload)
            self.db.execute("UPDATE queue SET status='downloaded',attempts=attempts+1,error=NULL WHERE game_id=?",(game_id,))
            self.db.commit()
            refresh(self.directory)
            print(f'{utcnow()} summary {game_id} saved',flush=True)
        except urllib.error.HTTPError as exc:
            status='skipped' if exc.code in (401,403,404,410,422) else 'queued' if attempts<3 else 'failed'
            self.db.execute('UPDATE queue SET status=?,attempts=attempts+1,error=? WHERE game_id=?',(status,f'HTTP {exc.code}',game_id))
            self.db.commit()
        except (ValueError,OSError) as exc:
            self.state['cooldownUntil']=max(self.state['cooldownUntil'],time.time()+60)
            self.db.execute('UPDATE queue SET status=?,attempts=attempts+1,error=? WHERE game_id=?',('queued' if attempts<3 else 'failed',str(exc)[:200],game_id))
            self.db.commit()
        self.persist()
        return True

    def run(self,daemon=False):
        refresh(self.directory)
        try:
            while True:
                if (self.directory/'STOP').exists():
                    break
                self.imports()
                if read(self.directory/'control.json',{}).get('paused'):
                    self.phase='paused'
                    self.status()
                    if not daemon:
                        break
                    time.sleep(5)
                    continue
                try:
                    if self.state['cooldownUntil']<=time.time():
                        self.tracked()
                        self.feed()
                        self.summary()
                except Paused:
                    self.phase='paused'
                    self.status()
                    continue
                except (ValueError,OSError) as exc:
                    self.error=str(exc)[:200]
                    self.state['cooldownUntil']=max(self.state['cooldownUntil'],time.time()+60)
                    print(f'{utcnow()} {self.error}',flush=True)
                self.phase='cooldown' if self.state['cooldownUntil']>time.time() else 'idle'
                self.persist()
                if not daemon:
                    break
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            self.status(running=False)
            self.db.close()
            (self.directory/'STOP').unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--daemon',action='store_true')
    parser.add_argument('--directory',type=Path,default=DIRECTORY)
    parser.add_argument('--enqueue')
    args=parser.parse_args()
    if args.enqueue:
        game_id,_=normalize_url(args.enqueue)
        write_json(args.directory/'queue'/f'{game_id}.json',dict(url=args.enqueue))
        print(f'Queued {game_id}')
        return
    # OS-backed lock releases automatically after crash; only one network worker.
    args.directory.mkdir(parents=True,exist_ok=True)
    lock=(args.directory/'worker.lock').open('a+b')
    lock.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            if lock.read(1)==b'':
                lock.write(b'0');lock.flush()
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        raise SystemExit('Collector already running')
    try:
        Collector(args.directory).run(args.daemon)
    finally:
        lock.close()


if __name__=='__main__':
    main()
