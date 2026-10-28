"""Package local game artwork for the comparison workspace (no network required)."""
import base64, hashlib, json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
CACHE=ROOT/'aoe4world/public/assets/icons'
RAW=ROOT.parent/'games/kb/aoe4/extract/UIArt/ui/icons'
def slug(s): return re.sub('[^a-z0-9]+','-',s.lower()).strip('-')
catalog=json.loads((ROOT/'data/game-catalog.json').read_text(encoding='utf-8'))
engine=(ROOT/'site/engine.js').read_text(encoding='utf-8')
block=engine.split('const TECH = {',1)[1].split('\n};',1)[0]
techs=re.findall(r'(?:"([\w-]+)"|(\w+)):\s*\[',block)
wanted={a or b for a,b in techs}
wanted.update('villager camel-rider camel-archer archer spearman horseman knight royal-knight lancer mangudai keshik donso musofadi-warrior samurai onna-bugeisha trader scout cow sheep town-center stable barracks archery-range blacksmith madrasa mill mining-camp lumber-camp house farm house-of-wisdom cattle-ranch pit-mine granary market monastery pasture ger university keep outpost economic-wing culture-wing military-wing'.split())
icons={}; manifest={}; missing=[]
records=[r for kind in ['units','buildings','technologies'] for r in catalog[kind]]
records.sort(key=lambda r: 'abbasid' not in r.get('icon',''))
for key in sorted(wanted):
 source=None; origin=None
 aliases={'elite-camel-riders':'elite-camel-rider'}
 candidates=[r for r in records if slug(r.get('name','')) in {key,aliases.get(key,key)}]
 for r in candidates:
  path=RAW/(r.get('icon','').replace('\\','/')+'.png')
  if path.is_file(): source=path;origin='installed UIArt texture decoded to PNG';break
 if not source:
  options=sorted(CACHE.glob('*--'+key+'-[1-4].png'))
  if key=='villager': options=[CACHE/'units--abbasid--villager-1.png']
  if key=='elite-camel-riders': options=[CACHE/'technologies--upgrade-to-elite-4.png']
  if options and options[0].is_file(): source=options[0];origin='existing local AoE4 World artwork cache'
 if not source: missing.append(key);continue
 payload=source.read_bytes()
 assert payload[:8]==b'\x89PNG\r\n\x1a\n',source
 icons[key]='data:image/png;base64,'+base64.b64encode(payload).decode()
 manifest[key]={'source':str(source),'origin':origin,'sha256':hashlib.sha256(payload).hexdigest()}
for name in ['food','wood','gold','stone']:
 source=RAW/'resources'/f'resource_{name}_icon.png';payload=source.read_bytes()
 icons[name]='data:image/png;base64,'+base64.b64encode(payload).decode()
 manifest[name]={'source':str(source),'origin':'installed UIArt texture decoded to PNG','sha256':hashlib.sha256(payload).hexdigest()}
(ROOT/'data/game-icons.json').write_text(json.dumps(icons,separators=(',',':')),encoding='utf-8')
(ROOT/'data/game-icons-provenance.json').write_text(json.dumps({'note':'Local UI artwork. Images do not establish stat or patch equivalence. Normalized lower-case hyphenated names. Unavailable images use UI symbols, never substitute unrelated art.','icons':manifest,'missing':missing},indent=2),encoding='utf-8')
print(f'{len(icons)} icons, {(ROOT/"data/game-icons.json").stat().st_size//1024} KB; missing: {missing}')
