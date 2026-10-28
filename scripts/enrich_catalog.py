"""Derive browse metadata only from installed catalog links/classes and local artwork."""
import base64,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; RAW=ROOT.parent/'games/kb/aoe4/extract/UIArt/ui/icons'; CACHE=ROOT/'aoe4world/public/assets/icons'
c=json.loads((DATA/'game-catalog.json').read_text(encoding='utf-8'))
icons=json.loads((DATA/'game-icons.json').read_text(encoding='utf-8')); prov=json.loads((DATA/'game-icons-provenance.json').read_text(encoding='utf-8'))
records={r['id']:r for kind in ('units','buildings','technologies') for r in c[kind]}; units={r['id']:r for r in c['units']}; techs={r['id']:r for r in c['technologies']}
slug=lambda s:re.sub('[^a-z0-9]+','-',s.lower()).strip('-')
parents={i:i for i in units}
def root(i):
 while parents[i]!=i: i=parents[i]
 return i
def join(a,b):
 if b in units and units[a]['civilization']==units[b]['civilization']:parents[root(b)]=root(a)
for i,u in units.items():
 for tr in u.get('tierTransitions',[]):join(i,tr.get('entity',''))
producers={i:[] for i in records}; tech_producers={i:[] for i in techs}
for b in c['buildings']:
 for i in b.get('trainableUnits',[]):
  if i in producers: producers[i].append(b['id'])
 for i in b.get('researchableTechnologies',[]):
  if i in tech_producers:tech_producers[i].append(b['id'])
families={}
for i in units:families.setdefault(root(i),[]).append(i)
for members in families.values():
 ps=sorted({p for i in members for p in producers[i]})
 for i in members:producers[i]=ps

def classes(tree):
 if not isinstance(tree,dict):return set()
 value=tree.get('unit_class',[]);return set([value] if isinstance(value,str) else value)
def relevant(u,t):
 targeted=classes(t.get('targeting',{}).get('apply_to_unit_classes',{})); own=set(u.get('classes',[]))
 if 'ranged' in own and 'infantry' in own:own.add('ranged_infantry')
 if 'ranged' in own and 'cavalry' in own:own.add('cavalry_archer')
 condition=t.get('targeting',{}).get('apply_to_filter_condition_statetree_ref','')
 if condition=='common_upgrade_master\\CONDITIONS\\ranged_units_and_buildings_all':return bool(own.intersection({'ranged_infantry','cavalry_archer','building','archer_ship','fishing_ship_attack_sul'})) and not own.intersection({'gunpowder','siege'})
 if not targeted or not targeted.intersection(own):return False
 ai=t.get('targeting',{}).get('ai_unit_types',{});any_=classes(ai.get('any',{}));none=classes(ai.get('none',{}))
 if any_ and not any_.intersection(own):return False
 if none.intersection(own):return False
 if t.get('targeting',{}).get('apply_to_filter_condition_statetree_ref'):return False
 # Tier upgrades belong only to explicit unit transitions, not broad class targets.
 if t['id'].startswith('upgrade_unit_'):return False
 return True
cachepaths=list(CACHE.glob('*.png'));missing=[];meta={}
for i,r in records.items():
 raw=r.get('icon','').replace('\\','/');path=RAW/(raw+'.png');origin='installed UIArt texture decoded to PNG'
 if not path.is_file():
  key=slug(r['name']);options=[p for p in cachepaths if re.search(r'--'+re.escape(key)+r'-[1-4]\.png$',p.name)]
  if not options:
   # Exact displayed tier names in catalog have cache filenames without tier prefix.
   base=re.sub(r'^(early|veteran|elite|hardened)-','',key);options=[p for p in cachepaths if re.search(r'--'+re.escape(base)+r'-[1-4]\.png$',p.name)]
  options.sort(key=lambda p:(r.get('civilization','') not in p.name, int(re.search(r'-(\d)\.png$',p.name).group(1))!=(r.get('age') or 0),p.name))
  path=options[0] if options else None;origin='existing local AoE4 World artwork cache'
 iconkey=None
 if path and path.is_file():
  payload=path.read_bytes();assert payload[:8]==b'\x89PNG\r\n\x1a\n';sha=hashlib.sha256(payload).hexdigest();iconkey='asset-'+sha[:20]
  icons[iconkey]='data:image/png;base64,'+base64.b64encode(payload).decode();prov['icons'][iconkey]={'source':str(path),'origin':origin,'sha256':sha}
 else:missing.append(i)
 tags=[x.replace('_',' ') for x in r.get('classes',[]) if not x.startswith('scar_') and x not in ['can_be_converted','none','unit','entity']]
 groups={}
 if i in units:
  explicit={t['upgrade'] for t in r.get('tierTransitions',[])}
  for tid,t in techs.items():
   if tid not in explicit and not relevant(r,t):continue
   for b in tech_producers[tid]:
    if records[b]['civilization']==r['civilization']:groups.setdefault(b,[]).append(tid)
 elif i in {b['id'] for b in c['buildings']}:
  valid=[t for t in r.get('researchableTechnologies',[]) if t in techs and not t.endswith('_age')]
  if valid:groups[i]=valid
 meta[i]={'tags':tags,'producerIds':producers[i] if i in units else tech_producers.get(i,[]),'familyKey':root(i) if i in units else i,'available':bool(producers[i]) if i in units else True,'upgradeGroups':[{'buildingId':b,'technologyIds':sorted(ids)} for b,ids in groups.items()],'iconKey':iconkey}
(DATA/'catalog-enrichment.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
(DATA/'game-icons.json').write_text(json.dumps(icons,separators=(',',':')),encoding='utf-8')
prov['catalogMissing']=missing
(DATA/'game-icons-provenance.json').write_text(json.dumps(prov,indent=2),encoding='utf-8')
print(f'{len(meta)} records, {len(icons)} icon keys, {len(missing)} records missing art, {sum(m["available"] for i,m in meta.items() if i in units)} roster forms')
