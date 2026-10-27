"""Vikings glue for scripts/build_civ_engine_rules.py (17.0 preview pack data/civ-rules/vikings.json).

Feeds the pack mechanics into the engine slots read by site/civ-mech/vikings.js: Northern Migration (free villagers per Town
Center up to the Longhouse villager capacity), Longhouses as the population building, the four Longhouse attachments, the
Smithy / Pasture and Loom auto-research, Konungr Hall feasts and Call Shield Maidens, Baugr Fort as a Barracks, Gullinn
Temple Berserkers, the engine-completable sagas, Bondi Forester, Rikets Nyckel and Kongens Dor. Map and placement facts the
pack cannot settle are named under `assumptions` and exposed as plan parameters (mech.*)."""

AUTO = {'upgrade_smithy_damage_1_vik': 'smithy', 'upgrade_smithy_damage_2_vik': 'smithy', 'upgrade_smithy_damage_3_vik': 'smithy',
        'upgrade_loom_armor_1_vik': 'loom', 'upgrade_loom_armor_2_vik': 'loom', 'upgrade_loom_armor_3_vik': 'loom'}


def glue(p, s, h):
    mech, lm, cost = h['mech'], h['lm'], h['cost']
    b, T = s['buildings'], s['techs']
    # No ordinary House: the Longhouse is the population building (+25), and it raises the villager capacity (+10).
    lh = mech(p, 'longhouse')
    b['longhouse']['pop'] = lh.get('popProvided', 25); b['longhouse']['house'] = True; b['longhouse']['eco'] = True
    s['house'] = None  # Longhouses are built by the mechanics module (villager capacity and population), not by the house rule
    s['blacksmith'] = None  # no Blacksmith: damage/armor tiers come from the Smithy and Pasture and Loom attachments

    nm, at, kf, cm, bf, sg, sa, fo, rk, kd = (mech(p, k) for k in ('northern-migration', 'longhouse-attachments', 'konungr-feast', 'call-shield-maidens', 'baugr-fort',
                                                                 'sacred-grove', 'sagas', 'bondi-forester', 'rikets-nyckel', 'kongens-dor'))
    att = {}
    for k in ('bee', 'farm', 'smithy', 'loom'):
        a = at[k]
        att[k] = {'id': a['id'], 'name': {'bee': 'Bee Skeps', 'farm': 'Farmstead', 'smithy': 'Smithy', 'loom': 'Pasture and Loom'}[k], 'cost': cost(a['cost']), 'time': a['seconds'],
                  'age': a['age'], 'limit': a['limit']}
        if k == 'bee': att[k]['goldPerSecond'] = a['goldPerMinute'] / 60
        if k == 'farm': att[k].update({'fields': a['fields'], 'fieldRate': a['fieldRate']})
        if k in ('smithy', 'loom'): att[k].update({'techs': a['techs'], 'researchSeconds': a['researchSeconds'], 'earlierAgeFaster': a['earlierAgeFaster']})
    s['mech'] = {
        'migration': {'interval': nm['intervalSeconds'], 'startCapacity': nm['startCapacity'], 'perLonghouse': nm['perLonghouse'], 'falkrMinus': nm['falkrIntervalMinus']},
        'longhouse': {'bondiRate': lh['bondiProductionRate'], 'pop': lh['popProvided']},
        'attach': att,
        'feast': {'interval': kf['intervalSeconds'], 'food': kf['food'], 'perLonghouse': kf['perLonghouse']},
        'maidens': {'cost': cost(cm['cost']), 'time': cm['seconds'], 'base': cm['base'], 'perLonghouse': cm['perLonghouse'], 'pbgid': cm['unit']},
        'baugr': {'rate': bf['barracksWorkRate'], 'grants': bf['grants']},
        'grove': {'gullinn': sg['gullinnSeconds'], 'grove': sg['groveSeconds'], 'dreki': sg['drekiRate'], 'limit': sg['limit'], 'volur': {'cost': cost(sg['volur']['cost']), 'time': sg['volur']['seconds']}},
        'sagas': {'falkr': sa['falkr'], 'ulfr': sa['ulfr'], 'jofurr': sa['jofurr']},
        'forester': {'perBondi': fo['woodPerBondiPerMinute'] / 60, 'max': fo['maxPerMinute'] / 60},
        'rikets': {'units': rk['crossbowmen'], 'pbgid': 'unit_crossbowman_rikets_vik'},
        'kongens': {'gold': kd['goldPerLonghouse'], 'interval': kd['intervalSeconds']},
        'auto': AUTO,
    }
    for k, src in AUTO.items():
        if k in T: T[k]['auto'] = src; T[k]['cat'] = 'military'

    # Baugr Fort acts as a Barracks with all technologies: each Barracks technology gets a Baugr Fort copy (the engine's
    # landmark-copy variant), researched there once the landmark stands. Barracks technologies cost 15% less with it.
    barracks = [k for k, t in T.items() if t.get('building') == 'barracks' and not t.get('groupOf')]
    for k in barracks:
        v = 'upgrade_landmark_' + k[len('upgrade_'):]
        T[v] = dict(T[k], building='landmark:baugr-fort', buildingName='Baugr Fort', landmark='baugr-fort', groupOf=k, pbgid=T[k]['pbgid'])
        T[v].pop('variants', None); T[v].pop('requires', None); T[v].pop('tierOf', None); T[v].pop('tierIndex', None)
        T[k].setdefault('variants', []).append(v)
    disc = [{'kind': 'cost', 'target': 'tech:' + k, 'op': 'mul', 'value': 0.85} for k in barracks] + [{'kind': 'cost', 'target': 'tech:upgrade_landmark_' + k[len('upgrade_'):], 'op': 'mul', 'value': 0.85} for k in barracks]
    lm(s, 'baugr-fort')['effects'] = [{'kind': 'research_speed', 'target': 'barracks', 'op': 'mul', 'value': bf['barracksWorkRate']},
                                      {'kind': 'research_speed', 'target': 'landmark:baugr-fort', 'op': 'mul', 'value': bf['barracksWorkRate']}] + disc
    lm(s, 'baugr-fort')['producer'] = {'lines': bf['producerLines']}
    tiers = [k for k, t in T.items() if t.get('tierOf')]
    lm(s, 'rikets-nyckel-castle')['effects'] = [{'kind': 'cost', 'target': 'tech:' + k, 'op': 'mul', 'value': rk['tierTechCost']} for k in tiers] + \
        [{'kind': 'cost', 'target': 'tech:upgrade_landmark_' + k[len('upgrade_'):], 'op': 'mul', 'value': rk['tierTechCost']} for k in tiers if 'upgrade_landmark_' + k[len('upgrade_'):] in T]
    for key in ('konungr-hall', 'valdemar-castle', 'gullinn-temple', 'kongens-dor-cathedral'):
        lm(s, key)['effects'] = []  # their timing effects (feast, Berserkers, tithe) run in site/civ-mech/vikings.js
    s['start']['villagerCapacity'] = p['start'].get('villagerCapacity', 10)

    s['assumptions'].update({
        'migrationPerTC': 'Every Town Center recruits a free villager every 22 s in parallel (ability attached to both Town Center types; "auto queue on all your town centers", Beastyqt 19:17). No frame times two Town Centers side by side.',
        'gatherRates': 'Viking villagers gather at the installed 16.3 standard rates (no 17.0 record lists a Viking gather table).',
        'vegetableFields': 'Farmstead vegetable fields are infinite farms beside the Longhouse (one villager each) gathered at 1.5x the farm rate; villagers still empty sheep, berries and deer first.',
        'beeSkeps': 'Bee Skeps pay 50 gold per minute continuously (tooltip and record; the on-screen tick is about 8 gold per 10 s).',
        'autoResearch': 'Smithy and Pasture and Loom research one tier at a time, the next tier whose age is reached: 270 s, or 210 s when that tier belongs to an earlier age than the current one.',
        'codeOfJylland': 'Code of Jylland is researched at the Stable in Castle Age (age and building are in no record).',
        'veteranBerserker': 'Upgrade to Veteran Berserker is researched at the Barracks (building in no record).',
        'baugrResearch': 'Once Baugr Fort stands, Barracks technologies are researched at Baugr Fort (one at a time), 25% faster and 15% cheaper.',
        'groveBerserkers': 'Gullinn Temple recruits one free Berserker every 50 s (Sacred Grove 100 s, one source), 15% faster after the Dreki saga, while population room exists; no Sacred Groves are placed (mech.groves = 0: relics and sacred sites are map facts).',
        'kongensTithe': 'Kongens Dor tithe counts mech.kongensLonghouses Longhouses inside its area (default 0: its growth rate is in no record).',
        'jofurrHunt': "Jofurr's Hunt counts deer gathered by villagers (the map assumption has 8 deer of 350 food per pack; no boar or shore fish).",
        'shieldMaidens': 'Called Shield Maidens arrive 10 s after the 800 food is paid and count as army population.',
    })
    s['defaultLines'] = ['hirdman']
    s['defaults'] = {'vilTarget': 150, 'extraTCs': {2: 1, 3: 0}, 'landmarks': {2: 'baugr-fort', 3: 'gullinn-temple', 4: 'rikets-nyckel-castle'},
                     'mech': {'lh': {1: 3, 2: 5, 3: 4, 4: 2}, 'attach': ['bee', 'bee', 'bee', 'bee', 'bee', 'bee', 'smithy', 'loom', 'farm', 'farm', 'farm', 'farm', 'farm', 'farm'],
                              'lhLead': 4, 'lhBuilders': 1, 'longhouseBondi': False, 'gullinnMinPop': 0, 'callMaidens': False, 'callMaidensAt': 14, 'groves': 0, 'kongensLonghouses': 0}}
    s['unmodeled'] = ["Björn's Forage, Hrafn's Raid and Jörmungandr's Trade sagas (need healing, raids or trade)", 'Völur Local Rituals (+15% Bee Skeps / Farmstead)',
                      'Living off the Land healing', 'Shield Maiden recruitment at Konungr Hall (only the one-time call is modelled)', 'Sacred Groves on relics or sacred sites',
                      'Danevirke walls, Keep fire', 'Jylland Knight gold on death (combat)', 'Longship / Drakkar and Dock influence', 'trade']
