"""Normalize one verified official RGS summary, shared by the patch worker."""
import json
from collections import Counter

def times(row,key):return [t for t in row.get(key,[]) if isinstance(t,(float,int)) and t>=0]

def normalize_game(d,meta,catalog,match_types):
    gid=d['gameId'];rows=[];coverage=[];seen=set()
    official_players={p['profile_id']:p for p in meta['matchhistorymember']}
    assert len({p['profileId'] for p in d['players']})==len(d['players']), 'Duplicate summary profile IDs'
    assert set(official_players)=={p['profileId'] for p in d['players']}, 'Summary/official roster mismatch'
    team_by_owner={p['playerId']:official_players[p['profileId']]['teamid'] for p in d['players']}
    team_sizes=Counter(p['teamid'] for p in official_players.values())
    shape='v'.join(map(str,sorted(team_sizes.values())))
    duration=d['events']['gameLength']
    lost=d['events'].get('lostEntities',[])
    # Keep raw event counts, but remove exact duplicate death records for profile counts.
    unique={json.dumps(e,sort_keys=True):e for e in lost}.values()
    kills=Counter();own_losses=Counter();unattributed=0
    for e in unique:
        if not e.get('hasTarget'):continue
        if 'villager' not in e.get('targetUnitType','').lower():continue
        own_losses[e['targetPlayerId']]+=1
        a=e.get('attackerPlayerId');v=e.get('targetPlayerId')
        if e.get('hasAttacker') and a in team_by_owner and v in team_by_owner and team_by_owner[a]!=team_by_owner[v]:kills[a]+=1
        else:unattributed+=1
    coverage.append({'gameId':gid,'status':'decoded','players':len(d['players']),'sourceSha256':d['source']['sha256'],'rawDeaths':len(lost),'exactDuplicateDeaths':len(lost)-len(list(unique)),'villagerDeathsNotHostileAttributed':unattributed})
    for p in d['players']:
        key=(gid,p['profileId']);assert key not in seen;seen.add(key)
        build=p['buildOrder'];vill=[b for b in build if b['type']=='Unit' and 'villager' in b['icon'].lower()]
        births=sorted(t for b in vill for t in times(b,'finished') if t>0)
        unit_rows=[];upgrade_rows=[];buildings=[]
        for b in build:
            entry={'pbgid':b['pbgid'],'names':catalog.get(b['pbgid'],[]),'icon':b['icon']}
            if b['type']=='Unit':
                t=times(b,'finished');unit_rows.append({**entry,'starting':sum(x==0 for x in t),'nonstartingAppearances':sum(x>0 for x in t),'firstNonstartingSeconds':min((x for x in t if x>0),default=None),'appearancesBy10m':sum(0<x<=600 for x in t) if duration>=600 else None,'appearanceSeconds':t,'destroyedSeconds':times(b,'destroyed')})
            elif b['type']=='Upgrade':upgrade_rows.append({**entry,'completionSeconds':times(b,'finished')})
            elif b['type']=='Building':buildings.append({**entry,'constructionSeconds':times(b,'constructed')})
        tc=sorted(t for b in build if b['type']=='Building' and 'town_center' in b['icon'].lower() for t in times(b,'constructed') if t>0)
        stats=p['stats'];age={};age_anomalies={}
        for n in [2,3,4]:
            v=stats.get(f'age{n}AvailableTimestampMsec')
            value=v/1000 if isinstance(v,(int,float)) and v>0 else None
            if value is not None and value>duration:
                age_anomalies[f'age{n}Seconds']={'rawSeconds':value,'reason':'After recorded gameLength; completion not established'}
                value=None
            age[f'age{n}Seconds']=value
        rows.append({'gameId':gid,'profileId':p['profileId'],'name':p['name'],'civilization':p['civilization'],'teamShape':shape,'matchTypeId':meta.get('matchtype_id'),'matchType':match_types.get(meta.get('matchtype_id')),'startedAt':meta.get('startgametime'),'durationSeconds':duration,'profileEligible10m':duration>=600,**age,'villagerAppearancesBy10m':sum(t<=600 for t in births) if duration>=600 and vill else None,'villagerAppearancesBy15m':sum(t<=900 for t in births) if duration>=900 and vill else None,'firstExtraExplicitTCSeconds':tc[0] if tc else None,'reportedUnitsProduced':stats.get('unitsProduced'),'reportedTechResearched':stats.get('techResearched'),'candidateHostileVillagerDeathCredits':kills[p['playerId']] if p['playerId'] in team_by_owner else None,'ownVillagerDeathEvents':own_losses[p['playerId']],'unitAppearances':unit_rows,'upgradeCompletions':upgrade_rows,'buildingCompletions':buildings,'unknownTimelineEventCount':sum(len(t) for b in build for t in b.get('unknown',{}).values()),'sourceSha256':d['source']['sha256']})
        rows[-1]['ageTimestampAnomalies']=age_anomalies
    return rows,coverage[0]
