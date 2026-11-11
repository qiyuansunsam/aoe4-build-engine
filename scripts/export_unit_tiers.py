"""Observed win rates and independent game usage from publisher files and installed catalog."""
import argparse,hashlib,json,re
from collections import defaultdict
from pathlib import Path
from build_winrates import BANDS,rating_in_band
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'games/kb/aoe4/extract/batch1000-20261111'
SOURCE=BASE/'independent-profiles/player-games.json'
HISTORY=BASE/'official-research/batch-match-history.json'
CATALOG=ROOT/'data/game-catalog.json'
META=ROOT/'data/catalog-enrichment.json'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def combat(u):return 'military' in u.get('classes',[]) and not re.search(r'(?:dummy|scout|villager|trade_cart|fishing_boat|transport|scholar|priest|monk)',u['id'])
def landmark(u):return u['id'].startswith(('building_landmark_','building_house_of_wisdom_','building_wonder_')) or u['id']=='building_defense_fortress_tem'
def significant(u):return ('town_center' in u['id'] and 'capital' not in u['id']) or 'keep' in u['id']
def band(score,n):
    if n<30:return 'Unrated'
    return 'S' if score>=.60 else 'A' if score>=.55 else 'B' if score>=.50 else 'C' if score>=.45 else 'D'
def main():
    global SOURCE,HISTORY
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--history',type=Path,default=HISTORY)
    parser.add_argument('--tc-cache',type=Path,default=ROOT/'.cache/tc-milestones.json')
    parser.add_argument('--external-evidence',action='store_true')
    args=parser.parse_args();SOURCE=args.source;HISTORY=args.history
    tc_cache=load(args.tc_cache)['rows']
    games=load(SOURCE);catalog=load(CATALOG);meta=load(META);history=load(HISTORY)
    assert len(games)==len({(g['gameId'],g['profileId']) for g in games}), 'Duplicate player-game inputs'
    records={};by_pbg=defaultdict(list)
    for kind in ['units','buildings','technologies']:
        for u in catalog[kind]:records[u['id']]=u|{'category':kind};by_pbg[u['source']['pbgid']].append(records[u['id']])
    # The UI metadata does not always join every upgrade tier (e.g. Camel Rider).
    # Union explicit installed squad/entity transitions before counting game appearances.
    unit_records={u['id']:u for u in catalog['units']};parents={key:key for key in unit_records}
    def find(key):
        while parents[key]!=key:
            parents[key]=parents[parents[key]];key=parents[key]
        return key
    def union(left,right):
        if right in unit_records and unit_records[left]['civilization']==unit_records[right]['civilization']:
            parents[find(right)]=find(left)
    for key,u in unit_records.items():
        family=meta.get(key,{}).get('familyKey')
        if family:union(key,family)
        for transition in u.get('tierTransitions',[]):
            for field in ['squad','entity']:
                target=transition.get(field)
                if target:union(key,target)
    components=defaultdict(list)
    for key in unit_records:components[find(key)].append(key)
    unit_families={}
    for members in components.values():
        base=min(members,key=lambda key:(unit_records[key].get('age') or 99,key))
        for key in members:unit_families[key]=base
    generic_names={'Spearman','Archer','Crossbowman','Man-at-Arms','Horseman','Knight','Lancer','Scout','Battering Ram','Mangonel','Springald','Trebuchet','Bombard','Handcannoneer','Culverin','Ribauldequin'}
    def plain(name):return re.sub(r'^(?:Elite|Veteran|Hardened|Early|Vanguard)\s+','',name)
    representatives={}; availability=defaultdict(set)
    for uid,u in unit_records.items():
        name=plain(records[unit_families[uid]]['name'])
        key=('generic-unit:'+name) if name in generic_names else u['civilization']+':'+name
        representatives.setdefault(key,records[unit_families[uid]])
        unit_families[uid]=key
        availability[key].add(u['civilization'])
    # Common definitions identify generic upgrades; match localized identity and
    # effect arguments, preserving improved upgrades and distinct levels.
    def tech_signature(u):
        return (u.get('nameLocalizationId'),u.get('descriptionTemplate'),json.dumps(u.get('descriptionArguments'),sort_keys=True))
    common={tech_signature(u):u['id'] for u in catalog['technologies'] if u['civilization']=='common' and u.get('nameLocalizationId') and u.get('descriptionTemplate') and not u['name'].startswith('Upgrade to ')}
    tech_families={u['id']:common.get(tech_signature(u),u['id']) for u in catalog['technologies']}
    upgrade_names={}
    for u in catalog['units']:
        for transition in u.get('tierTransitions',[]):
            target=unit_records.get(transition.get('squad')) or unit_records.get(transition.get('entity'))
            if target and transition.get('upgrade') and target['name'].startswith(('Elite ', 'Veteran ', 'Hardened ', 'Early ', 'Vanguard ')):
                upgrade_names.setdefault(transition['upgrade'],set()).add(target['name'])
    outcomes={};game_ratings={}
    for game in history['matchHistory']:
        ratings=[p.get('oldrating') for p in game['matchhistorymember']]
        game_ratings[game['id']]=sum(ratings)/len(ratings) if ratings and all(isinstance(r,(int,float)) for r in ratings) else None
        reported={x['profile_id']:x['resulttype'] for x in game['matchhistoryreportresults']}
        for p in game['matchhistorymember']:
            if p['outcome'] in (0,1) and reported.get(p['profile_id'])==p['outcome']:outcomes[(game['id'],p['profile_id'])]=p['outcome']
    all_civs={g['civilization'] for g in games}
    for u in catalog['technologies']:
        key=tech_families[u['id']]
        availability[key].update(all_civs if u['civilization']=='common' else [u['civilization']])
    for u in catalog['buildings']:
        availability[u['id']].add(u['civilization'])
        if 'keep' in u['id'] and not landmark(u):availability['generic-keep'].add(u['civilization'])
    groups=defaultdict(list)
    for g in games:
        if g['durationSeconds']>=600:
            for band_def in BANDS:
                if band_def['id']=='all' or rating_in_band(game_ratings.get(g['gameId']),band_def):
                    groups[(band_def['id'],g['civilization'],g['matchTypeId'])].append(g)
                    groups[(band_def['id'],'__all__',g['matchTypeId'])].append(g)
    output=[];audit=[]
    for (rank_band,civ,mode),sample in sorted(groups.items()):
        for category in ['units','technologies','buildings']:
            items={};unknown=0;unknown_games=set();valid_outcomes=0;contributing=0;unresolved_tc=0
            for g in sample:
                outcome=outcomes.get((g['gameId'],g['profileId']))
                if outcome is None:continue
                valid_outcomes+=1;local={};tc_events=[];capital_base=None
                has_capital=any(any('town_center_capital' in n['id'] for n in b['names']) and b['constructionSeconds'] for b in g['buildingCompletions'])
                raw_rows=g['unitAppearances'] if category=='units' else g['upgradeCompletions'] if category=='technologies' else g['buildingCompletions']+g['upgradeCompletions']
                for row in raw_rows:
                    count=row['nonstartingAppearances'] if category=='units' else sum(t>=0 if category=='buildings' else t>0 for t in row.get('completionSeconds',row.get('constructionSeconds',[])))
                    if count<=0:continue
                    candidates=by_pbg.get(row['pbgid'],[]);u=next((x for x in candidates if x['civilization']==g['civilization']),None)
                    if u is None and len(candidates)==1:u=candidates[0]
                    if u is None:unknown+=1;unknown_games.add((g['gameId'],g['profileId']));continue
                    if category=='units' and (u['category']!='units' or not combat(u)):continue
                    if category=='technologies' and (u['category']!='technologies' or u['id'].startswith('upgrade_add_')):continue
                    wing=u['category']=='technologies' and u['id'].startswith('upgrade_add_')
                    if category=='buildings':
                        if not wing and (u['category']!='buildings' or not (landmark(u) or significant(u) or 'town_center_capital' in u['id'])):continue
                        if 'town_center' in u['id']:
                            if 'capital' in u['id']:capital_base=u
                            else:tc_events.extend((t,u) for t in row.get('constructionSeconds',[]) if t>0)
                            continue
                    key=unit_families[u['id']] if category=='units' else tech_families[u['id']] if category=='technologies' else u['id']
                    base=representatives.get(key,records.get(key,u))
                    if category=='units' and key.startswith('generic-unit:'):base=base|{'civilization':'generic'}
                    if category=='buildings' and wing:
                        key='wing:'+u['civilization']+':'+u['name'];base=u
                        availability[key].add(u['civilization'])
                    elif category=='buildings' and 'keep' in u['id'] and not landmark(u):
                        key='generic-keep';base=u|{'name':'Keep','civilization':'generic'}
                    v=local.setdefault(key,{'base':base,'count':0,'forms':set()});v['count']+=count;v['forms'].add(u['id'])
                tc=tc_cache.get(str(g['gameId'])+':'+str(g['profileId']),{})
                if category=='buildings' and capital_base and tc.get('status')=='verified-timeline':
                    for number in range(1,min(3,tc['maximum'])+1):
                        key='generic-tc-'+str(number)
                        label=['Town Center','Second Town Center','Third Town Center'][number-1]
                        local[key]={'base':capital_base|{'name':label,'civilization':'generic'},'count':1,'forms':{capital_base['id']}}
                        availability[key].update(all_civs)
                elif category=='buildings' and tc_events:unresolved_tc+=len(tc_events)
                total=sum(v['count'] for v in local.values())
                if not total:continue
                contributing+=1
                for key,v in local.items():
                    base=v['base']
                    name=re.sub(r'^(?:Elite|Veteran|Hardened|Early|Vanguard)\s+','',base['name']) if category=='units' else base['name']
                    if category=='technologies' and name.startswith('Upgrade to ') and key in upgrade_names:
                        name=' / '.join(sorted(upgrade_names[key]))+' upgrade'
                    if category=='technologies' and 'Emplacement' in name:
                        for prefix,label in [('upgrade_keep_','Keep'),('upgrade_outpost_','Outpost'),('upgrade_wooden_castle_','Wooden Fortress'),('upgrade_barbican_','Barbican')]:
                            if key.startswith(prefix):
                                name=label+' '+name;break
                    item=items.setdefault(key,{'id':key,'catalogId':base['id'],'civilization':'generic' if category=='technologies' and base['civilization']=='common' else base['civilization'],'name':name,'usedIn':0,'wins':0,'losses':0,'observedEvents':0,'forms':set(),'contributions':[]})
                    item['usedIn']+=1;item['wins']+=outcome;item['losses']+=1-outcome;item['observedEvents']+=v['count'];item['forms'].update(v['forms'])
                    item['contributions'].append({'gameId':g['gameId'],'profileId':g['profileId'],'count':v['count'],'total':total,'share':v['count']/total if category=='units' else 1,'civilization':g['civilization'],'win':outcome})
            rows=[]
            for item in items.values():
                contributions=item['contributions']
                win_weight=sum(x['share']*x['win'] for x in contributions)
                loss_weight=sum(x['share']*(1-x['win']) for x in contributions)
                score=win_weight/(win_weight+loss_weight)
                supported=availability[item['id']]|{x['civilization'] for x in contributions}
                eligible=sum(g['civilization'] in supported and (g['gameId'],g['profileId']) in outcomes and (not item['id'].startswith('generic-tc-') or tc_cache.get(str(g['gameId'])+':'+str(g['profileId']),{}).get('status')=='verified-timeline') for g in sample)
                average_share=sum(x['share'] for x in contributions)/len(contributions)
                assert item['wins']+item['losses']==item['usedIn']
                assert sum(x['win'] for x in contributions)==item['wins']
                audit.append({'rankBand':rank_band,'category':category,'civilization':civ,'matchTypeId':mode,'id':item['id'],'score':score,'contributions':contributions})
                rows.append({k:v for k,v in item.items() if k not in ('forms','contributions')}|{'winRate':score,'eligibleCivilizations':sorted(supported),'usageRate':item['usedIn']/eligible,'eligiblePlayerGames':eligible,'averageShareWhenUsed':average_share if category=='units' else None,'calculationGames':[[x['gameId'],x['profileId'],x['count'],x['total'],x['win']] for x in contributions] if category=='units' else [],'winWeight':win_weight,'lossWeight':loss_weight,'rawWinRate':item['wins']/item['usedIn'],'tier':band(score,item['usedIn']),'forms':sorted(item['forms']),'matchesUsed':len({x['gameId'] for x in contributions}),'playersUsing':len({x['profileId'] for x in contributions})})
            if category=='units':
                duplicates=defaultdict(list)
                for item in rows:duplicates[(item['civilization'],item['name'])].append(item)
                for similar in duplicates.values():
                    if len(similar)<2:continue
                    for item in similar:
                        uid=item['catalogId']
                        item['variantLabel']=('Field-built' if 'buildable' in uid or uid.startswith('unit_ram_') else 'Workshop' if 'workshop' in uid or 'mangonel' in uid or 'springald' in uid else 'Free landmark unit' if 'king_free' in uid else 'Trained' if 'abbey_king' in uid else 'Khaganate Palace' if 'khaganate' in uid else 'Double production' if 'double' in uid else 'Separate unit form')
            rows.sort(key=lambda x:(-x['winRate'],-x['usedIn'],x['name']))
            if args.external_evidence or len(games)>10000:
                folder=ROOT/'data/tier-evidence';folder.mkdir(exist_ok=True)
                for item in rows:
                    if not item['calculationGames']:continue
                    payload=json.dumps(item.pop('calculationGames'),separators=(',',':'))
                    filename=hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]+'.json'
                    (folder/filename).write_text(payload,encoding='utf-8')
                    item['calculationUrl']='data/tier-evidence/'+filename
            counts={c:sum(g['civilization']==c and (g['gameId'],g['profileId']) in outcomes for g in sample) for c in {g['civilization'] for g in sample}}
            tc_counts={c:sum(g['civilization']==c and (g['gameId'],g['profileId']) in outcomes and tc_cache.get(str(g['gameId'])+':'+str(g['profileId']),{}).get('status')=='verified-timeline' for g in sample) for c in counts}
            output.append({'rankBand':rank_band,'countsByCivilization':counts,'tcCountsByCivilization':tc_counts,'category':category,'civilization':civ,'matchTypeId':mode,'matchType':sample[0]['matchType'],'teamShape':sample[0]['teamShape'],'playerGames':len(sample),'games':len({g['gameId'] for g in sample}),'players':len({g['profileId'] for g in sample}),'knownOutcomePlayerGames':valid_outcomes,'contributingPlayerGames':contributing,'unmappedRows':unknown,'playerGamesWithUnmappedRows':len(unknown_games),'unresolvedAdditionalTCEvents':unresolved_tc,'items':rows})
    result={'rankBands':BANDS,'version':5,'title':'Win rates & usage','source':'Direct publisher statistical summaries and match outcomes, decoded locally',
        'sourceGames':len({g['gameId'] for g in games}), 'eligiblePlayerGames':sum(g['durationSeconds']>=600 and (g['gameId'],g['profileId']) in outcomes for g in games),
        'categories':[{'id':k,'label':v} for k,v in [('units','Units'),('technologies','Technologies'),('buildings','Buildings & landmarks')]],
        'bands':[{'id':k,'label':v} for k,v in [('S','60% and above'),('A','55–59%'),('B','50–54%'),('C','45–49%'),('D','Below 45%'),('Unrated','Small sample')]],
        'minimumAppearances':30,'civilizations':{c['id']:c['name'] for c in catalog['civilizations']}|{'__all__':'All civilizations','generic':'Generic'},
        'cohorts':output,'provenance':{'tcTimelinesSha256':sha(args.tc_cache),'sourceSha256':sha(SOURCE),'outcomesSha256':sha(HISTORY),'catalogSha256':sha(CATALOG),'familyMetadataSha256':sha(META),'startTimestamp':min(g['startedAt'] for g in games),'endTimestamp':max(g['startedAt'] for g in games)},
        'method':[
            'Unit share in each game = recorded nonstarting appearances of that unit family / all classified military unit appearances. Weighted win rate = sum(share in wins) / (sum(share in wins) + sum(share in losses)). Counts, not resource costs, determine shares.',
            'Average share when used is the arithmetic mean of those per-game shares among games using the unit. Usage is games using the item divided by games of its relevant civilization(s) in the selected mode. Generic units pool civilizations with that catalog unit; civilization filters restrict the denominator to that civilization.',
            'Generic unit tiers and production variants are merged. Named special units such as Gilded Spearman and Clocktower Battering Ram stay distinct. Recorded appearances can include free units and transformations, so these are not guaranteed paid production counts.',
            'Technologies and buildings use ordinary win rate among games using them. Buildings include wonders, landmarks, House of Wisdom wing completions, Golden Tent, generic Keeps and TC milestones. TC milestones mean reaching one, two or three concurrently owned TCs, using verified construction and destruction timelines. Replacements do not inflate the count. Packed TCs remain the same owned building; unpacking does not create another. Incomplete TC timelines are excluded from TC usage denominators.',
            'Rating filters use the mean pre-match publisher Elo of all participants, not historical Bronze–Conqueror RankPoints divisions.',
            'Only games lasting at least ten minutes with agreeing official outcomes contribute. One player perspective is one game observation; teammates share outcomes. At least thirty using observations are needed for a tier.',
            'Tiers: S >=60%, A >=55%, B >=50%, C >=45%, D <45%. Unmapped rows are excluded. These are selected-sample associations, not causal strength.'
        ]}
    target=ROOT/'data/unit-usage-tiers.json';temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8');temporary.replace(target)
    audit_path=ROOT/'.cache/usage-ranking-audit.json';audit_path.parent.mkdir(exist_ok=True);audit_path.write_text(json.dumps(audit,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'cohorts':len(output),'eligiblePlayerGames':result['eligiblePlayerGames'],'rows':sum(len(x['items']) for x in output),'bytes':target.stat().st_size}))
if __name__=='__main__':main()
