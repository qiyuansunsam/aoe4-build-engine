"""Engine glue for the Scots (Update 17.0 preview pack data/civ-rules/scots.json).

Same role as malian()/japanese() in scripts/build_civ_engine_rules.py: puts the pack's mechanics into the engine slots
(spec['mech']['scots'] is read by site/civ-mech/scots.js), sets landmark effects the engine applies directly (regional
technology halving), technology effects the generic compiler cannot infer (Fermtouns and Pastures, Wallace's Rally), and
records the named assumptions. Every number is read from the pack (which cites the 17.0 records, the checklist or footage).
"""


def glue(p, s, helpers):
    mech, lm, cost, kebab = helpers['mech'], helpers['lm'], helpers['cost'], helpers['kebab']
    b = s['buildings']
    tower = mech(p, 'tower-house')
    b['house']['pop'] = next(x for x in [p['buildings']['house'].get('popProvided')] if x)
    b['house']['house'] = True
    b['tower-house']['pop'] = tower.get('pop', 15)
    b['tower-house']['eco'] = True
    b['mustering-hall']['eco'] = False
    s['house'] = 'house'
    s['blacksmith'] = 'blacksmith'
    s['roles'] = {}

    # Technology effects the generic id-pattern compiler does not know.
    pack_t = {t['id']: t for t in p['technologies']}
    T = s['techs']
    T['upgrade_lowland_and_highland_tier2_sco']['effects'] = [
        {'kind': e['kind'], 'target': e['target'], 'op': e['op'], 'value': e['value']} for e in pack_t['upgrade_lowland_and_highland_tier2_sco']['effects']]
    T['upgrade_wallace_rally_sco']['effects'] = [
        {'kind': e['kind'], 'target': e['target'], 'op': e['op'], 'value': e['value']} for e in pack_t['upgrade_wallace_rally_sco']['effects']]
    for k, t in pack_t.items():
        if t.get('region') and k in T:
            T[k]['region'] = t['region']

    # Landmarks: region, and the regional technology halving as engine cost effects (priced(cost, 'tech', id)).
    rd = mech(p, 'regional-discount')
    region_of = {}
    for age, opts in p['landmarks'].items():
        for l in opts:
            region_of[l['key']] = l['region']
            L = lm(s, l['key'])
            L['region'] = l['region']
            L['effects'] = [{'kind': 'cost', 'target': 'tech:' + tid, 'op': 'mul', 'value': rd.get('perLandmark', 0.5)} for tid in rd.get(l['region'], [])]

    cat = mech(p, 'highland-cattle')
    hall = mech(p, 'mustering-hall')
    snow = mech(p, 'snowdoun-gate')
    kirk = mech(p, 'kirkman-relics')
    fish = mech(p, 'fishpond')
    abbey = mech(p, 'abbey-relic')
    sod = mech(p, 'stone-of-destiny-rebate')
    musters = {}
    for key, m in hall.get('musters', {}).items():
        musters[key] = {'id': m['id'], 'name': m['name'], 'food': m['food'], 'action': m['actionSeconds'], 'units': m['units'], 'unitSeconds': m['unitSeconds'],
                        'age': m['age'], 'line': kebab(m['line'].replace('_', '-')) if m.get('line') else None, 'requiresTier': m.get('requiresTier', 0)}
    s['mech'] = {'scots': {
        'cattle': {'foodPerSecond': cat['foodPerMinute'] / 60, 'cost': cost(cat['cost']), 'time': cat['trainSeconds'], 'capStart': cat['capStart'], 'capPerHighland': cat['capPerHighlandLandmark'],
                   'start': cat['startCount'], 'producers': [kebab(x.replace('_', '-')) if not x.startswith('landmark:') else x for x in cat['producers']]},
        'hall': {'defaultCharges': hall['defaultCharges'], 'tiers': hall['tierStructures'], 'reduction': {int(k): v for k, v in hall['costReductionByTier'].items()},
                 'structures': [kebab(x.replace('_', '-')) for x in hall['structureTypes']], 'lookoutCharges': hall['lookoutCharges'], 'lookoutMultiplier': hall['lookoutWarriorMultiplier']},
        'musters': musters,
        'snowdoun': {'batch': snow['batch'], 'cycle': {kebab(k.replace('_', '-')): v for k, v in snow['cycleSeconds'].items()}, 'perHallTech': snow['perHallTech']},
        'kirkman': {'cost': cost(kirk['kirkmanCost']), 'time': kirk['kirkmanSeconds'], 'speed': kirk['kirkmanSpeedTiles'], 'relicAge': kirk['relicAge']},
        'fishpond': {'goldPerSecond': fish['goldPerMinute'] / 60, 'build': fish['buildSeconds'], 'aura': fish['aura'], 'capPerLowland': fish['capPerLowlandLandmark'],
                     'capLandmarkMax': fish.get('capLandmarkMax', 4), 'stewPonds': fish.get('stewPonds')},
        'abbeyMultiplier': abbey['productionMultiplier'], 'rebate': sod['fraction'],
        'highland': sorted(k for k, v in region_of.items() if v == 'highland'), 'lowland': sorted(k for k, v in region_of.items() if v == 'lowland'),
    }}
    s['start']['cattle'] = cat['startCount']
    s['defaultLines'] = ['man-at-arms', 'gallowglass']
    s['defaults'] = {'mech': {
        'towerHouses': {'1': 1, '2': 1, '3': 0}, 'cattle': {'1': 5, '2': 9, '3': 13, '4': 17}, 'cattleFrom': 0,
        'hallAge': 2, 'musters': ['cateran', 'gallowglass', 'pikemen', 'reivers'], 'musterAge': {}, 'snowdoun': 'man-at-arms',
        'kirkmen': 0, 'fishponds': 0, 'relics': 3, 'relicDistanceTiles': 45, 'relicGoldPerMinute': 100, 'pondWorkers': 8, 'rebateFarms': True}}
    s['planExtras'] = {}
    s['ageUpGrants'] = {}
    s['assumptions'].update({
        'patch': 'Scots are not in the installed game: every unique value is Update 17.0 preview data (datamined records, footage); standard villager gather rates come from the installed 16.3 standard villager.',
        'musterSpawn': 'A muster is a 5 s action; its warriors then come out one at a time, 2 s apart (mustered unit records; one test game shows about one every 2 s). A cheat sandbox showed a faster burst.',
        'musterOnce': 'Each muster type is used once per player (record: "Each type of muster is one-time use"; a second Mustering Hall is not shown to reset it).',
        'musterPop': 'A muster starts only when all its warriors fit under the population cap.',
        'hallStructures': 'Barracks, Archery Ranges, Stables, Siege Workshops and Docks all stand inside the Mustering Hall influence and count toward its tiers.',
        'cattleBushes': 'One cow per Berry Bush; grazing does not block villagers; cows graze only on bushes not yet depleted (main patch and far patches). The starting cow grazes from 0:00.',
        'skye': 'Tower of Skye trains Highland Cattle like a Tower House; it adds no population.',
        'wallace': "Wallace's Rally speeds Barracks infantry only (the record modifier also names the Archery Range).",
        'rebate': 'Stone of Destiny: every non-landmark building finished after it completes, farms and Town Centers included, is built in its reach (Sam, 2026-10-25); 30% of its cost comes back as gold on completion.',
        'kirkmanFeudal': 'With the Stone of Destiny, Kirkmen are available from its completion (producing building not shown); otherwise from the Castle Age Monastery.',
        'relics': 'Relics: mech.relics relics collected, each mech.relicDistanceTiles tiles from the Monastery (walked out and back at the Kirkman record speed), mech.relicGoldPerMinute gold per relic per minute (not in any decoded installed record).',
        'fishpondAura': 'A worked Fishpond speeds mech.pondWorkers nearby workers (one ring of farms or one resource line around it; geometry, not a game value) by 10%, 20% after Stew Ponds. The buff does not stack: each worker counts once however many ponds reach it, so ponds cover separate groups. Fishpond capacity 1 per Lowland landmark (at most 4), +1 with Stew Ponds (record text); Stew Ponds also spawns a free Kirkman.',
        'abbey': "Abbey of the Isles: the Saint's Relic sits in the first production building of the build's lines for the whole game (x2.35 production there); its research-speed use and moves are not modelled.",
        'snowdounStacking': 'Snowdoun Gate cycle = toggle time / (1 + 0.15 x Mustering Hall technologies researched); Wallace\'s Rally and the enemies-nearby bonus are not applied there.',
    })
    s['unmodeled'] = ['Highland Ambush and Stealth Forests', 'Ghillie stealth', 'Barmkins and cattle garrisons', 'Lion\'s Duty armor aura', 'Fortified Tower Houses',
                      'Snowdoun Gate enemies-nearby bonus', 'Seven Sisters cannons', 'Muster Royal Navy', 'trade', 'naval']
