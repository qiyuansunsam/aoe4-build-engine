import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"
TRACKED = {7195780, 1588970, 7999822, 18518902}


def commands(replay):
    return sorted((dict(c, time=r['time']) for r in replay['records'] if r['record'] == 'tick'
                   for b in r['blocks'] for c in b['commands']), key=lambda c: c['time'])


def own_match(game, summary_file):
    replay = json.loads((ROOT / f'replay-{game}.parsed.json').read_text(encoding='utf8'))
    summary = json.loads((ROOT / summary_file).read_text(encoding='utf8'))
    catalog = json.loads((ROOT / 'metric-tech-data.json').read_text())
    all_commands = commands(replay)
    results = []
    for player in summary['players']:
        if player['profile_id'] not in TRACKED:
            continue
        pid = next(p['playerId'] for p in replay['summary']['players'] if p['profileId'] == player['profile_id'])
        cs = [c for c in all_commands if c['playerId'] == pid]
        villagers = [b for b in player['build_order'] if b['type'] == 'Unit' and b['icon'].endswith('/villager')]
        births = sorted(t for b in villagers for t in b['finished'] if t > 0)
        deaths = sorted(t for b in villagers for t in b['destroyed'])
        villager_ids = {b['pbgid'] for b in villagers}
        queues = [c for c in cs if c['name'] == 'QueueUnit' and any(a.get('pbgid') in villager_ids for a in c.get('args', []))]
        orders = [c for c in cs if c['name'] in ['Move', 'AttackMove', 'SeekShelter', 'UnitAbility']]
        research = []
        for item in player['build_order']:
            if item['type'] != 'Upgrade':
                continue
            clicks = [c['time'] for c in cs if c['name'] == 'Research' and any(a.get('pbgid') == item['pbgid'] for a in c.get('args', []))]
            for finish in item['finished']:
                preceding = [t for t in clicks if t <= finish]
                if not preceding:
                    continue
                tech = catalog.get(str(item['pbgid']))
                row = {'name': tech['name'] if tech else item['icon'].split('/')[-1], 'pbgid': item['pbgid'],
                       'requests_before_finish': preceding, 'last_request': preceding[-1], 'finish': finish,
                       'request_to_finish_seconds': round(finish-preceding[-1], 3)}
                if tech:
                    row['current_catalog_research_seconds'] = tech['costs']['time']
                    row['duration_residual_seconds'] = round(finish-preceding[-1]-tech['costs']['time'], 3)
                    r = player['resources']
                    affordable = [t for i, t in enumerate(r['timestamps']) if t < preceding[-1]
                                  and all(r[k][i] >= tech['costs'][k] for k in ['food', 'wood', 'gold', 'stone'])]
                    row['earliest_sample_with_nominal_cost'] = min(affordable, default=None)
                    row['affordability_caveat'] = 'Not an opportunity delay: prerequisites, building queues, discounts and strategic commitments unresolved'
                research.append(row)
        episodes = []
        for death in deaths:
            if not episodes or death-episodes[-1]['last_death'] > 20:
                episodes.append({'first_death': death, 'last_death': death, 'lost': 1})
            else:
                episodes[-1]['last_death'] = death
                episodes[-1]['lost'] += 1
        for e in episodes:
            lo, hi = max(0, e['first_death']-10), e['last_death']+20
            e['shelter_orders_near_episode'] = [c['time'] for c in cs if c['name'] == 'SeekShelter' and lo <= c['time'] <= hi]
            e['villager_queue_orders_near_episode'] = sum(lo <= c['time'] <= hi for c in queues)
            e['villager_births_near_episode'] = sum(lo <= t <= hi for t in births)
        duration = min(replay['summary']['durationSeconds'], player['resources']['timestamps'][-1])
        windows = []
        for start in range(0, int(duration)-29, 30):
            q = sum(start <= c['time'] < start+30 for c in queues)
            o = sum(start <= c['time'] < start+30 for c in orders)
            windows.append({'start': start, 'villager_queue_orders': q, 'unit_orders': o,
                            'both': bool(q and o), 'villager_losses': sum(start <= t < start+30 for t in deaths)})
        r = player['resources']
        banks = [sum(r[k][i] for k in ['food', 'wood', 'gold', 'stone']) for i in range(len(r['timestamps']))]
        coverage = r['timestamps'][-1]-r['timestamps'][0]
        area = sum(banks[i]*(r['timestamps'][i+1]-t) for i, t in enumerate(r['timestamps'][:-1]))
        results.append({'profile_id': player['profile_id'], 'name': player['name'], 'civilization': player['civilization'],
                        'command_counts': dict(Counter(c['name'] for c in cs)), 'research': research,
                        'loss_episodes': episodes, 'coordination_30s_windows': windows,
                        'coordination_caveat': 'Orders to units can target villagers or scouts; co-occurrence is not a multitasking skill score',
                        'mean_sampled_resource_bank': round(area/coverage, 1) if coverage else None,
                        'resource_coverage_end_seconds': r['timestamps'][-1],
                        'first_villager_request': queues[0]['time'] if queues else None,
                        'first_villager_birth': births[0] if births else None})
    return {'game_id': game, 'replay_seconds': replay['summary']['durationSeconds'], 'summary_seconds': summary['duration'],
            'clock_note': 'No duration-based shift applied; assess paired command/completion anchors', 'players': results}


def recorded_sample(path=None):
    path = path or ROOT / 'tactical-recordings_aoe4_245598603.rlog'
    entities, bases, states, masks = {}, {}, {}, {}
    counts, hits, missing_hits = Counter(), [], 0
    cell_seconds, visited = defaultdict(float), defaultdict(set)
    first_enemy_half, damage_by_player = {}, Counter()
    previous = None
    max_gap = 0
    queue_known_seconds, queue_empty_seconds = Counter(), Counter()
    queues = {}
    teams, lethal_hits, killed = {}, defaultdict(list), []
    records = []
    for line in path.read_text(encoding='utf8').splitlines():
        a = line.split('|')
        counts[a[0]] += 1
        if a[0] == 'HDR':
            width, length = float(a[3]), float(a[4])
        if a[0] == 'PL':
            teams[int(a[1])] = int(a[4])
        if a[0] in ['N', 'S', 'O', 'X', 'V', 'H', 'PQ', 'T', 'K']:
            records.append((float(a[1]), a))
    for t, a in sorted(records, key=lambda x: x[0]):
        kind = a[0]
        if kind == 'K':
            context = dict(part.split('=', 1) for part in a[2].split(';') if '=' in part)
            victim = context.get('victim', '')
            if victim.startswith('e') and victim[1:].isdigit():
                killed.append((t, int(victim[1:])))
            continue
        if kind == 'T':
            if previous is not None:
                dt = t-previous
                max_gap = max(max_gap, dt)
                for owner, cells in last_cells.items():
                    cell_seconds[owner] += len(cells)*dt
                for eid, size in last_queues.items():
                    owner = entities[eid]['owner']
                    queue_known_seconds[owner] += dt
                    if size == 0:
                        queue_empty_seconds[owner] += dt
            last_cells = defaultdict(set)
            for eid, entity in entities.items():
                if eid not in states or not entity['military'] or states[eid][2] <= 0:
                    continue
                owner = entity['owner']
                x, z, hp = states[eid]
                cell = (int((x+width/2)/(width/16)), int((z+length/2)/(length/16)))
                if 0 <= cell[0] < 16 and 0 <= cell[1] < 16:
                    last_cells[owner].add(cell)
                    visited[owner].add(cell)
                enemies = [v for k, v in bases.items() if k != owner]
                if owner in bases and enemies:
                    home, enemy = bases[owner], enemies[0]
                    if math.dist((x,z), enemy) < math.dist((x,z), home):
                        first_enemy_half.setdefault(owner, t)
            last_queues = {eid:size for eid,size in queues.items() if eid in states and 'town_center' in entities[eid]['bp']}
            previous = t
            continue
        for part in a[2].split(';'):
            v = part.split(',')
            if kind == 'N':
                eid, owner, bp = int(v[0]), int(v[1]), v[2]
                military = bp.startswith('unit_') and not any(s in bp for s in ['villager', 'scout', 'monk', 'trader', 'fishing', 'transport'])
                entities[eid] = {'owner':owner, 'bp':bp, 'military':military}
                states[eid] = tuple(map(float,v[6:9]))
                if 'town_center_capital' in bp:
                    bases.setdefault(owner, states[eid][:2])
            elif kind == 'S':
                states[int(v[0])] = tuple(map(float,v[1:4]))
            elif kind == 'X':
                states.pop(int(v[0]), None)
                queues.pop(int(v[0]), None)
            elif kind == 'O' and int(v[0]) in entities:
                entities[int(v[0])]['owner'] = int(v[1])
            elif kind == 'V':
                masks[int(v[0])] = int(v[1])
            elif kind == 'PQ':
                queues[int(v[0])] = int(v[1])
            elif kind == 'H':
                attacker, victim = int(v[0]), int(v[1])
                if attacker not in entities or victim not in entities:
                    missing_hits += 1
                    continue
                aa, vv = entities[attacker], entities[victim]
                if aa['owner'] <= 0 or vv['owner'] <= 0 or teams.get(aa['owner'],aa['owner']) == teams.get(vv['owner'],vv['owner']) or v[5] == '1':
                    continue
                if float(v[3]) <= 0 and float(v[2]) > 0:
                    lethal_hits[victim].append((t, aa['owner']))
                damage_by_player[aa['owner']] += float(v[2])
                hits.append({'time':t, 'attacker':attacker, 'victim':victim, 'damage':float(v[2]),
                             'victim_is_villager':'villager' in vv['bp'],
                             'attacker_visible_in_last_sample_to_victim': bool(masks.get(attacker,0) & (1 << (vv['owner']-1)))})
    villager_kills, uncredited, seen = Counter(), 0, set()
    for t, victim in killed:
        if victim in seen or victim not in entities or 'villager' not in entities[victim]['bp']:
            continue
        seen.add(victim)
        candidates = [(ht, owner) for ht, owner in lethal_hits[victim] if t-1 <= ht <= t+0.5]
        if candidates:
            villager_kills[max(candidates)[1]] += 1
        else:
            uncredited += 1
    return {'dataset':'Upstream showcase, not your games', 'game_id':245598603,
            'source':'https://github.com/BigManJohn000/aoe4-replay-viewer', 'record_line_counts':dict(counts),
            'max_heartbeat_gap_seconds':max_gap, 'hostile_damage_events_resolved':len(hits),
            'damage_events_with_unresolved_entity':missing_hits, 'reported_hostile_damage':dict(damage_by_player),
            'first_non_scout_military_in_enemy_half_seconds':first_enemy_half,
            'military_visited_grid_cells':{k:len(v) for k,v in visited.items()},
            'military_presence_cell_seconds':dict(cell_seconds),
            'observed_tc_queue_empty_seconds':dict(queue_empty_seconds),
            'observed_tc_queue_known_seconds':dict(queue_known_seconds),
            'confirmed_enemy_villagers_killed_by_player':dict(villager_kills),
            'villager_deaths_without_confirmed_hostile_finisher':uncredited,
            'sample_hostile_hits':hits[:10],
            'caveats':['16x16 grid; presence is not control or vision',
                       'TC empty time is whole observed match, includes intentional stop; not the final requested TC metric',
                       'Reported damage is not effective damage or a skill rating',
                       'Entity types inferred from blueprint names; validate classifications before scoring',
                       'Visibility sampled, not proof of player attention; damage events are not automatically reaction opportunities']}


if __name__ == '__main__':
    result = {'own_matches':[own_match(255410440, 'summary-255410440.txt'), own_match(257307543, 'summary-257307543.txt'),
                             own_match(257209177, 'summary-257209177.txt')], 'telemetry_sample':recorded_sample()}
    (ROOT/'tactical-findings.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result['telemetry_sample'],indent=2))
