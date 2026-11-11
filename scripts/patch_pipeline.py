"""Resumable publisher-only patch analysis. --limit limits work this run, never selection.

Every stored ranked match of configured patch builds is queued. Missing or expired
publisher summaries remain explicit coverage gaps; this is not a worldwide census.
Compressed RGS and verified bundles survive restarts; decoded temporary JSON does not.
"""
import argparse,gzip,hashlib,importlib.util,json,os,shutil,sqlite3,subprocess,sys,threading,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from patch_normalize import normalize_game
ROOT=Path(__file__).resolve().parents[1]
EXTRACT=ROOT.parent/'games/kb/aoe4/extract'
OLD=EXTRACT/'batch100-20261111';SAMPLE=EXTRACT/'batch1000-20261111'
DEFAULT=ROOT/'.cache/patch-analysis'
API='https://aoe-api.worldsedgelink.com/community/leaderboard/'
DLL=OLD/'publisher-parser/bin/Debug/net8.0/runner.dll'
rate_lock=threading.Lock();last_request=0
class RateLimited(Exception):pass

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for attempt in range(20):
        try:tmp.replace(path);return
        except PermissionError:
            if attempt==19:raise
            time.sleep(.1)
def fetch(url):
    global last_request
    for attempt in range(3):
        with rate_lock:
            time.sleep(max(0,.5-(time.monotonic()-last_request)));last_request=time.monotonic()
        try:
            with urlopen(Request(url,headers={'User-Agent':'Sam-headless-aoe4-patch-analysis/1.0'}),timeout=45) as r:return r.read()
        except HTTPError as e:
            if e.code==429:raise RateLimited('Publisher HTTP429; retry after cooldown')
            if e.code<500 or attempt==2:raise
            time.sleep(2**attempt)
        except Exception:
            if attempt==2:raise
            time.sleep(2**attempt)
def api(route,ids):
    d=json.loads(fetch(API+route+'?'+urlencode({'title':'age4','matchIDs':json.dumps(ids)})))
    if d.get('result',{}).get('code')!=0:raise ValueError(str(d.get('result')))
    return d

def setup(base):
    for name in ['games','raw','work','metadata','snapshots','indexes']: (base/name).mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(base/'manifest.sqlite');db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY, build INTEGER, start INTEGER, state TEXT DEFAULT "pending", attempts INTEGER DEFAULT 0, updated REAL DEFAULT 0, error TEXT, bundle TEXT)')
    if 'priority' not in {r[1] for r in db.execute('PRAGMA table_info(games)')}:db.execute('ALTER TABLE games ADD COLUMN priority INTEGER DEFAULT 0');db.commit()
    return db

def discover(db,builds):
    rows=[]
    tracked_path=ROOT/'data/tracked-player-ids.json'
    tracked=set(load(tracked_path).get('profileIds',[])) if tracked_path.exists() else set()
    with (ROOT/'data/winrates/relic-games.jsonl').open(encoding='utf-8') as f:
        for line in f:
            try:r=json.loads(line)
            except ValueError:continue
            if r.get('build') in builds:rows.append((r['id'],r['build'],r['start'],int(any(p[0] in tracked for p in r['players']))))
    db.executemany('INSERT OR IGNORE INTO games(id,build,start,priority) VALUES(?,?,?,?)',rows);db.executemany('UPDATE games SET priority=? WHERE id=?',[(r[3],r[0]) for r in rows if r[3]]);db.commit()

def status(base,db,phase,**extra):
    counts=dict(db.execute('SELECT state,count(*) FROM games GROUP BY state'))
    d={'phase':phase,'updatedAt':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'counts':counts,'knownGames':sum(counts.values()),'freeBytes':shutil.disk_usage(base).free,'coverage':'All known official ranked matches for configured patch builds; leaderboard-seeded discovery, not a global census.',**extra}
    atomic(base/'status.json',d);print(json.dumps(d),flush=True)

def cache_sources():
    sources={};hist={}
    for old in [OLD,SAMPLE]:
        p=old/'official-research/download-manifest.json'
        if p.exists():sources.update({r['gameId']:r for r in load(p)['results'] if r.get('path')})
        p=old/'official-research/batch-match-history.json'
        if p.exists():hist.update({r['id']:r for r in load(p)['matchHistory']})
    return sources,hist

def decoder():
    spec=importlib.util.spec_from_file_location('rgs_decoder',OLD/'publisher-parser/parse_batch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def bundle_game(base,gid,meta,files,cached,cat,types,parser):
    work=base/'work';source=work/f'{gid}.rgs';decoded=work/f'{gid}.json'
    rawpath=base/'raw'/f'{gid}.rgs.gz';dest=base/'games'/f'{gid}.json.gz'
    if dest.exists():
        with gzip.open(dest,'rt',encoding='utf-8') as f:prior=json.load(f)
        if prior['gameId']==gid and prior.get('verified'):return str(dest),len(prior['playerGames']),'cached-bundle'
    if cached and Path(cached['path']).exists():raw=Path(cached['path']).read_bytes()
    elif rawpath.exists():raw=gzip.decompress(rawpath.read_bytes())
    else:
        candidates=[f for f in files if f.get('matchhistory_id')==gid and f.get('datatype')==1 and f.get('size',0)>0]
        if not candidates:raise FileNotFoundError('No publisher summary available')
        error=None
        for candidate in candidates[:3]:
            try:
                packed=fetch(candidate['url']);raw=gzip.decompress(packed) if packed[:2]==b'\x1f\x8b' else packed;error=None;break
            except RateLimited:raise
            except Exception as e:error=e
        if error:raise error
    if not raw.startswith(b'Relic Chunky\r\n\x1a\0'):raise ValueError('Invalid RGS header')
    digest=hashlib.sha256(raw).hexdigest()
    if cached and cached['sha256']!=digest:raise ValueError('Cached source SHA mismatch')
    if not rawpath.exists():
        tmp=rawpath.with_suffix('.tmp');tmp.write_bytes(gzip.compress(raw,compresslevel=6));tmp.replace(rawpath)
    if hashlib.sha256(gzip.decompress(rawpath.read_bytes())).hexdigest()!=digest:raise ValueError('Compressed archive verification failed')
    previous=SAMPLE/'publisher-parsed'/f'{gid}.json'
    if not previous.exists():previous=OLD/'publisher-parsed'/f'{gid}.json'
    try:
        if previous.exists():d=load(previous)
        else:
            source.write_bytes(raw)
            run=subprocess.run(['dotnet',str(DLL),str(source),str(decoded)],capture_output=True,text=True,encoding='utf-8',timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if run.returncode:raise RuntimeError(run.stderr[-1000:])
            d=load(decoded);d['gameId']=gid
            for p in d['players']:
                p['buildOrder']=parser.normalize(p['unitTimeline']);p['stats'].pop('unitTimeline',None)
        if d['source']['sha256']!=digest:raise ValueError('Decoded SHA mismatch')
        reports={r['profile_id']:r['resulttype'] for r in meta['matchhistoryreportresults']}
        if any(p['outcome'] not in (0,1) or reports.get(p['profile_id'])!=p['outcome'] for p in meta['matchhistorymember']):raise ValueError('Official outcome mismatch')
        rows,coverage=normalize_game(d,meta,cat,types)
        stats_by_id={p['profileId']:p['stats'] for p in d['players']}
        for row in rows:
            for field in ['totalResourcesGathered','totalResourcesSpent']:row[field]=stats_by_id[row['profileId']].get(field)
        result={'version':1,'gameId':gid,'verified':True,'sourceSha256':digest,'officialMatch':meta,'playerGames':rows,'coverage':coverage,'parsed':d}
        tmp=dest.with_suffix('.tmp')
        with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=6) as f:json.dump(result,f,ensure_ascii=False,separators=(',',':'))
        with gzip.open(tmp,'rt',encoding='utf-8') as f:check=json.load(f)
        if check['sourceSha256']!=digest or len(check['playerGames'])!=len(meta['matchhistorymember']):raise ValueError('Bundle roundtrip mismatch')
        tmp.replace(dest)
        save_index(base,result)
        return str(dest),len(rows),'analyzed'
    finally:
        # Only this worker's scratch files are removed, never existing source archives.
        for path in [source,decoded]:
            if path.parent.resolve()!=work.resolve():raise RuntimeError('Unsafe scratch path')
            path.unlink(missing_ok=True)

def compact_index(d):
    from export_tc_milestones import calculate
    tcids=tc_catalog();rows=[];tc_rows={}
    parsed_players={p['profileId']:p for p in d['parsed']['players']}
    for row in d['playerGames']:
        p=parsed_players[row['profileId']];records=[b for b in p['buildOrder'] if b['pbgid'] in tcids]
        maximum,milestones,underflow=calculate(records)
        unknown=[b['pbgid'] for b in p['buildOrder'] if b['pbgid'] not in tcids and ('town_center' in b.get('icon','') or 'town_centre' in b.get('icon',''))]
        capital=any('capital' in tcids[r['pbgid']] and r['constructed'] for r in records)
        verified=capital and not unknown and not underflow and not any(r.get('unknown') for r in records)
        tcrow={'maximum':maximum if verified else None,'milestones':milestones,'status':'verified-timeline' if verified else 'incomplete','hasCapital':capital,'underflow':underflow,'unknownIds':unknown,'sourceSha256':row['sourceSha256']}
        tc_rows[str(d['gameId'])+':'+str(row['profileId'])]=tcrow
        compact={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
        for field in ['totalResourcesGathered','totalResourcesSpent']:compact[field]=p['stats'].get(field)
        compact['unitAppearances']=[{k:u[k] for k in ['pbgid','starting','nonstartingAppearances']} for u in row['unitAppearances']]
        compact['upgradeCompletions']=[{k:u[k] for k in ['pbgid','completionSeconds']} for u in row['upgradeCompletions']]
        compact['buildingCompletions']=[{k:u[k] for k in ['pbgid','names','constructionSeconds']} for u in row['buildingCompletions']]
        rows.append(compact)
    return {'gameId':d['gameId'],'officialMatch':d['officialMatch'],'playerGames':rows,'tcRows':tc_rows}

from functools import lru_cache
@lru_cache(maxsize=1)
def tc_catalog():
    return {b['source']['pbgid']:b['id'] for b in load(ROOT/'data/game-catalog.json')['buildings'] if 'town_center' in b['id']}

def save_index(base,d):
    path=base/'indexes'/f"{d['gameId']}.json.gz";tmp=path.with_suffix('.tmp')
    result=compact_index(d)
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=3) as f:json.dump(result,f,ensure_ascii=False,separators=(',',':'))
    tmp.replace(path)
    return result

def export_snapshot(base,db):
    destination=base/'snapshots';rows_path=destination/'player-games.json';history_path=destination/'batch-match-history.json'
    tcpath=destination/'tc-milestones.json';tctemp=tcpath.with_suffix('.tmp')
    rows_temp=rows_path.with_suffix('.tmp');hist_temp=history_path.with_suffix('.tmp');n=0;players=0
    with rows_temp.open('w',encoding='utf-8') as out,hist_temp.open('w',encoding='utf-8') as hist,tctemp.open('w',encoding='utf-8') as tc_out:
        out.write('[');hist.write('{"matchHistory":[');tc_out.write('{"rows":{')
        for gid,path in db.execute('SELECT id,bundle FROM games WHERE state="complete" ORDER BY id'):
            index=base/'indexes'/f'{gid}.json.gz'
            if index.exists():
                with gzip.open(index,'rt',encoding='utf-8') as f:d=json.load(f)
            else:
                with gzip.open(path,'rt',encoding='utf-8') as f:d=save_index(base,json.load(f))
            if n:hist.write(',')
            json.dump(d['officialMatch'],hist,ensure_ascii=False,separators=(',',':'));n+=1
            for row in d['playerGames']:
                if players:out.write(',');tc_out.write(',')
                key=str(gid)+':'+str(row['profileId'])
                tc_out.write(json.dumps(key)+':');json.dump(d['tcRows'][key],tc_out,separators=(',',':'))
                json.dump(row,out,ensure_ascii=False,separators=(',',':'));players+=1
        out.write(']');hist.write('],"profiles":[]}');tc_out.write('}}')
    rows_temp.replace(rows_path);hist_temp.replace(history_path);tctemp.replace(tcpath)
    atomic(destination/'snapshot.json',{'games':n,'playerGames':players,'generatedAt':datetime.now(timezone.utc).isoformat()})
    return n,players

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,default=DEFAULT);ap.add_argument('--builds',type=int,nargs='+',default=[12182,12260]);ap.add_argument('--limit',type=int,default=0);ap.add_argument('--workers',type=int,default=3);ap.add_argument('--watch',action='store_true');ap.add_argument('--export',action='store_true');ap.add_argument('--skip-cached',action='store_true');ap.add_argument('--import-cached',action='store_true');ap.add_argument('--refresh-discovery',action='store_true');ap.add_argument('--discovery-hours',type=float,default=20);ap.add_argument('--discovery-profiles',type=int,default=4000);ap.add_argument('--publish-script',type=Path);ap.add_argument('--publish-every',type=int,default=500);ap.add_argument('--min-free-gb',type=float,default=20);args=ap.parse_args()
    base=args.base.resolve();db=setup(base);discover(db,args.builds)
    if args.export:print(export_snapshot(base,db));return
    import msvcrt
    worker_lock=(base/'worker.lock').open('a+b');worker_lock.seek(0);worker_lock.write(b'0');worker_lock.flush();worker_lock.seek(0)
    try:msvcrt.locking(worker_lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise SystemExit('Another patch worker owns this base directory')
    cat={}
    for kind,entries in load(ROOT/'data/game-catalog.json').items():
        if kind in ['units','buildings','technologies']:
            for u in entries:cat.setdefault(u['source']['pbgid'],[]).append({'name':u['name'],'id':u['id'],'category':kind})
    definitions=load(OLD/'official-research/publisher-definitions.json');types={m['id']:m.get('name') for m in definitions['matchTypes']}
    cached,hist=cache_sources();parser=decoder();done=0;last_publish=0;discovery_process=None;discovery_log=None;last_discovery=0
    import atexit
    def stop_discovery():
        if discovery_process is not None and discovery_process.poll() is None:
            discovery_process.terminate()
            try:discovery_process.wait(timeout=10)
            except subprocess.TimeoutExpired:discovery_process.kill()
        if discovery_log:discovery_log.close()
    atexit.register(stop_discovery)
    while True:
        if (base/'STOP').exists():status(base,db,'stopped');return
        if args.refresh_discovery and (discovery_process is None or discovery_process.poll() is not None) and time.time()-last_discovery>=args.discovery_hours*3600:
            if discovery_log:discovery_log.close()
            discovery_log=(base/'discovery.log').open('a',encoding='utf-8')
            discovery_process=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'scripts/collect_relic_matches.py'),'--max-profiles',str(args.discovery_profiles),'--workers','2','--seed-min-rating','0','--refetch-after-hours',str(args.discovery_hours)],cwd=ROOT,stdout=discovery_log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            last_discovery=time.time();atomic(base/'discovery-status.json',{'pid':discovery_process.pid,'startedAt':last_discovery})
        discover(db,args.builds)
        todo=[r[0] for r in db.execute('SELECT id FROM games WHERE build IN ('+','.join('?' for _ in args.builds)+') AND (state="pending" OR (state="failed" AND updated<?)) ORDER BY priority DESC,start DESC',(*args.builds,time.time()-86400)) if not(args.skip_cached and r[0] in cached) and (not args.import_cached or r[0] in cached)]
        todo=todo[:min(1000,max(0,args.limit-done)) if args.limit else 1000]
        if not todo:
            status(base,db,'waiting' if args.watch and not args.limit else 'idle',processedThisRun=done)
            if not args.watch or args.limit:return
            time.sleep(60);continue
        for start in range(0,len(todo),10):
            if (base/'STOP').exists():status(base,db,'stopped');return
            if shutil.disk_usage(base).free<args.min_free_gb*1024**3:status(base,db,'storage-paused');return
            batch=todo[start:start+10]
            try:
                missing=[gid for gid in batch if gid not in hist and not(base/'metadata'/f'{gid}.json').exists()]
                if missing:
                    for m in api('getMatchHistory',missing).get('matchHistory',[]):atomic(base/'metadata'/f"{m['id']}.json",m)
                metas={gid:hist.get(gid) or (load(base/'metadata'/f'{gid}.json') if (base/'metadata'/f'{gid}.json').exists() else None) for gid in batch}
                remote=[gid for gid in batch if gid not in cached and not(base/'raw'/f'{gid}.rgs.gz').exists()]
                files=api('getReplayFiles',remote).get('replayFiles',[]) if remote else []
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    futures={pool.submit(bundle_game,base,gid,metas[gid],files,cached.get(gid),cat,types,parser):gid for gid in batch if metas[gid]}
                    for task in as_completed(futures):
                        gid=futures[task]
                        try:
                            path,player_count,origin=task.result();db.execute('UPDATE games SET state="complete",updated=?,bundle=?,error=NULL,attempts=attempts+1 WHERE id=?',(time.time(),path,gid))
                        except RateLimited:raise
                        except Exception as e:db.execute('UPDATE games SET state="failed",updated=?,error=?,attempts=attempts+1 WHERE id=?',(time.time(),str(e)[:500],gid))
                        db.commit();done+=1
                    for gid in batch:
                        if not metas[gid]:db.execute('UPDATE games SET state="failed",updated=?,error="Official metadata unavailable",attempts=attempts+1 WHERE id=?',(time.time(),gid));done+=1
                    db.commit()
                status(base,db,'analyzing',processedThisRun=done)
                if args.publish_script and done-last_publish>=args.publish_every:
                    export_snapshot(base,db)
                    subprocess.run([sys.executable,'-X','utf8',str(args.publish_script),'--base',str(base)],cwd=ROOT,check=True)
                    last_publish=done
            except RateLimited:
                status(base,db,'rate-limited',retryAfterSeconds=3600)
                if not args.watch:return
                for _ in range(60):
                    if (base/'STOP').exists():status(base,db,'stopped');return
                    time.sleep(60)
                break
            except Exception as e:
                status(base,db,'error',error=str(e)[:500])
                if not args.watch:raise
                time.sleep(60);break
        if args.limit and done>=args.limit:status(base,db,'idle',processedThisRun=done);return

if __name__=='__main__':main()
