"""Verify catalog browse metadata, roster distinctions and packaged artwork."""
import base64,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
c=json.loads((ROOT/'data/game-catalog.json').read_text(encoding='utf-8'));m=json.loads((ROOT/'data/catalog-enrichment.json').read_text(encoding='utf-8'));icons=json.loads((ROOT/'data/game-icons.json').read_text(encoding='utf-8'));p=json.loads((ROOT/'data/game-icons-provenance.json').read_text(encoding='utf-8'))
rs={r['id']:r for k in ['units','buildings','technologies'] for r in c[k]}
assert len(m)==len(rs)
assert not m['unit_cannon_4_abb']['available']
assert m['unit_culverin_4_abb']['available']
for tier in [2,3,4]:
 x=m[f'unit_horseman_{tier}_abb'];assert x['available'];assert x['familyKey']==m['unit_horseman_2_abb']['familyKey'];assert x['producerIds']
a=m['unit_archer_2_abb'];assert 'ranged' in a['tags'] and 'infantry' in a['tags'];assert all(not t.startswith('scar') for t in a['tags'])
aids={t for g in a['upgradeGroups'] for t in g['technologyIds']};assert 'upgrade_ranged_damage_i' in aids;assert 'upgrade_melee_damage_i' not in aids
for i,x in m.items():
 for b in x['producerIds']:assert b in rs
 for g in x['upgradeGroups']:
  assert g['buildingId'] in rs
  assert all(t in rs[g['buildingId']].get('researchableTechnologies',[]) for t in g['technologyIds'])
 if x['iconKey']:assert x['iconKey'] in icons
for key,data in icons.items():
 raw=base64.b64decode(data.split(',',1)[1]);assert raw[:8]==b'\x89PNG\r\n\x1a\n';assert hashlib.sha256(raw).hexdigest()==p['icons'][key]['sha256'];w,h=struct.unpack('>II',raw[16:24]);assert w>0 and h>0
for i in ['unit_crossbowman_3_abb','unit_culverin_4_abb','unit_handcannon_4_abb','unit_cannon_4_abb']:assert m[i]['iconKey']
print('Catalog metadata: source roster, tier families, targeted upgrade relations and all icon hashes/dimensions passed')
