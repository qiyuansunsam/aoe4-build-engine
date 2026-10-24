"""Normalize locally decoded installed-game RGD facts; never changes engine constants.

Run after tools/game-extract. Raw files remain in the private game knowledge base.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from inspect_rgd import load

# Selected from root racebps records with ui_visibility=true; historical campaign races are excluded.
EXCLUDED_RACES = {'rogue_neutral'}
RESOURCES = ('food', 'wood', 'gold', 'stone')

def cost_fields(time_cost):
    raw = time_cost.get('cost',{})
    return {r:raw.get(r,0) for r in RESOURCES} | {r:v for r,v in raw.items() if r not in RESOURCES and isinstance(v,(int,float)) and v != 0}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def walk(value, path=''):
    if isinstance(value, dict):
        yield path, value
        for k, v in value.items(): yield from walk(v, path+'/'+k)
    elif isinstance(value, list):
        for i, v in enumerate(value): yield from walk(v, path+'/'+str(i))

def arr(value):
    return value if isinstance(value, list) else [value] if value else []

def refs(value, category):
    return list(dict.fromkeys(d['$PBGNAME'] for _, d in walk(value)
                             if d.get('$PBGMAP') == category and d.get('$PBGNAME')))

def requirements(value):
    result = []
    for path, d in walk(value):
        if 'upgrade_name' in d and isinstance(d['upgrade_name'], dict):
            result.append({'id': d['upgrade_name'].get('$PBGNAME'),
                           'present': d.get('is_present'), 'reason': d.get('reason'),
                           'includeQueued': d.get('include_queued'), 'field': path})
    return result

def get_civ(path):
    parts = path.split('/')
    return parts[parts.index('races')+1] if 'races' in parts else 'common'

def clean_name(value):
    return re.sub(r'<[^>]*>', '', value or '').replace('\\r\\n', '\n')

def normalize(decoded, locale, archive, steam_build, executable_version=None):
    raw_locale = locale.read_bytes()
    locale_text = raw_locale.decode('utf-16' if raw_locale[:2] in [b'\xff\xfe', b'\xfe\xff'] else 'utf-8-sig')
    strings = {}
    for line in locale_text.splitlines():
        key, sep, val = line.partition('\t')
        if sep and key.isdigit(): strings[int(key)] = clean_name(val)
    manifest = json.loads((decoded/'extraction-manifest.json').read_text(encoding='utf-8'))
    hashes = {r['asset']: r['sha256'] for r in manifest['records']}
    records, index = {}, defaultdict(list)
    for path in sorted((decoded/'attrib').rglob('*.json')):
        relative = path.relative_to(decoded/'attrib').as_posix()[:-5]
        if any('/'+x+'/' in relative for x in ('campaign', 'rogue')): continue
        records[relative] = load(path)
        index[(relative.split('/')[0], path.stem)].append(relative)

    civ_records = {key.split('/')[-1]: d for key,d in records.items() if key.startswith('racebps/') and key.count('/') == 1 and d.get('race_bag',{}).get('ui_visibility') and key.split('/')[-1] not in EXCLUDED_RACES}
    CIVS = set(civ_records)

    def resolve(category, name):
        matches = index.get((category, name), [])
        return matches[0] if len(matches) == 1 else None

    def source(key):
        return {'asset': 'attrib/'+key+'.rgd', 'pbgid': records[key].get('pbgid'),
                'sha256': hashes.get('attrib/'+key+'.rgd')}

    def ui_info(data, squad=False):
        if squad:
            race = data.get('squad_ui_ext', {}).get('race_list', {}).get('race_data', {})
            return arr(race)[0].get('info', {}) if race else {}
        return data.get('ui_ext', {})

    def info_fields(info, key):
        loc_id = info.get('screen_name')
        name = strings.get(loc_id) or key.rsplit('/',1)[-1].replace('_',' ').title()
        help_id = info.get('help_text')
        formatter = info.get('help_text_formatter', {})
        return {'name': name, 'description': strings.get(help_id, ''),
                'descriptionTemplate': strings.get(formatter.get('formatter'), ''),
                'descriptionArguments': formatter.get('formatter_arguments', {}),
                'icon': info.get('icon_name', ''), 'nameLocalizationId': loc_id}

    weapons = {}
    for key, d in records.items():
        if not key.startswith('weapon/'): continue
        if key.rsplit('/',1)[-1] in weapons:
            raise ValueError('Ambiguous weapon basename: '+key)
        w = d.get('weapon_bag', {})
        damage = w.get('damage', {})
        weapons[key.rsplit('/',1)[-1]] = {'id': key.rsplit('/',1)[-1],
            'name': strings.get(w.get('ui_name'), w.get('name','')),
            'damage': damage, 'damageMin': damage.get('min'), 'damageMax':damage.get('max'),
            'damageType': damage.get('damage_type'),
            'activation':'Referenced weapon variant; activation conditions are not evaluated.',
            'cooldownSeconds': w.get('cooldown',{}).get('duration'),
            'windupSeconds': w.get('fire',{}).get('wind_up'),
            'winddownSeconds': w.get('fire',{}).get('wind_down'),
            'range': w.get('range'),
            'bonuses': arr(w.get('target_type_table',{}).get('target_unit_type_multipliers')),
            'source': source(key)}

    units, buildings, techs = [], [], []
    warnings = ['Installed executable build is recorded separately from Steam build ID; official release status is in patch-audit.json.',
        'Entity definitions can bake in civilization differences; runtime buffs, aura effects and research are not applied again.',
        'Movement and range remain in engine units; cooldown is not a complete attack interval.',
        'Upgrade scalar properties and targeting are extracted; state-tree effect execution is not yet resolved.',
        'Historical Abbasid simulation constants remain separate from this installed ruleset.']
    unresolved = []
    for key, d in records.items():
        civ = get_civ(key)
        if civ not in CIVS and civ != 'common': continue
        if key.startswith('sbps/races/'):
            if civ not in CIVS: continue
            entity_refs = refs(d.get('squad_loadout_ext',{}), 'ebps')
            entity_key = resolve('ebps', entity_refs[0]) if entity_refs else None
            if not entity_key:
                if entity_refs: unresolved.append({'source':key,'entity':entity_refs[0]})
                continue
            entity = records[entity_key]
            if not any(segment in entity_key for segment in ('/units/','/animals/')): continue
            tc = entity.get('cost_ext',{}).get('time_cost',{})
            health = entity.get('health_ext',{})
            # Dummy bundles and scenario kings are not trainable stat-bearing forms.
            if 'hitpoints' not in health or 'time_seconds' not in tc: continue
            item = {'id':key.rsplit('/',1)[-1], 'civilization':civ, **info_fields(ui_info(d, True),key),
                'cost':cost_fields(tc),
                'trainTimeSeconds':tc.get('time_seconds'), 'hp':health.get('hitpoints'),
                'armor':health.get('armor_scaler_by_damage_type',{}),
                'speedEngineUnits':entity.get('moving_ext',{}).get('speed_scaling_table',{}).get('default_speed'),
                'population':entity.get('population_ext',{}).get('personnel_pop'),
                'age':max([{'dark_age':1,'feudal_age':2,'castle_age':3,'imperial_age':4}.get(r['id'],0) for r in requirements(d.get('squad_requirement_ext',{})) if r['present']] or [0]) or None,
                'statStatus':'verified-base-fields',
                'resourceDeposit':{'amount':entity.get('resource_deposit_ext',{}).get('initial_amount'),
                    'type':entity.get('resource_deposit_ext',{}).get('resource_sub_type',{}).get('$PBGNAME')},
                'weapon':[weapons[n] for n in refs(entity.get('combat_ext',{}),'weapon') if n in weapons],
                'requirements':requirements(d.get('squad_requirement_ext',{})),
                'classes':arr(d.get('squad_type_ext',{}).get('squad_type_list',{}).get('squad_type')),
                'source':source(key), 'entitySource':source(entity_key),
                'fieldEvidence':{'speedEngineUnits':'moving_ext/speed_scaling_table/default_speed','population':'population_ext/personnel_pop','hp':'health_ext/hitpoints','cost':'cost_ext/time_cost/cost','trainTimeSeconds':'cost_ext/time_cost/time_seconds','armor':'health_ext/armor_scaler_by_damage_type'}}
            item['tierTransitions'] = [{'upgrade':o.get('statetree_tier_requirements_pbg',{}).get('$PBGNAME'),
                    'entity':o.get('statetree_tier_pgb_upgrade_target_entity',{}).get('$PBGNAME'),
                    'squad':o.get('statetree_tier_pgb_upgrade_target_squad',{}).get('$PBGNAME')}
                for _,o in walk(entity) if o.get('statetree_tier_requirements_pbg',{}).get('$PBGNAME')]
            units.append(item)
        elif key.startswith('ebps/races/') and '/buildings/' in key and civ in CIVS:
            info = ui_info(d)
            tc=d.get('cost_ext',{}).get('time_cost',{})
            if not info.get('screen_name') or info.get('screen_name') not in strings: continue
            if 'time_seconds' not in tc: continue
            buildings.append({'id':key.rsplit('/',1)[-1], 'civilization':civ, **info_fields(info,key),
                'cost':cost_fields(tc),
                'buildTimeSeconds':tc.get('time_seconds'), 'hp':d.get('health_ext',{}).get('hitpoints'),
                'armor':d.get('health_ext',{}).get('armor_scaler_by_damage_type',{}),
                'garrison':{'slots':d.get('hold_ext',{}).get('num_slots'),
                    'acceptedTypes':d.get('hold_ext',{}).get('acceptable_types',{}),
                    'loadAction':d.get('hold_ext',{}).get('on_loaded_squad_action_tree',{}).get('ActionTree_OpeningBranch')},
                'trainableUnits':refs(d.get('spawner_ext',{}),'sbps'),
                'researchableTechnologies':refs(d,'upgrade'), 'statStatus':'verified-base-fields', 'source':source(key)})
        elif key.startswith('upgrade/'):
            bag=d.get('upgrade_bag',{}); info=bag.get('ui_info',{})
            if not info.get('screen_name') or info.get('screen_name') not in strings: continue
            tc=bag.get('time_cost',{})
            props=[]
            for kind in ('float_properties','int_properties'):
                for path, prop in walk(bag.get(kind,{})):
                    if 'id' in prop and 'value' in prop:
                        props.append({'property':prop['id'],'value':prop['value'],'field':'upgrade_bag/'+kind+path,'interpretation':'raw scalar; effect operation requires state-tree resolution'})
            techs.append({'id':key.rsplit('/',1)[-1], 'civilization':civ, **info_fields(info,key),
                'cost':cost_fields(tc),
                'researchTimeSeconds':tc.get('time_seconds'), 'requirements':requirements(bag.get('requirements',{})),
                'statStatus':'verified-scalars-unresolved-runtime-effects', 'modifiers':props, 'targeting':bag.get('filter_conditions',{}),
                'stateTrees':bag.get('state_tree_references',{}), 'source':source(key)})
    resource_types=[]
    for key,d in records.items():
        if not key.startswith('resource_type_info/'): continue
        bag=d.get('resource_type_bag',{}); ui=bag.get('ui',{})
        overrides={o.get('race',{}).get('$PBGNAME'):strings.get(o.get('ui',{}).get('name')) for o in arr(ui.get('overrides',{}).get('item'))}
        resource_types.append({'id':bag.get('resource_type'),'name':strings.get(ui.get('name'),bag.get('resource_type')),
            'productionCost':ui.get('is_productionCost',False),'overrides':overrides,'source':source(key)})
    for item in units+buildings+techs:
        item['costLabels']={r['id']:r['overrides'].get(item['civilization']) or r['name'] for r in resource_types}
        item['displayCost']={r['id']:item['cost'][r['id']] for r in resource_types if r['productionCost'] and item['cost'].get(r['id'])}
    counts={kind:len(items) for kind,items in [('units',units),('buildings',buildings),('technologies',techs)]}
    return {'schemaVersion':1, 'provenance':{'kind':'installed-game','steamBuildId':steam_build,
        'archive':str(archive),'sha256':sha(archive),'localeSha256':sha(locale),
        'extractedAt':datetime.now(timezone.utc).isoformat(),'patch':executable_version.rsplit('.',1)[0] if executable_version else None,
        'executableVersion':executable_version,'patchEvidence':'Installed RelicCardinal.exe ProductVersion; public release-note equivalence checked separately.' if executable_version else None,
        'gameSaveDataVersion':records.get('data_version/data_version',{}).get('value_bag',{}).get('cur_gamesave_data_version'),
        'decoder':'AOEMods.Essence 0.6.0','decodedRoot':str(decoded)},
        'coverage':{**counts,'decodedRecords':manifest['selectedRecords'], 'archiveRecords':manifest['archiveRecords'],
                    'warnings':warnings,'unresolvedEntityReferences':unresolved,
                    'civilizations':dict(Counter(u['civilization'] for u in units))},
        'resourceTypes':resource_types,
        'civilizations':[{'id':c,'name':strings.get(d['race_bag'].get('name'),c), 'icon':d['race_bag'].get('icon'), 'source':source('racebps/'+c)} for c,d in civ_records.items()],
        'units':units,'buildings':buildings,'technologies':techs}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decoded',type=Path,required=True)
    parser.add_argument('--locale',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--steam-build',required=True)
    parser.add_argument('--executable-version')
    parser.add_argument('--out',type=Path,default=Path('data/game-catalog.json'))
    args=parser.parse_args()
    result=normalize(args.decoded,args.locale,args.archive,args.steam_build,args.executable_version)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['coverage'],indent=2))
