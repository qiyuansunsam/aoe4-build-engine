"""Evidence checks against independently read decoded RGD records."""
import hashlib
import json
from pathlib import Path
import unittest
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'data/game-catalog.json').read_text(encoding='utf-8'))
RAW=Path(CAT['provenance']['decodedRoot'])

def values(nodes, *keys):
    """Direct tree lookup deliberately independent of production normalizer."""
    current=nodes
    for key in keys:
        matches=[entry['value'] for entry in current if entry['key']==key]
        if len(matches)!=1: raise AssertionError((key,len(matches)))
        current=matches[0]
    return current

def raw(source):
    path=RAW/Path(source['asset']).with_suffix('.json')
    return json.loads(path.read_text(encoding='utf-8-sig'))['data']

def plain(nodes):
    if not isinstance(nodes,list): return nodes
    result={}
    for entry in nodes:
        result.setdefault(entry['key'],[]).append(plain(entry['value']))
    return {k:v[0] if len(v)==1 else v for k,v in result.items()}

class GameCatalogTests(unittest.TestCase):
    def test_every_unit_fact_matches_installed_entity(self):
        for unit in CAT['units']:
            with self.subTest(unit=unit['id']):
                entity=raw(unit['entitySource'])
                self.assertEqual(unit['hp'],values(entity,'default','health_ext','hitpoints'))
                self.assertEqual(unit['trainTimeSeconds'],values(entity,'default','cost_ext','time_cost','time_seconds'))
                for resource in ('food','wood','gold','stone'):
                    self.assertEqual(unit['cost'][resource],values(entity,'default','cost_ext','time_cost','cost',resource))
                self.assertEqual(unit['source']['pbgid'],values(raw(unit['source']),'default','pbgid'))
                self.assertEqual(unit['armor'],plain(values(entity,'default','health_ext','armor_scaler_by_damage_type')))
                base=plain(values(entity,'default'))
                self.assertEqual(unit['speedEngineUnits'],base.get('moving_ext',{}).get('speed_scaling_table',{}).get('default_speed'))
                self.assertEqual(unit['population'],base.get('population_ext',{}).get('personnel_pop'))

    def test_every_technology_cost_time_and_scalar_matches_source(self):
        for tech in CAT['technologies']:
            with self.subTest(tech=tech['id']):
                data=raw(tech['source'])
                self.assertEqual(tech['researchTimeSeconds'],values(data,'default','upgrade_bag','time_cost','time_seconds'))
                for resource in ('food','wood','gold','stone'):
                    self.assertEqual(tech['cost'][resource],values(data,'default','upgrade_bag','time_cost','cost',resource))
                bag=plain(values(data,'default','upgrade_bag'))
                expected=[]
                for kind in ('float_properties','int_properties'):
                    def traverse(node):
                        if isinstance(node,dict):
                            if 'id' in node and 'value' in node: expected.append((node['id'],node['value']))
                            for value in node.values(): traverse(value)
                        elif isinstance(node,list):
                            for value in node: traverse(value)
                    traverse(bag.get(kind,{}))
                self.assertEqual([(m['property'],m['value']) for m in tech['modifiers']],expected)
                self.assertEqual(tech['targeting'],bag.get('filter_conditions',{}))

    def test_every_building_cost_and_time_matches_source(self):
        for building in CAT['buildings']:
            with self.subTest(building=building['id']):
                data=raw(building['source'])
                self.assertEqual(building['buildTimeSeconds'],values(data,'default','cost_ext','time_cost','time_seconds'))
                for resource in ('food','wood','gold','stone'):
                    self.assertEqual(building['cost'][resource],values(data,'default','cost_ext','time_cost','cost',resource))
                base=plain(values(data,'default'))
                self.assertEqual(building['hp'],base.get('health_ext',{}).get('hitpoints'))
                self.assertEqual(building['armor'],base.get('health_ext',{}).get('armor_scaler_by_damage_type',{}))

    def test_every_weapon_damage_armor_type_bonus_and_timing_field(self):
        seen=set()
        for unit in CAT['units']:
            for weapon in unit['weapon']:
                if weapon['id'] in seen: continue
                seen.add(weapon['id'])
                with self.subTest(weapon=weapon['id']):
                    bag=plain(values(raw(weapon['source']),'default','weapon_bag'))
                    for field,rawfield in [('damageMin','min'),('damageMax','max'),('damageType','damage_type')]:
                        self.assertEqual(weapon[field],bag.get('damage',{}).get(rawfield))
                    self.assertEqual(weapon['range'],bag.get('range'))
                    self.assertEqual(weapon['cooldownSeconds'],bag.get('cooldown',{}).get('duration'))
                    self.assertEqual(weapon['windupSeconds'],bag.get('fire',{}).get('wind_up'))
                    self.assertEqual(weapon['winddownSeconds'],bag.get('fire',{}).get('wind_down'))
                    bonuses=bag.get('target_type_table',{}).get('target_unit_type_multipliers',[])
                    if isinstance(bonuses,dict): bonuses=[bonuses]
                    self.assertEqual(weapon['bonuses'],bonuses)

    def test_every_playable_race_is_present(self):
        visible=[]
        for path in (RAW/'attrib/racebps').glob('*.json'):
            base=plain(json.loads(path.read_text(encoding='utf-8-sig'))['data'])['default']
            if base.get('race_bag',{}).get('ui_visibility') and path.stem!='rogue_neutral':visible.append(path.stem)
        self.assertEqual(set(visible),{c['id'] for c in CAT['civilizations']})
        self.assertEqual(len(visible),23)

    def test_nonstandard_resource_costs_are_never_discarded(self):
        for group in ('units','buildings','technologies'):
            for obj in CAT[group]:
                data=raw(obj.get('entitySource',obj['source']))
                cost=plain(values(data,'default','upgrade_bag' if group=='technologies' else 'cost_ext','time_cost','cost'))
                nonzero={k:v for k,v in cost.items() if isinstance(v,(int,float)) and v!=0}
                self.assertEqual({k:v for k,v in obj['cost'].items() if v!=0},nonzero,obj['id'])
        merc=next(u for u in CAT['units'] if u['id']=='unit_landsknecht_3_merc_byz')
        self.assertEqual(merc['cost']['merc_byz'],160)
        self.assertEqual(merc['displayCost']['merc_byz'],160)
        self.assertEqual(merc['costLabels']['merc_byz'],'Olive Oil')
        mac=next(u for u in CAT['units'] if u['civilization']=='byzantine_ha_mac')
        self.assertEqual(mac['costLabels']['merc_byz'],'Silver')
        action=next(u for u in CAT['units'] if u['id']=='unit_trade_camel_abb_ha_01')
        self.assertEqual(action['cost']['action'],1)
        self.assertNotIn('action',action['displayCost'])

    def test_cattle_economy_records_are_present(self):
        cow=next(x for x in CAT['units'] if x['id']=='herdable_cattle_mal')
        self.assertEqual(cow['cost']['gold'],90)
        self.assertEqual(cow['resourceDeposit'],{'amount':500,'type':'cattle'})
        ranch=next(x for x in CAT['buildings'] if x['id']=='building_econ_ranch_mal')
        self.assertEqual(ranch['garrison']['slots'],3)
        self.assertEqual(ranch['garrison']['loadAction'],'ranch_hold_events_mal\\load_cattle')

    def test_royal_artillery_is_not_misclassified_as_campaign(self):
        ids={u['id'] for u in CAT['units']}
        for suffix in ('fre','fre_ha_01'):
            for unit in ('cannon','culverin','ribauldequin'):
                self.assertIn(f'unit_{unit}_4_royal_{suffix}',ids)

    def test_repeat_keys_not_lost(self):
        tech=next(x for x in CAT['technologies'] if x['id']=='upgrade_cavalry_chivalry_fre')
        self.assertEqual({x['property']:x['value'] for x in tech['modifiers']},{'heal_amount':1,'interval':1})
        unit=next(x for x in CAT['units'] if x['id']=='unit_spearman_2_eng')
        weapon=next(x for x in unit['weapon'] if x['id']=='weapon_spearman_2')
        self.assertEqual(weapon['damageMin'],8)
        self.assertEqual(weapon['damageType'],'Melee')
        self.assertEqual({b['unit_type']:b['base_damage_modifier'] for b in weapon['bonuses']},
                         {'cavalry':20,'war_elephant':4,'worker_elephant':24})

    def test_all_sources_have_hashes_and_ids(self):
        for group in ('units','buildings','technologies'):
            ids=[x['id'] for x in CAT[group]]
            self.assertEqual(len(ids),len(set(ids)))
            for obj in CAT[group]:
                self.assertRegex(obj['source']['sha256'],r'^[a-f0-9]{64}$')
                self.assertIsInstance(obj['source']['pbgid'],int)
        self.assertFalse(CAT['coverage']['unresolvedEntityReferences'])
        self.assertEqual(CAT['provenance']['patch'],'16.3.11308')

    def test_each_source_fingerprint_matches_extracted_binary(self):
        result=subprocess.run(['dotnet',str(ROOT/'tools/game-extract/bin/Release/net8.0/GameExtract.dll'),
            '--verify',CAT['provenance']['archive'],str(ROOT/'data/game-catalog.json')],
            capture_output=True,text=True,encoding='utf-8',timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('source fingerprints directly against installed archive',result.stdout)

    def test_archive_fingerprint(self):
        digest=hashlib.sha256()
        with Path(CAT['provenance']['archive']).open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
        self.assertEqual(digest.hexdigest(),CAT['provenance']['sha256'])

if __name__=='__main__': unittest.main()
