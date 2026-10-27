"""Skill metrics from recorded game state (.rlog), the replay command stream (parsed .rec) and the AoE4 World summary.

Usage: python -X utf8 skill_metrics.py [--only GID ...] [--recorder DIR]
Reads data/latest10-manifest.json, <recorder>/recordings/aoe4_<gid>.rlog (complete recordings only, per
data/recording-status.json), data/replay-<gid>.rec, data/replay-<gid>.parsed.json (command stream, optional) and
data/summary-<gid>.txt (optional); writes data/skill-analysis.json: every player of every recorded match with raw
metrics and evidence, pool percentiles over all player-matches in the dataset, radar axes per player-match, and each
tracked player's aggregate over every recorded match they appear in. Nothing missing is scored as zero: an unavailable
metric is null and leaves the axis.

Definitions (seconds of game time, metres of world units):
- hostile: attacker and victim owned by different teams; repair ticks and self damage excluded.
- military unit: convert.classify in MILITARY, scouts excluded (villagers, monks, traders, livestock are not military).
- value: the owner's resource quote for the blueprint (convert.entity_value). A villager is worth 400 resources at
  population 0 falling linearly to 100 at population 200, by its owner's population when it dies (Sam: a villager
  scales far beyond its face value, and less the more population the owner has). time weight w(t) = 1 + max(0,
  (1200 - t) / 1200): double at 0:00, 1.5 at 10:00, 1 from 20:00 on; applied to army kills and losses and to resource
  credits so earlier trades and income count more; villagers carry no time weight since their value already does.
- kill credit: the killer the game reports (K record), else the last unit attacking the victim within 3 s.
- enemy half: closer to the nearest enemy capital Town Center than to the player's own.
- combat window: ±5 s around every hostile hit dealt or taken by the player's units, merged.
- fight: convert.detect_fights cluster the player's units take part in. microed: at least two army orders (Move,
  AttackMove, Attack, Stop, Patrol, UnitAbility) to units inside the fight area while it runs. concurrent fronts:
  fights of the player overlapping in time and more than 60 m apart.
- threat: a hostile hit on the player's villager, building, trader, monk, or a unit with no own military unit within
  30 m, where no own entity was hit within 80 m in the previous 30 s. response: the first order within 60 s that
  selects the victim's squad or squads within 30 m of it (Move, AttackMove, SeekShelter, Garrison, UnitAbility,
  Stop) or sends army (AttackMove/Move/Attack) to within 40 m of it. None = censored (counted, never zero seconds).
- first attack advantage: own military value ÷ the victim owner's military value at the player's first hostile hit.
- army value: alive military units' resource value plus the cost of every military technology completed so far
  (blacksmith, university, unit tier and civ military upgrades, from the recorder's technology table), sampled every
  30 s; used for the army milestones, the strongest phase and the first-attack army values (Sam, 2026-10-27).
- pressure: episodes of hostile military hits on the player's entities in their own half (30 s gaps). growth lost =
  villagers lost x 300 + income shortfall against the player's own rate over the 120 s before the episode + villager
  idle seconds priced at income per villager-second, all time-weighted; pressure received = damage taken in the
  episode, time-weighted; components need 2,000+ weighted damage of pressure, otherwise null (never really attacked).
  attackers at once / targets at once = distinct enemy players hitting the player / hit by the player per 10 s window.
- Town Center idle: queue-empty seconds / known seconds, counted only while the player's villager count is below
  the game's peak minus two and below 120 (growing, or replacing losses after a raid), before the last villager, and
  only in seconds where a villager was affordable (50+ food) and the population was not at a housing cap; time at
  the chosen maximum is a plateau, not idle (Sam, 2026-10-27).
- efficiency: population capped share = time at a population cap below the 200 maximum (capped by houses) / sampled time; float minutes = time-weighted mean bank ÷ gather per minute; unspent share = final bank ÷ gathered;
  production idle = seconds of empty queue on military production buildings while the bank held 400+ resources, ÷
  their known seconds.
"""
import argparse, bisect, json, math, re, statistics, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
DEFAULT_RECORDER = HERE.parents[1] / '.cache' / 'aoe4-replay-viewer'
AGES = {'bfeudal_age': 'feudal', 'bcastle_age': 'castle', 'bimperial_age': 'imperial'}
ECO_TECHS = ('wheelbarrow', 'horticulture', 'double_broadax', 'specialized_pick', 'survival_techniques', 'fertilization', 'lumber_preservation', 'acid_distillation', 'shaft_mining', 'forestry', 'professional_scouts', 'textiles')
ARMY_ORDERS = {'Move', 'AttackMove', 'Attack', 'Stop', 'Patrol', 'UnitAbility'}
RESPONSE_ORDERS = ARMY_ORDERS | {'SeekShelter', 'Garrison'}
PRODUCTION = re.compile(r'barracks|archery|stable|siege_workshop|dock|ranged|infantry|cavalry|military', re.I)
VILLAGER_VALUE = 300.0
AFFORDABLE = 400
GRID = 16
DEFENSE_RANGE = [(re.compile(r'keep|castle|fortress|citadel', re.I), 40.0), (re.compile(r'town_center', re.I), 32.0), (re.compile(r'outpost|tower|bastion', re.I), 32.0)]
MARKS = (300, 480, 600, 720, 900, 1200)


# PvP measures averaged by minute count only game time from 6:00 (Sam, 2026-10-28: the pre-contact minutes dilute them).
PVP_FROM = 360.0
# Games shorter than this enter neither the percentile pool nor a player profile (Sam, 2026-10-28).
MIN_GAME_SECONDS = 600.0


def weight(t):
    return 1.0 + max(0.0, (1200.0 - t) / 1200.0)


def clip(v, lo, hi):
    return max(lo, min(hi, v))


class Intervals:
    """Merged [start, end) intervals and their total length."""
    def __init__(self, items=()):
        self.items = []
        for s, e in sorted(items):
            if self.items and s <= self.items[-1][1]:
                self.items[-1][1] = max(self.items[-1][1], e)
            else:
                self.items.append([s, e])

    def contains(self, t):
        i = bisect.bisect_right(self.items, [t, float('inf')]) - 1
        return i >= 0 and self.items[i][0] <= t < self.items[i][1]

    def total(self, lo=0.0, hi=float('inf')):
        return sum(max(0.0, min(e, hi) - max(s, lo)) for s, e in self.items)


def load_commands(gid):
    path = DATA / f'replay-{gid}.parsed.json'
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding='utf-8'))
    cmds = []
    for r in raw['records']:
        if r.get('record') != 'tick':
            continue
        for b in r['blocks']:
            for c in b['commands']:
                if c['name'].startswith(('Periodic', 'PreCommand', 'PostCommand')):
                    continue
                target = None
                for a in c.get('args', []):
                    pos = (a.get('target') or {}).get('position') if isinstance(a, dict) else None
                    if pos:
                        target = (pos['x'], pos['z'])
                squads = [50000 + s['id'] for s in c.get('selection', []) if s.get('kind') == 32]
                entities = [1000005000 + s['id'] for s in c.get('selection', []) if s.get('kind') == 16]
                cmds.append({'t': r['time'], 'pid': c['playerId'] - 1000, 'name': c['name'], 'squads': squads, 'entities': entities, 'target': target})
    cmds.sort(key=lambda c: c['t'])
    profiles = {p['playerId'] - 1000: p.get('profileId') for p in raw['summary']['players']}
    return cmds, profiles


ECON_IDS = ('villager', 'trader', 'trade', 'fishing', 'monk', 'scholar', 'imam', 'prelate', 'warrior-monk', 'shaman', 'scout', 'sheep')
_TECHS = None


def tech_table(recorder, classify, military_kinds):
    """attribName -> (cost, military) from the recorder's viewer/stats.js (aoe4world data): a technology is military
    when any of its effects targets a military unit (the units table classified like the entities), or its name is a
    unit tier (veteran/elite) or blacksmith/university combat upgrade."""
    global _TECHS
    if _TECHS is None:
        text = (recorder / 'viewer' / 'stats.js').read_text(encoding='utf-8')
        stats = json.loads(text[text.index('= {') + 2:text.rindex('}') + 1])
        mil_ids = {u.get('b') for name, u in stats['units'].items() if classify(name, False) in military_kinds and 'scout' not in name}
        table = {}
        for name, t in stats['techs'].items():
            cost = sum(float((t.get('cost') or {}).get(k, 0) or 0) for k in ('f', 'w', 'g', 's'))
            ids = [i for e in (t.get('eff') or []) for i in (e.get('id') or [])]
            military = any(i in mil_ids for i in ids) or bool(re.search(r'veteran|elite|_tier_|bloomery|decarbon|damascus|fitted|insulated|steeled|iron_undermesh|wedge_rivets|angled_surfaces|chemistry|siege_engineering|biology|incendiary|ranged_damage|melee_damage|ranged_armor|melee_armor', name))
            table[name] = (cost, military)
        _TECHS = table
    return _TECHS


def tech_lookup(table, name):
    """Longest known attribName prefix (civ variants share names); the recorder's U names carry a leading 'b'."""
    tk = name[1:].split('_') if name.startswith('b') else name.split('_')
    for n in range(len(tk), 2, -1):
        hit = table.get('_'.join(tk[:n]))
        if hit:
            return hit
    return None


def analyze_match(gid, recorder, tracked):
    sys.path.insert(0, str(recorder / 'tools'))
    import convert, recfile, rlog
    techs = tech_table(recorder, convert.classify, convert.MILITARY)
    rlog_path = recorder / 'recordings' / f'aoe4_{gid}.rlog'
    rec_path = DATA / f'replay-{gid}.rec'
    log = convert.parse_rlog(rlog_path)
    rep = recfile.load(rec_path)
    by_id = {e.id: e for e in log.ents}
    kills = convert.resolve_kills(log, by_id)
    base_values = {e.id: convert.entity_value(e, log.costs) for e in log.ents}
    world = max(log.header['width'], log.header['length'])
    fights = convert.detect_fights(log, base_values, world)
    players = convert.match_players(log, rep)
    duration = max(rep.duration_seconds, log.samples[-1] if log.samples else 0.0)
    teams = {p['idx']: p['team'] for p in players}
    idx_of_pid = {p['pid']: p['idx'] for p in players}
    loaded = load_commands(gid)
    commands, profiles = (loaded if loaded else ([], {}))
    summary = None
    spath = DATA / f'summary-{gid}.txt'
    if spath.exists():
        summary = json.loads(spath.read_text(encoding='utf-8'))
        for sp in summary.get('players', []):
            try:
                pid_match = next((p for p in players if p['name'] == sp.get('name')), None)
                if pid_match and pid_match['pid'] not in profiles:
                    profiles[pid_match['pid']] = int(sp['profile_id'])
            except (TypeError, ValueError):
                pass

    hits, queues, idles, built, income, popstats = [], defaultdict(list), defaultdict(list), [], defaultdict(list), defaultdict(list)
    for kind, r in rlog.read(rlog_path):
        if kind == rlog.HIT:
            if not r.repair and r.attacker and r.damage > 0:
                hits.append(r)
        elif kind == rlog.QUEUE:
            queues[r.id].append(r)
        elif kind == rlog.IDLE:
            idles[r.squad].append(r)
        elif kind == rlog.BUILT:
            built.append(r)
        elif kind == rlog.INCOME:
            income[r.idx].append((r.t, sum(r.res[:4])))
        elif kind == rlog.STATS:
            if r.cap > 0 and r.pop >= 0:
                popstats[r.idx].append((r.t, r.pop, r.cap))

    kind_of = {e.id: convert.classify(e.bp, e.building) for e in log.ents}
    military = {e.id for e in log.ents if kind_of[e.id] in convert.MILITARY and kind_of[e.id] != 'scout' and 'scout' not in e.bp and 'khan' not in e.bp}
    villagers = {e.id for e in log.ents if kind_of[e.id] == 'villager'}
    economic = {e.id for e in log.ents if kind_of[e.id] in ('villager', 'trader', 'monk', 'livestock') or e.building}
    values = {eid: (VILLAGER_VALUE if eid in villagers else v) for eid, v in base_values.items()}

    def pop_at(owner, t):
        rows = popstats.get(owner, [])
        if not rows:
            return None
        i = bisect.bisect_right(rows, (t, float('inf'), float('inf'))) - 1
        return rows[max(0, i)][1]

    def villager_value(owner, t):
        """400 resources at population 0 falling linearly to 100 at population 200 (Sam, 2026-10-27)."""
        pop = pop_at(owner, t)
        return 400.0 - 300.0 * min(1.0, max(0.0, (pop if pop is not None else 100) / 200.0))
    squad_members = defaultdict(list)
    for e in log.ents:
        if e.squad:
            squad_members[e.squad].append(e.id)
    bases = {}
    for e in log.ents:
        if 'town_center_capital' in e.bp and not e.bp.startswith('wpn_'):
            bases.setdefault(e.owner, e.position_at(e.born)[:2])

    def owner_at(eid, t):
        e = by_id.get(eid)
        return e.owner_at(t) if e else None

    def hostile(a_owner, v_owner):
        return a_owner in teams and v_owner in teams and a_owner != v_owner and teams[a_owner] != teams[v_owner]

    def enemy_half(owner, x, z):
        home = bases.get(owner)
        enemies = [b for o, b in bases.items() if o in teams and teams[o] != teams.get(owner)]
        if not home or not enemies:
            return None
        return min(math.dist((x, z), b) for b in enemies) < math.dist((x, z), home)

    # Sides (Sam, 2026-10-28: "4v4 is kinda like 2v2 and 3v3, half scaling when attacked by the middle"): each team splits into
    # a left and a right half along the front, the line through both teams' base centroids; with an odd team size the middle
    # player belongs to both halves (half each); a team of two or fewer is a single side. Both teams are ordered on the same
    # axis, so a left half faces the other team's left half. off_side(a, b): 0 same side, 1 opposite side, 0.5 with a middle.
    side_of, side_label = {}, {}
    team_ids = sorted(set(teams.values()))
    if len(team_ids) == 2 and all(o in bases for o in teams):
        cent = {t: (statistics.mean(bases[o][0] for o in teams if teams[o] == t), statistics.mean(bases[o][1] for o in teams if teams[o] == t)) for t in team_ids}
        fx, fz = cent[team_ids[1]][0] - cent[team_ids[0]][0], cent[team_ids[1]][1] - cent[team_ids[0]][1]
        for t in team_ids:
            members = sorted((o for o in teams if teams[o] == t), key=lambda o: bases[o][0] * -fz + bases[o][1] * fx)
            n = len(members)
            for k, o in enumerate(members):
                if n <= 2:
                    side_of[o], side_label[o] = (0.5, 0.5), 'one side'
                elif n % 2 and k == n // 2:
                    side_of[o], side_label[o] = (0.5, 0.5), 'middle'
                else:
                    side_of[o], side_label[o] = ((1.0, 0.0), 'left') if k < n / 2 else ((0.0, 1.0), 'right')

    def off_side(a, b):
        sa, sb = side_of.get(a), side_of.get(b)
        return 0.5 * (abs(sa[0] - sb[0]) + abs(sa[1] - sb[1])) if sa and sb else None

    hostile_hits = []
    for h in hits:
        ao, vo = owner_at(h.attacker, h.t), owner_at(h.victim, h.t)
        if hostile(ao, vo):
            hostile_hits.append((h.t, h.attacker, h.victim, h.damage, ao, vo))
    hits_by_victim = defaultdict(list)
    for t, a, v, d, ao, vo in hostile_hits:
        hits_by_victim[v].append((t, a, ao, d))

    # Per-second military presence, enemy-half time, and army value every 30 s.
    seconds = int(duration) + 1
    presence = {idx: [set() for _ in range(seconds)] for idx in teams}
    enemy_half_sec = {idx: [False] * seconds for idx in teams}
    first_enemy_half = {}
    cell_of = lambda x, z: (int(clip((x + world / 2) / (world / GRID), 0, GRID - 1)), int(clip((z + world / 2) / (world / GRID), 0, GRID - 1)))
    army_series = {idx: [] for idx in teams}
    army_steps = list(range(0, int(duration) + 1, 30))
    army_sum = {idx: [0.0] * len(army_steps) for idx in teams}
    for e in log.ents:
        if e.id not in military:
            continue
        for s, end in e.spans:
            end = duration if end is None else end
            for sec in range(int(math.ceil(s)), int(min(end, duration)) + 1):
                x, z, hp = e.position_at(sec)
                if hp <= 0:
                    continue
                o = e.owner_at(sec)
                if o not in presence:
                    continue
                presence[o][sec].add(cell_of(x, z))
                if enemy_half(o, x, z):
                    enemy_half_sec[o][sec] = True
                    if o not in first_enemy_half or sec < first_enemy_half[o]:
                        first_enemy_half[o] = sec
                if sec % 30 == 0:
                    army_sum[o][sec // 30] += values.get(e.id, 0.0)
    for idx in teams:
        army_series[idx] = [[t, round(v)] for t, v in zip(army_steps, army_sum[idx])]

    def army_value_at(idx, t):
        i = min(len(army_steps) - 1, max(0, int(t // 30)))
        return army_sum[idx][i]

    # Cells inside the attack range of standing defensive buildings, per second, per owner (from completion)
    completed_at = {}
    for c in log.constructions:
        ent = c['fields'].get('entity', '')
        if ent.startswith('e') and ent[1:].isdigit():
            completed_at.setdefault(int(ent[1:]), c['t'])
    cell_size = world / GRID
    defense_cells = {idx: [0] * seconds for idx in teams}
    for idx in teams:
        per_second = [set() for _ in range(seconds)]
        for e in log.ents:
            if not e.building or e.bp.startswith('wpn_'):
                continue
            rng = next((r for rx, r in DEFENSE_RANGE if rx.search(e.bp)), None)
            if rng is None:
                continue
            x, z, _ = e.position_at(e.born)
            cells = set()
            for cx in range(GRID):
                for cz in range(GRID):
                    centre = (-world / 2 + (cx + 0.5) * cell_size, -world / 2 + (cz + 0.5) * cell_size)
                    if math.dist(centre, (x, z)) <= rng:
                        cells.add((cx, cz))
            start = completed_at.get(e.id, e.born)
            for s_, end in e.spans:
                lo = max(s_, start)
                hi = duration if end is None else end
                for sec in range(int(math.ceil(lo)), int(min(hi, duration)) + 1):
                    if e.owner_at(sec) == idx:
                        per_second[sec] |= cells
        defense_cells[idx] = [len(c) for c in per_second]
    villager_series = {idx: [] for idx in teams}
    for minute in range(0, int(duration) // 60 + 1):
        t = minute * 60
        counts = defaultdict(int)
        for e in log.ents:
            if e.id in villagers and e.alive_at(t):
                counts[e.owner_at(t)] += 1
        for idx in teams:
            villager_series[idx].append([t, counts.get(idx, 0)])

    age_time, eco_time = defaultdict(dict), defaultdict(dict)
    tech_spend = defaultdict(list)   # owner -> [(t, cost, name)] completed military technologies
    for u in log.upgrades:
        name = u['fields'].get('upgrade', '')
        ex = u['fields'].get('executer', '')
        owner = owner_at(int(ex[1:]), u['t']) if ex.startswith('e') and ex[1:].isdigit() else (idx_of_pid.get(int(ex[1:]) - 1000) if ex.startswith('p') and ex[1:].isdigit() else None)
        if owner is None:
            continue
        if name in AGES:
            age_time[owner].setdefault(AGES[name], u['t'])
        for key in ECO_TECHS:
            if key in name and 'upgrade' in name:
                eco_time[owner].setdefault(key, u['t'])
        hit = tech_lookup(techs, name)
        if hit and hit[1] and hit[0] > 0:
            tech_spend[owner].append((u['t'], hit[0], name))
    # Army value = alive military units' value + military technologies completed so far (Sam, 2026-10-27)
    army_units_only = {idx: list(v) for idx, v in army_sum.items()}
    for idx in teams:
        spent = sorted(tech_spend.get(idx, []))
        running, j = 0.0, 0
        for i, t in enumerate(army_steps):
            while j < len(spent) and spent[j][0] <= t:
                running += spent[j][1]; j += 1
            army_sum[idx][i] += running
        army_series[idx] = [[t, round(v)] for t, v in zip(army_steps, army_sum[idx])]

    fielded = defaultdict(float)
    fielded_military = defaultdict(float)
    for e in log.ents:
        if e.building or kind_of[e.id] in convert.NON_COMBAT:
            continue
        fielded[e.owner] += villager_value(e.owner, e.born) if e.id in villagers else values.get(e.id, 0.0)
        if e.id in military:
            fielded_military[e.owner] += values.get(e.id, 0.0)
    results = []
    for p in players:
        idx = p['idx']
        enemies = [o for o in teams if teams[o] != teams[idx]]
        enemy_fielded = sum(fielded.get(o, 0.0) for o in enemies)
        own_ents = [e for e in log.ents if e.owner == idx]
        cmds_mine = [c for c in commands if c['pid'] == p['pid']]
        dealt = [(t, a, v, d, vo) for t, a, v, d, ao, vo in hostile_hits if ao == idx]
        taken = [(t, a, v, d, ao) for t, a, v, d, ao, vo in hostile_hits if vo == idx]
        damage_dealt = sum(d for _, _, _, d, _ in dealt)
        military_damage = sum(d for _, a, _, d, _ in dealt if a in military)
        army_resources = fielded_military.get(idx, 0.0) + sum(c for _, c, _ in tech_spend.get(idx, []))
        damage_per_resource = round(military_damage / army_resources, 3) if army_resources >= 500 else None
        damage_taken = sum(d for _, _, _, d, _ in taken)
        # Time-weighted damage per minute of game time from 6:00 (weight: double at 0:00 to 1 from 20:00; Sam, 2026-10-28).
        pvp_min = max(1.0, (duration - PVP_FROM) / 60)
        w_taken = sum(d * weight(t) for t, _, _, d, _ in taken) / pvp_min
        w_dealt = sum(d * weight(t) for t, a, _, d, _ in dealt if a in military) / pvp_min
        w_off_side = sum(d * weight(t) * (off_side(idx, ao) or 0.0) for t, _, _, d, ao in taken) / pvp_min if idx in side_of else None
        team_damage = sum(d for t, a, v, d, ao, vo in hostile_hits if teams.get(ao) == teams[idx])

        def command_point(c):
            for sq in c['squads']:
                for eid in squad_members.get(sq, []):
                    e = by_id.get(eid)
                    if e and e.alive_at(c['t']):
                        x, z, _ = e.position_at(c['t'])
                        return (x, z)
            return c['target']

        # Kills, losses (raw and time-weighted), villager kills with assists, raids
        killed = {'unit': 0.0, 'building': 0.0, 'unitW': 0.0}
        lost = {'unit': 0.0, 'building': 0.0, 'unitW': 0.0}
        kill_rows, vill_kills, own_vill_lost = [], [], []
        for k in kills:
            v = by_id[k['victim']]
            vo = v.owner_at(k['t'])
            ko = owner_at(k['killer'], k['t']) if k['killer'] is not None else None
            bucket = 'building' if v.building else 'unit'
            is_vill = v.id in villagers
            val = villager_value(vo, k['t']) if is_vill else values.get(v.id, 0.0)
            w = 1.0 if is_vill else weight(k['t'])  # the villager value already encodes earliness through population
            if ko == idx and hostile(ko, vo):
                killed[bucket] += val
                if bucket == 'unit':
                    killed['unitW'] += val * w
                x, z, _ = v.position_at(k['t'])
                kill_rows.append({'t': round(k['t'], 2), 'victim': v.bp, 'value': round(val, 1), 'weighted': round(val * w, 1), 'x': round(x, 1), 'z': round(z, 1), 'victimOwner': vo})
                if v.id in villagers:
                    assists = sorted({ao for t, a, ao, d in hits_by_victim[v.id] if k['t'] - 10 <= t <= k['t'] and ao != idx and teams.get(ao) == teams[idx]})
                    vill_kills.append({'t': round(k['t'], 2), 'x': round(x, 1), 'z': round(z, 1), 'victimOwner': vo, 'assists': assists, 'victimPopulation': pop_at(vo, k['t']), 'weighted': round(val, 1)})
            if vo == idx and v.killed and (ko is None or hostile(ko, vo)):
                lost[bucket] += val
                if bucket == 'unit':
                    lost['unitW'] += val * w
                if v.id in villagers:
                    own_vill_lost.append({'t': round(k['t'], 2), 'killer': ko, 'value': round(val, 1)})
        raids = []
        for vk in sorted(vill_kills, key=lambda r: r['t']):
            if raids and vk['t'] - raids[-1]['last'] <= 30 and math.dist((vk['x'], vk['z']), (raids[-1]['x'], raids[-1]['z'])) <= 40:
                raids[-1]['last'] = vk['t']; raids[-1]['kills'] += 1
            else:
                raids.append({'first': vk['t'], 'last': vk['t'], 'x': vk['x'], 'z': vk['z'], 'kills': 1})

        # Fights the player is in, with micro orders inside each
        my_fights = []
        for f in fights:
            if idx not in f['participants']:
                continue
            own = f['losses'].get(str(idx)) or f['losses'].get(idx) or {}
            enemy_lost = sum((f['losses'].get(str(o)) or f['losses'].get(o) or {}).get('value', 0) for o in f['participants'] if teams.get(o) != teams[idx])
            team_lost = sum((f['losses'].get(str(o)) or f['losses'].get(o) or {}).get('value', 0) for o in f['participants'] if teams.get(o) == teams[idx])
            reach = f['radius'] * 1.5 + 10
            my_kills = sum(r['weighted'] for r in kill_rows if f['start'] - 2 <= r['t'] <= f['end'] + 2 and math.dist((r['x'], r['z']), (f['x'], f['z'])) <= reach)
            my_lost_w = own.get('value', 0) * weight(f['start'])
            micro = 0
            if cmds_mine:
                for c in cmds_mine:
                    if c['t'] < f['start'] - 3 or c['name'] not in ARMY_ORDERS or not c['squads']:
                        continue
                    if c['t'] > f['end'] + 3:
                        break
                    pt = command_point(c)
                    if pt and math.dist(pt, (f['x'], f['z'])) <= reach:
                        micro += 1
            my_fights.append({'start': round(f['start'], 1), 'end': round(f['end'], 1), 'x': round(f['x'], 1), 'z': round(f['z'], 1), 'radius': round(f['radius'], 1), 'ownLost': round(own.get('value', 0), 1), 'ownLostWeighted': round(my_lost_w, 1), 'teamLost': round(team_lost, 1), 'enemyLost': round(enemy_lost, 1), 'ownKilled': round(my_kills, 1), 'microOrders': micro if cmds_mine else None, 'participants': f['participants']})
        # Share of the enemy army killed per minute: value killed in each minute / the enemy players' army value
        # (units only) at that minute x number of enemies, averaged over minutes where the enemy fielded 500+ of army
        shares = []
        for minute in range(int(PVP_FROM) // 60, int(duration) // 60 + 1):
            t0 = minute * 60
            enemy_army = sum(army_units_only[o][min(len(army_steps) - 1, t0 // 30)] for o in enemies) if army_steps else 0
            if enemy_army < 500:
                continue
            killed_now = sum(r['value'] for r in kill_rows if t0 <= r['t'] < t0 + 60 and not r['victim'].startswith('building_'))
            shares.append(killed_now / enemy_army * len(enemies))
        kill_share_per_minute = round(sum(shares) / len(shares), 4) if len(shares) >= 5 else None
        with_stake = [f for f in my_fights if f['ownLostWeighted'] > 0 or f['ownKilled'] > 0]
        fights_won = sum(1 for f in with_stake if f['ownKilled'] > f['ownLostWeighted'])
        team_fights_won = sum(1 for f in my_fights if f['enemyLost'] > f['teamLost'])
        microed = sum(1 for f in my_fights if (f['microOrders'] or 0) >= 2)
        # Concurrent fronts: per fight-second, how many of the player's fights more than 60 m apart run at once
        front_seconds = defaultdict(float)
        multi_front = multi_front_microed = 0
        for i, f in enumerate(my_fights):
            for g in my_fights[i + 1:]:
                if g['start'] < f['end'] and f['start'] < g['end'] and math.dist((f['x'], f['z']), (g['x'], g['z'])) > 60:
                    multi_front += 1
                    if (f['microOrders'] or 0) >= 2 and (g['microOrders'] or 0) >= 2:
                        multi_front_microed += 1
        multi_time = all_microed_time = 0.0
        if my_fights:
            edges = sorted({f['start'] for f in my_fights} | {f['end'] for f in my_fights})
            total_fs = weighted_fs = 0.0
            for a, b in zip(edges, edges[1:]):
                mid = (a + b) / 2
                active = [f for f in my_fights if f['start'] <= mid < f['end']]
                if not active:
                    continue
                fronts, centres, front_fights = 0, [], []
                for f in active:
                    if not any(math.dist((f['x'], f['z']), c) <= 60 for c in centres):
                        centres.append((f['x'], f['z'])); fronts += 1; front_fights.append(f)
                total_fs += b - a; weighted_fs += (b - a) * fronts
                if fronts >= 2 and cmds_mine:
                    multi_time += b - a
                    if all((f['microOrders'] or 0) >= 2 for f in front_fights):
                        all_microed_time += b - a
            mean_fronts = round(weighted_fs / total_fs, 2) if total_fs else None
        else:
            mean_fronts = None

        combat = Intervals([(t - 5, t + 5) for t, *_ in dealt] + [(t - 5, t + 5) for t, *_ in taken])
        # Villagers, Town Centers, idle
        vill_built = sorted(b.t for b in built if b.idx == idx and 'villager' in b.bp)
        last_vill = vill_built[-1] if vill_built else None
        # Villager production phases: seconds where the villager count is below the game's peak minus two (still
        # growing, or replacing losses after a raid); a plateau at the player's chosen maximum does not count as idle.
        own_vills = [e for e in own_ents if e.id in villagers]
        vill_count = [sum(1 for e in own_vills if e.alive_at(s)) for s in range(0, seconds, 5)]
        peak_vill = max(vill_count) if vill_count else 0
        pops = popstats.get(idx, [])
        capped_time = known_pop = headroom_area = 0.0
        for i, (t, pop, cap) in enumerate(pops[:-1]):
            dt = pops[i + 1][0] - t
            known_pop += dt
            headroom_area += (cap - pop) * dt
            if pop >= cap and cap < 200:
                capped_time += dt
        pop_capped_share = round(capped_time / known_pop, 3) if known_pop > 60 else None
        mean_headroom = round(headroom_area / known_pop, 1) if known_pop > 60 else None
        def capped_at(t):
            i = bisect.bisect_right(pops, (t, float('inf'), float('inf'))) - 1
            return i >= 0 and pops[i][2] < 200 and pops[i][1] >= pops[i][2]

        growing = Intervals([(s * 5, s * 5 + 5) for s, n in enumerate(vill_count) if n < peak_vill - 2 and n < 120])
        stats_rows = log.stats.get(idx, [])

        def food_at(t):
            i = bisect.bisect_right(stats_rows, [t, float('inf')]) - 1
            return stats_rows[i][1] if i >= 0 else 0

        def could_produce(t):
            return food_at(t) >= 50 and not capped_at(t)

        plateau_seconds = round(max(0.0, (last_vill or duration) - growing.total(0, last_vill or duration)))
        tc_known = tc_empty = tc_c_known = tc_c_empty = 0.0
        tc_rows = []
        for tc in [e for e in own_ents if e.bp.startswith('building_town_center')]:
            q = queues.get(tc.id, [])
            if not q or last_vill is None or not any(r.size > 0 for r in q):
                continue
            end_cut = min(last_vill, tc.died if tc.died is not None else duration)
            empty = known = c_known = c_empty = 0.0
            for i, r in enumerate(q):
                nxt = q[i + 1].t if i + 1 < len(q) else end_cut
                lo, hi = r.t, min(nxt, end_cut)
                if hi <= lo:
                    continue
                span = growing.total(lo, hi)
                if span <= 0:
                    continue
                known += span
                c = sum(combat.total(max(lo, a), min(hi, b)) for a, b in growing.items if b > lo and a < hi)
                c_known += c
                if r.size == 0:
                    idle_here = idle_combat_here = 0.0
                    for a, b in growing.items:
                        t = max(lo, a)
                        while t < min(hi, b):
                            step = min(5.0, min(hi, b) - t)
                            if could_produce(t):
                                idle_here += step
                                idle_combat_here += combat.total(t, t + step)
                            t += step
                    empty += idle_here; c_empty += idle_combat_here
            tc_known += known; tc_empty += empty; tc_c_known += c_known; tc_c_empty += c_empty
            tc_rows.append({'bp': tc.bp, 'from': round(q[0].t, 1), 'to': round(end_cut, 1), 'emptySeconds': round(empty, 1), 'knownSeconds': round(known, 1)})
        idle_seconds = vill_seconds = 0.0
        for e in own_ents:
            if e.id not in villagers:
                continue
            vill_seconds += Intervals([(s, duration if end is None else end) for s, end in e.spans]).total()
            spans, start = [], None
            for r in idles.get(e.squad, []):
                if r.idle and start is None:
                    start = r.t
                elif not r.idle and start is not None:
                    spans.append((start, r.t)); start = None
            if start is not None:
                spans.append((start, e.died if e.died is not None else duration))
            idle_seconds += sum(min(b, duration) - a for a, b in spans if b > a)
        vill_at = {str(m): sum(1 for e in own_ents if e.id in villagers and e.alive_at(m)) for m in MARKS if m <= duration}
        pop_at_marks = {str(m): pop_at(idx, m) for m in MARKS if m <= duration}

        # Resources: gathered (raw and early-weighted), bank float, unspent
        credits = income.get(idx, [])
        gathered = sum(v for _, v in credits)
        gathered_w = sum(v * weight(t) for t, v in credits)
        gathered_by = {str(m): round(sum(v for t, v in credits if t <= m)) for m in MARKS if m <= duration}
        stats = log.stats.get(idx, [])
        bank_series = [(row[0], sum(row[1:5])) for row in stats]
        bank_area = sum((bank_series[i + 1][0] - t) * b for i, (t, b) in enumerate(bank_series[:-1]))
        bank_span = bank_series[-1][0] - bank_series[0][0] if len(bank_series) > 1 else 0
        mean_bank = bank_area / bank_span if bank_span else None
        final_bank = bank_series[-1][1] if bank_series else None
        gather_pm = gathered / (duration / 60) if duration else None
        # Army milestones: first time the army value reaches 3,000 and 8,000 resources, and the biggest two-minute rise
        series = army_sum[idx]
        milestone = {str(v): next((t for t, a in zip(army_steps, series) if a >= v), None) for v in (3000, 8000)}
        bump, bump_at = 0.0, None
        for i in range(len(series)):
            j = min(len(series) - 1, i + 4)
            if series[j] - series[i] > bump:
                bump, bump_at = series[j] - series[i], army_steps[i]

        def bank_at(t):
            i = bisect.bisect_right(bank_series, (t, float('inf'))) - 1
            return bank_series[i][1] if i >= 0 else 0

        # Resources locked in military queues: units queued behind the one in production (all of them while the player
        # sits at the population cap) times the unit's quoted cost, time-weighted over the game.
        def quote_cost(owner, bp, t):
            quotes = log.costs.get((owner, bp)) or []
            best = None
            for qte in quotes:
                if qte['t'] <= t or qte['t'] == float('-inf'):
                    best = qte
            if best is None and quotes:
                best = quotes[0]
            return sum(v for k, v in (best['cost'] or {}).items() if k in ('food', 'wood', 'gold', 'stone')) if best else 0.0

        locked_area = 0.0
        minutes_n = int(duration) // 60 + 1
        locked_at_minute = [0.0] * minutes_n
        # Military production idle while affordable
        prod_known = prod_idle_aff = prod_idle = 0.0
        for b in own_ents:
            if not b.building or not PRODUCTION.search(b.bp) or b.bp.startswith('building_town_center'):
                continue
            q = queues.get(b.id, [])
            if not q or not any(r.size > 0 for r in q):
                continue
            end_cut = b.died if b.died is not None else duration
            for i, r in enumerate(q):
                nxt = q[i + 1].t if i + 1 < len(q) else end_cut
                lo, hi = r.t, min(nxt, end_cut)
                if hi <= lo:
                    continue
                prod_known += hi - lo
                if r.size >= 1 and r.kind == 'spawn' and r.bp != '-':
                    cost = quote_cost(idx, r.bp, lo)
                    t = lo
                    while t < hi:
                        step = min(10.0, hi - t)
                        waiting = r.size - (0 if capped_at(t) else 1)
                        if waiting > 0:
                            locked_area += waiting * cost * step
                        t += step
                    for mnt in range(int(lo // 60), int(hi // 60) + 1):
                        tm = mnt * 60
                        if lo <= tm < hi and mnt < minutes_n:
                            waiting = r.size - (0 if capped_at(tm) else 1)
                            if waiting > 0:
                                locked_at_minute[mnt] += waiting * cost
                if r.size == 0:
                    prod_idle += hi - lo
                    t = lo
                    while t < hi:
                        step = min(10.0, hi - t)
                        if bank_at(t) >= AFFORDABLE:
                            prod_idle_aff += step
                        t += step

        # Pressure: episodes of hostile military hits on own entities in own half; growth lost during them
        own_half_hits = []
        for t, a, v, d, ao in taken:
            if a not in military:
                continue
            ent = by_id.get(v)
            x, z, _ = ent.position_at(t)
            eh = enemy_half(idx, x, z)
            if eh is False:
                own_half_hits.append((t, ao, d, v))
        episodes = []
        for t, ao, d, v in own_half_hits:
            if episodes and t - episodes[-1]['end'] <= 30:
                ep = episodes[-1]; ep['end'] = t; ep['damage'] += d; ep['attackers'].add(ao)
            else:
                episodes.append({'start': t, 'end': t, 'damage': d, 'attackers': {ao}})
        income_sorted = credits
        def income_between(lo, hi):
            i = bisect.bisect_left(income_sorted, (lo, -1.0)); total = 0.0
            while i < len(income_sorted) and income_sorted[i][0] < hi:
                total += income_sorted[i][1]; i += 1
            return total
        vill_idle_spans = []
        for e_ in own_ents:
            if e_.id not in villagers:
                continue
            start = None
            for r in idles.get(e_.squad, []):
                if r.idle and start is None:
                    start = r.t
                elif not r.idle and start is not None:
                    vill_idle_spans.append((start, r.t)); start = None
            if start is not None:
                vill_idle_spans.append((start, e_.died if e_.died is not None else duration))
        income_per_vill_sec = (gathered / vill_seconds) if vill_seconds else 0.0
        pressure_total = growth_lost_total = expected_income_total = episode_income_total = 0.0
        vill_lost_pressure = 0
        episode_rows = []
        for ep in episodes:
            dur = max(10.0, ep['end'] - ep['start'] + 10)
            lo, hi = ep['start'], ep['start'] + dur
            pre_rate = income_between(lo - 120, lo) / 120.0
            # Expected income keeps the economy's own growth (Sam, 2026-10-28): the rate's slope over the two minutes before
            # the episode (never negative; the rate at most doubles by the episode's end) carries on through the episode.
            # pre_rate is the mean over [lo-120, lo], centred 60 s before the episode starts.
            earlier = income_between(lo - 240, lo - 120) / 120.0 if lo >= 240 else None
            slope = max(0.0, (pre_rate - earlier) / 120.0) if earlier is not None and earlier > 0 else 0.0
            slope = min(slope, pre_rate / (60.0 + dur))
            expected = pre_rate * dur + slope * (60.0 * dur + dur * dur / 2.0)
            actual = income_between(lo, hi)
            shortfall = max(0.0, expected - actual)
            vlost = [r for r in own_vill_lost if lo <= r['t'] <= hi]
            idle = sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in vill_idle_spans if b > lo and a < hi)
            w = weight(lo)
            lost_here = sum(r['value'] for r in vlost) + shortfall * w + idle * income_per_vill_sec * w
            pressure = ep['damage'] * w
            pressure_total += pressure; growth_lost_total += lost_here; expected_income_total += expected; episode_income_total += actual
            vill_lost_pressure += len(vlost)
            episode_rows.append({'start': round(lo, 1), 'end': round(hi, 1), 'attackers': sorted(ep['attackers']), 'damage': round(ep['damage']), 'villagersLost': len(vlost), 'incomeExpected': round(expected), 'incomeActual': round(actual), 'villagerIdleSeconds': round(idle), 'growthLost': round(lost_here)})
        # Attackers at once (hits taken) and targets at once (hits dealt), per 10 s window
        def owners_per_window(rows, key):
            windows = defaultdict(set)
            for row in rows:
                windows[int(row[0] // 10)].add(row[key])
            counts = [len(s) for s in windows.values()]
            return (round(sum(counts) / len(counts), 2), max(counts)) if counts else (None, None)
        attackers_by_minute = defaultdict(set)
        for t_, a_, v_, d_, ao_ in taken:
            attackers_by_minute[int(t_ // 60)].add(ao_)
        peak_attackers_minute = max((len(x) for x in attackers_by_minute.values()), default=0)
        # Minutes in which at least N distinct enemy players hit anything of this player's (Sam, 2026-10-28).
        attacked_by = {n: sum(1 for x in attackers_by_minute.values() if len(x) >= n) for n in (2, 3, 4)}
        attackers_mean, attackers_max = owners_per_window([(t, a, v, d, ao) for t, a, v, d, ao in taken if a in military], 4)
        targets_mean, targets_max = owners_per_window([(t, a, v, d, vo) for t, a, v, d, vo in dealt if a in military], 4)
        income_minute = [0.0] * minutes_n
        for t_, v_ in credits:
            k_ = int(t_ // 60)
            if k_ < minutes_n:
                income_minute[k_] += v_
        float_shares, queued_shares = [], []
        for mnt in range(1, minutes_n):
            inc = income_minute[mnt]
            if inc < 50:
                continue
            float_shares.append(bank_at(mnt * 60) / inc)
            queued_shares.append(locked_at_minute[mnt] / inc)
        float_share = round(sum(float_shares) / len(float_shares), 3) if len(float_shares) >= 5 else None
        queued_share = round(sum(queued_shares) / len(queued_shares), 3) if len(queued_shares) >= 5 and prod_known > 120 else None
        # Threats on economy / undefended units and responses
        threats, recent = [], []
        for t, a, v, d, ao, vo in hostile_hits:
            if idx not in (ao, vo):
                continue
            ent = by_id.get(v)
            x, z, _ = ent.position_at(t)
            if vo == idx:
                if not any(t - 30 <= rt <= t and math.dist((x, z), (rx, rz)) <= 80 for rt, rx, rz in recent[-600:]):
                    defended = v not in economic and any(o.id in military and o.id != v and o.alive_at(t) and math.dist(o.position_at(t)[:2], (x, z)) <= 30 for o in own_ents)
                    if v in economic or not defended:
                        threats.append({'t': round(t, 2), 'x': round(x, 1), 'z': round(z, 1), 'victim': ent.bp, 'victimSquad': ent.squad, 'attackerOwner': ao, 'kind': 'economy' if v in economic else 'undefended unit'})
            recent.append((t, x, z))
        responses = []
        if cmds_mine:
            for th in threats:
                lat = None; cmd_name = None
                for c in cmds_mine:
                    if c['t'] < th['t']:
                        continue
                    if c['t'] > th['t'] + 60:
                        break
                    if c['name'] not in RESPONSE_ORDERS:
                        continue
                    near = False
                    if th['victimSquad'] and th['victimSquad'] in c['squads']:
                        near = True
                    if not near and c['squads']:
                        for sq in c['squads']:
                            for eid in squad_members.get(sq, []):
                                e = by_id.get(eid)
                                if e and e.alive_at(c['t']) and math.dist(e.position_at(c['t'])[:2], (th['x'], th['z'])) <= 30:
                                    near = True; break
                            if near:
                                break
                    if not near and c['name'] in ARMY_ORDERS and c['target'] and math.dist(c['target'], (th['x'], th['z'])) <= 40:
                        near = True
                    if near:
                        lat = round(c['t'] - th['t'], 2); cmd_name = c['name']; break
                responses.append({'t': th['t'], 'kind': th['kind'], 'latency': lat, 'command': cmd_name, 'victim': th['victim']})
        latencies = [r['latency'] for r in responses if r['latency'] is not None]
        per_minute = {}
        for k_, th in enumerate(threats):
            rs = responses[k_] if cmds_mine and k_ < len(responses) else None
            row = per_minute.setdefault(int(th['t'] // 60), [0, 0])
            row[0] += 1
            if rs and rs['latency'] is not None:
                row[1] += 1
        minute_rates = [a / n for n, a in per_minute.values() if n]
        answered_share_per_minute = round(sum(minute_rates) / len(minute_rates), 3) if cmds_mine and len(minute_rates) >= 3 else None
        by_attacker = {}
        for k_, th in enumerate(threats):
            rs = responses[k_] if cmds_mine and k_ < len(responses) else None
            row = by_attacker.setdefault(th['attackerOwner'], {'threats': 0, 'answered': 0})
            row['threats'] += 1
            if rs and rs['latency'] is not None:
                row['answered'] += 1

        ages = age_time.get(idx, {})
        eco = eco_time.get(idx, {})
        first_dealt = next((h for h in dealt if h[1] in military), None)
        running_dmg, damage_1000_at = 0.0, None
        for t_, a_, v_, d_, vo_ in dealt:
            if a_ not in military:
                continue
            running_dmg += d_
            if running_dmg >= 1000:
                damage_1000_at = round(t_, 1)
                break
        first_attack_adv = None
        if first_dealt:
            own_av, foe_av = army_value_at(idx, first_dealt[0]), army_value_at(first_dealt[4], first_dealt[0])
            first_attack_adv = round(math.log((own_av + 100) / (foe_av + 100)), 3)
        peak = max(army_sum[idx]) if army_sum[idx] else 0
        phase_w = lambda t: 3.0 if t < 600 else 2.0 if t < 1200 else 1.0
        weighted_army = round(sum(v * phase_w(t) for t, v in zip(army_steps, army_sum[idx])) / len(army_steps)) if army_steps else None
        strong_phase = next((t for t, v in zip(army_steps, army_sum[idx]) if peak > 0 and v >= 0.8 * peak), None)
        pres = presence[idx]
        minutes = max(1.0, duration / 60)
        pvp_minutes = max(1.0, (duration - PVP_FROM) / 60)
        pvp_seconds = max(1, int(duration - PVP_FROM))
        pvp_sec0 = int(PVP_FROM)
        cell_seconds = sum(len(s) for s in pres[pvp_sec0:])
        visited = set().union(*pres) if pres else set()
        contested = 0
        for sec in range(pvp_sec0, seconds):
            mine = pres[sec]
            if not mine:
                continue
            enemy_cells = set().union(*(presence[o][sec] for o in teams if teams[o] != teams[idx]))
            contested += len(mine & enemy_cells)
        vill_in_combat = sum(1 for t in vill_built if combat.contains(t))
        combat_total = combat.total(0, last_vill or duration)
        quiet_total = max(0.0, (last_vill or duration) - combat_total)
        # Efficiency while fighting: the efficiency shares measured inside combat windows only, combined into one score
        idle_in_combat = sum(combat.total(a, b) for a, b in vill_idle_spans)
        vill_sec_in_combat = sum(combat.total(s, duration if end is None else end) for e_ in own_vills for s, end in e_.spans)
        prod_idle_c = prod_known_c = 0.0
        for b_ in own_ents:
            if not b_.building or not PRODUCTION.search(b_.bp) or b_.bp.startswith('building_town_center'):
                continue
            q = queues.get(b_.id, [])
            if not q or not any(r.size > 0 for r in q):
                continue
            end_cut = b_.died if b_.died is not None else duration
            for i, r in enumerate(q):
                nxt = q[i + 1].t if i + 1 < len(q) else end_cut
                lo, hi = r.t, min(nxt, end_cut)
                if hi <= lo:
                    continue
                c = combat.total(lo, hi)
                prod_known_c += c
                if r.size == 0:
                    prod_idle_c += c
        combat_shares = [x for x in (tc_c_empty / tc_c_known if tc_c_known > 30 else None, idle_in_combat / vill_sec_in_combat if vill_sec_in_combat > 60 else None, prod_idle_c / prod_known_c if prod_known_c > 60 else None) if x is not None]
        combat_efficiency = round(sum(1 - x for x in combat_shares) / len(combat_shares), 3) if combat_shares else None
        vk_weighted = sum(v['weighted'] for v in vill_kills)
        m = {
            'profileId': profiles.get(p['pid']), 'name': p['name'], 'civ': p['civ'], 'team': p['team'], 'idx': idx, 'tracked': profiles.get(p['pid']) in tracked,
            'durationSeconds': round(duration, 1),
            'combat': {'damageDealt': round(damage_dealt), 'damageTaken': round(damage_taken), 'teamDamageShare': round(damage_dealt / team_damage, 3) if team_damage else None,
                       'valueKilledUnits': round(killed['unit']), 'valueKilledUnitsWeighted': round(killed['unitW']), 'valueKilledBuildings': round(killed['building']), 'valueLostUnits': round(lost['unit']), 'valueLostUnitsWeighted': round(lost['unitW']), 'valueLostBuildings': round(lost['building']),
                       'tradeRatio': round(killed['unitW'] / lost['unitW'], 3) if lost['unitW'] else None, 'netValueTraded': round(killed['unitW'] - lost['unitW']), 'enemyValueFielded': round(enemy_fielded), 'enemyCount': len(enemies), 'valueKilledShare': kill_share_per_minute, 'damagePerResource': damage_per_resource, 'armyResources': round(army_resources), 'militaryDamage': round(military_damage),
                       'fights': len(my_fights), 'fightsWithStake': len(with_stake), 'fightsWonPersonal': fights_won, 'teamFightsWon': team_fights_won,
                       'damagePerCombatMinute': round(damage_dealt / (combat.total() / 60), 1) if combat.total() > 30 else None, 'combatSeconds': round(combat.total(), 1), 'firstHostileHitDealt': round(first_dealt[0], 1) if first_dealt else None, 'damage1000At': damage_1000_at},
            'aggression': {'firstMilitaryInEnemyHalf': first_enemy_half.get(idx), 'enemyHalfSeconds': sum(enemy_half_sec[idx]), 'enemyHalfShare': round(sum(enemy_half_sec[idx][pvp_sec0:]) / pvp_seconds, 3), 'weightedDamageDealtPerMinute': round(w_dealt, 1)},
            'map': {'cellSecondsPerMinute': round(cell_seconds / pvp_minutes, 1), 'defenseCellsMean': round(sum(defense_cells[idx][pvp_sec0:]) / pvp_seconds, 2), 'defenseCellsPeak': max(defense_cells[idx]), 'cellsVisited': len(visited), 'cellsVisitedShare': round(len(visited) / (GRID * GRID), 3), 'contestedCellSecondsPerMinute': round(contested / pvp_minutes, 1)},
            'growth': {'villagersAt': vill_at, 'populationAt': pop_at_marks, 'villagersTrained': len(vill_built), 'lastVillagerAt': round(last_vill, 1) if last_vill else None, 'villagerSeries': villager_series[idx],
                       'gathered': round(gathered), 'gatheredWeighted': round(gathered_w), 'gatherPerMinute': round(gather_pm, 1) if gather_pm is not None else None, 'weightedGatherPerMinute': round(gathered_w / minutes, 1), 'gatheredBy': gathered_by,
                       'ages': {k: round(v, 1) for k, v in ages.items()}, 'ecoTechs': {k: round(v, 1) for k, v in eco.items()},
                       'armyMilestones': milestone, 'weightedArmyValue': weighted_army, 'armySeries': army_series[idx], 'armyUnitsOnlyPeak': round(max(army_units_only[idx]) if army_units_only[idx] else 0),
                       'militaryTechSpend': round(sum(c for _, c, _ in tech_spend.get(idx, []))), 'militaryTechs': [{'t': round(t, 1), 'cost': round(c), 'name': n} for t, c, n in sorted(tech_spend.get(idx, []))][:80]},
            'efficiency': {'tcEmptyShare': round(tc_empty / tc_known, 3) if tc_known else None, 'tcEmptySeconds': round(tc_empty, 1), 'tcKnownSeconds': round(tc_known, 1), 'peakVillagers': peak_vill, 'plateauSeconds': plateau_seconds, 'townCenters': tc_rows,
                           'idleVillagerShare': round(idle_seconds / vill_seconds, 3) if vill_seconds else None, 'idleVillagerSeconds': round(idle_seconds),
                           'meanBank': round(mean_bank) if mean_bank is not None else None, 'floatMinutes': round(mean_bank / gather_pm, 2) if mean_bank is not None and gather_pm else None, 'floatShare': float_share, 'queuedShare': queued_share,
                           'finalBank': round(final_bank) if final_bank is not None else None, 'unspentShare': round(final_bank / gathered, 3) if final_bank is not None and gathered else None,
                           'popCappedShare': pop_capped_share, 'popCappedSeconds': round(capped_time), 'meanPopHeadroom': mean_headroom, 'productionIdleShare': round(prod_idle / prod_known, 3) if prod_known > 120 else None, 'productionIdleSeconds': round(prod_idle), 'queuedResourcesMean': round(locked_area / duration) if duration and prod_known > 120 else None, 'productionIdleAffordableShare': round(prod_idle_aff / prod_known, 3) if prod_known > 120 else None, 'productionIdleAffordableSeconds': round(prod_idle_aff), 'productionKnownSeconds': round(prod_known)},
            'pressure': {'episodes': len(episodes), 'pressureReceived': round(pressure_total), 'growthLost': round(growth_lost_total), 'growthLostPer1000Pressure': round(growth_lost_total / pressure_total * 1000 / max(1.0, attackers_mean or 1.0), 1) if pressure_total >= 2000 else None, 'pressureMultiplier': round(max(1.0, attackers_mean or 1.0), 2),
                         'villagersLostUnderPressure': vill_lost_pressure, 'villagersLostPer1000Pressure': round(vill_lost_pressure / pressure_total * 1000 / max(1.0, attackers_mean or 1.0), 2) if pressure_total >= 2000 else None,
                         'incomeKeptUnderPressure': round(min(1.0, episode_income_total / expected_income_total), 3) if expected_income_total >= 500 else None,
                         'attackersAtOnceMean': attackers_mean, 'attackersAtOnceMax': attackers_max, 'peakAttackersPerMinute': peak_attackers_minute, 'minutesAttackedBy2': attacked_by[2], 'minutesAttackedBy3': attacked_by[3], 'minutesAttackedBy4': attacked_by[4], 'side': side_label.get(idx), 'weightedDamageTakenPerMinute': round(w_taken, 1), 'offSideDamageTakenPerMinute': round(w_off_side, 1) if w_off_side is not None else None, 'targetsAtOnceMean': targets_mean, 'targetsAtOnceMax': targets_max, 'episodeList': episode_rows[:120]},
            'harassment': {'enemyVillagersKilled': len(vill_kills), 'villagerKillValueWeighted': round(vk_weighted), 'villagerKillValuePer10': round(vk_weighted / (max(duration - PVP_FROM, 60.0) / 600)) if duration else None, 'firstVillagerKill': vill_kills[0]['t'] if vill_kills else None,
                           'villagerKillsBefore10': sum(1 for v in vill_kills if v['t'] <= 600), 'villagerKillsBefore15': sum(1 for v in vill_kills if v['t'] <= 900),
                           'raids': len(raids), 'killsPerRaid': round(len(vill_kills) / len(raids), 2) if raids else None, 'assistedVillagerKills': sum(1 for v in vill_kills if v['assists']), 'ownVillagersLost': len(own_vill_lost), 'villagerKills': vill_kills[:200], 'raidList': raids},
            'timing': {'ages': {k: round(v, 1) for k, v in ages.items()}, 'wheelbarrow': eco.get('wheelbarrow'), 'firstAttackAdvantage': first_attack_adv, 'firstAttackOwnArmy': round(army_value_at(idx, first_dealt[0])) if first_dealt else None, 'firstAttackEnemyArmy': round(army_value_at(first_dealt[4], first_dealt[0])) if first_dealt else None,
                       'armyStrongPhase': strong_phase, 'armyPeakValue': round(peak), 'armySeries': army_series[idx]},
            'multitasking': {'meanConcurrentFronts': mean_fronts, 'fightsMicroed': microed if cmds_mine else None, 'fightsMicroedShare': round(microed / len(my_fights), 3) if cmds_mine and len(my_fights) >= 3 else None,
                             'simultaneousFrontWindows': multi_front, 'multiFrontSeconds': round(multi_time), 'allFrontsMicroedShare': round(all_microed_time / multi_time, 3) if cmds_mine and multi_time >= 30 else None,
                             'tcEmptyShareInCombat': round(tc_c_empty / tc_c_known, 3) if tc_c_known > 30 else None, 'idleVillagerShareInCombat': round(idle_in_combat / vill_sec_in_combat, 3) if vill_sec_in_combat > 60 else None, 'productionIdleShareInCombat': round(prod_idle_c / prod_known_c, 3) if prod_known_c > 60 else None, 'combatEfficiency': combat_efficiency, 'villagersPerMinuteInCombat': round(vill_in_combat / (combat_total / 60), 2) if combat_total > 60 else None, 'villagersPerMinuteQuiet': round((len(vill_built) - vill_in_combat) / (quiet_total / 60), 2) if quiet_total > 60 else None},
            'reaction': {'threats': len(threats), 'economyThreats': sum(1 for t in threats if t['kind'] == 'economy'), 'responded': len(latencies), 'responseRate': round(len(latencies) / len(threats), 3) if threats and cmds_mine else None, 'answeredPerMinute': answered_share_per_minute, 'answeredCountPerMinute': round(len(latencies) / pvp_minutes, 3) if cmds_mine and duration else None, 'threatsByAttacker': {str(k): v for k, v in by_attacker.items()},
                         'medianLatency': round(statistics.median(latencies), 2) if latencies else None, 'p90Latency': round(sorted(latencies)[int(0.9 * (len(latencies) - 1))], 2) if latencies else None, 'threatList': responses[:150] if cmds_mine else threats[:150], 'commandStream': bool(cmds_mine)},
            'fightList': my_fights,
            'kills': kill_rows[:300],
        }
        if summary:
            sp = next((s for s in summary.get('players', []) if s.get('name') == p['name']), None)
            if sp:
                m['summary'] = {'result': sp.get('result'), 'apm': sp.get('apm'), 'scores': sp.get('scores'), 'profileId': sp.get('profile_id')}
                if m['profileId'] is None and str(sp.get('profile_id', '')).isdigit():
                    m['profileId'] = int(sp['profile_id']); m['tracked'] = m['profileId'] in tracked
        results.append(m)
    return {'gameId': gid, 'map': rep.map.layout if rep.map else None, 'durationSeconds': round(duration, 1), 'players': results, 'fights': len(fights), 'kills': len(kills),
            'recorderErrors': len(log.errors), 'commandStream': bool(commands), 'summary': bool(summary), 'teams': {str(k): v for k, v in teams.items()}}


# Radar axes: (metric path, higher is better) — percentile rank within the pool of all player-matches.
AXES = {
    'Fighting efficiency': [('combat.tradeRatio', True, 2), ('combat.netValueTraded', True, 1), ('combat.damagePerResource', True, 1), ('combat.fightsWonPersonalShare', True, 1)],
    'Aggression': [('combat.valueKilledShare', True, 2), ('combat.teamDamageShare', True, 1), ('combat.damage1000At', False, 1), ('aggression.enemyHalfShare', True, 1), ('aggression.weightedDamageDealtPerMinute', True, 1)],
    'Map control': [('map.cellsVisitedShare', True, 2), ('map.defenseCellsMean', True, 1), ('map.contestedCellSecondsPerMinute', True, 1)],
    'Growth': [('growth.populationAt.900', True, 1), ('growth.gatheredBy.900', True, 2), ('growth.weightedGatherPerMinute', True, 1), ('growth.ages.feudal', False, 1), ('growth.ages.castle', False, 1), ('growth.weightedArmyValue', True, 2)],
    'Efficiency': [('efficiency.floatShare', False, 2), ('efficiency.tcEmptyShare', False, 1), ('efficiency.idleVillagerShare', False, 1), ('efficiency.queuedShare', False, 1)],
    'Harassment': [('harassment.villagerKillValuePer10', True, 2), ('harassment.firstVillagerKill', False, 1), ('harassment.killsPerRaid', True, 1)],
    'Pressure handling': [('pressure.growthLostPer1000Pressure', False, 2), ('pressure.incomeKeptUnderPressure', True, 1), ('pressure.villagersLostPer1000Pressure', False, 1), ('pressure.targetsAtOnceMean', True, 1), ('pressure.offSideDamageTakenPerMinute', True, 1), ('pressure.weightedDamageTakenPerMinute', True, 1)],
    'Multitasking': [('multitasking.meanConcurrentFronts', True, 2), ('multitasking.fightsMicroedShare', True, 1), ('multitasking.allFrontsMicroedShare', True, 1), ('multitasking.combatEfficiency', True, 1)],
    'Reaction': [('reaction.answeredPerMinute', True, 2), ('reaction.responseRate', True, 1), ('reaction.medianLatency', False, 1)],
}
RANK_SCALE = {'harassment.villagerKillValuePer10': {'conqueror_1': 2.0, 'conqueror_2': 2.0, 'conqueror_3': 2.5}, 'combat.valueKilledShare': {'conqueror_1': 1.5, 'conqueror_2': 1.5, 'conqueror_3': 1.5}}


def rank_from_rating(rating):
    if not isinstance(rating, (int, float)):
        return None
    return 'conqueror_3' if rating >= 1700 else 'conqueror_1' if rating >= 1400 else 'below'


def set_path(m, path, value):
    cur = m
    parts = path.split('.')
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


def apply_rank_scale(m, level):
    for path, table in RANK_SCALE.items():
        factor = table.get(level or '', 1.0)
        v = get_path(m, path)
        if v is not None and factor != 1.0:
            set_path(m, path, round(v * factor, 2))


def derive(m):
    c = m['combat']
    c['fightsWonPersonalShare'] = round(c['fightsWonPersonal'] / c['fightsWithStake'], 3) if c['fightsWithStake'] >= 3 else None


def get_path(m, path):
    cur = m
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, (int, float)) and not isinstance(cur, bool) else None


def percentile_rank(values, v, higher):
    if v is None or not values:
        return None
    below = sum(1 for x in values if (x < v if higher else x > v))
    equal = sum(1 for x in values if x == v)
    return round(100 * (below + 0.5 * equal) / len(values), 1)


def fill_results(match, entry):
    """A player's result comes from the game summary; when the summary is missing (aoe4world refuses the summary page to
    scripts for some games, 255400269 among them) the manifest's aoe4world game record carries the same win/loss per
    profile (Sam, 2026-10-28: "this game is a loss, somehow that is not captured")."""
    results = {p['player'].get('profile_id'): p['player'].get('result') for team in entry['game'].get('teams', []) for p in team if isinstance(p.get('player'), dict)}
    for m in match['players']:
        if (m.get('summary') or {}).get('result') is None and results.get(m.get('profileId')) in ('win', 'loss'):
            m['summary'] = dict(m.get('summary') or {}, result=results[m['profileId']], resultSource='aoe4world game record')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only', type=int, nargs='*')
    ap.add_argument('--recorder', type=Path, default=DEFAULT_RECORDER)
    ap.add_argument('--reuse', action='store_true', help='recompute pools and profiles from the saved per-match results instead of re-analysing recordings')
    ap.add_argument('--min-pool-games', type=int, default=1, help='games a player needs to enter the percentile pool')
    args = ap.parse_args()
    recorder = args.recorder.resolve()
    manifest = json.loads((DATA / 'latest10-manifest.json').read_text(encoding='utf-8'))
    tracked = {int(k) for k in manifest['players']}
    status_path = DATA / 'recording-status.json'
    recorded = json.loads(status_path.read_text(encoding='utf-8'))['matches'] if status_path.exists() else {}
    matches = []
    saved = json.loads((DATA / 'skill-analysis.json').read_text(encoding='utf-8'))['matches'] if args.reuse and (DATA / 'skill-analysis.json').exists() else []
    for entry in manifest['unique_games']:
        gid = entry['game']['game_id']
        if args.only and gid not in args.only:
            continue
        if args.reuse:
            found = next((m for m in saved if m['gameId'] == gid), None)
            if found:
                for m in found['players']:
                    m.pop('radar', None)
                fill_results(found, entry)
                matches.append(found)
            continue
        if not (recorder / 'recordings' / f'aoe4_{gid}.rlog').exists() or not (DATA / f'replay-{gid}.rec').exists():
            continue
        if recorded and recorded.get(str(gid), {}).get('status') != 'complete':
            print('Skipping', gid, 'recording not complete', flush=True)
            continue
        print('Analyzing', gid, flush=True)
        match = analyze_match(gid, recorder, tracked)
        fill_results(match, entry)
        levels = {p['player']['profile_id']: (p['player'].get('rank_level') or rank_from_rating(p['player'].get('rating'))) for team in entry['game'].get('teams', []) for p in team if isinstance(p.get('player'), dict)}
        for m in match['players']:
            derive(m)
            m['rankLevel'] = levels.get(m.get('profileId'))
            apply_rank_scale(m, m['rankLevel'])
        matches.append(match)
    pool = [m for match in matches for m in match['players']]
    pool_values = {path: [v for v in (get_path(m, path) for m in pool) if v is not None] for axis in AXES.values() for path, _, _ in axis}
    # Strongest phase: the player's army value ranked against every pool player at the same game minute, then the
    # five-minute window with the highest mean percentile (only minutes the match reached).
    by_minute = defaultdict(list)
    for m in pool:
        for t, v in m['growth']['armySeries']:
            if t % 60 == 0:
                by_minute[t].append(v)
    for m in pool:
        pct = [[t, percentile_rank(by_minute[t], v, True)] for t, v in m['growth']['armySeries'] if t % 60 == 0 and len(by_minute[t]) >= 8]
        m['growth']['armyPercentileByMinute'] = pct
        best = None
        for i in range(len(pct)):
            window = pct[i:i + 5]
            if len(window) < 3:
                break
            mean = sum(p for _, p in window) / len(window)
            if best is None or mean > best['percentile']:
                best = {'from': window[0][0], 'to': window[-1][0] + 60, 'percentile': round(mean, 1)}
        m['growth']['strongestPhase'] = best
    for match in matches:
        for m in match['players']:
            radar = {}
            for axis, comps in AXES.items():
                parts = {}
                for path, higher, wgt in comps:
                    pr = percentile_rank(pool_values[path], get_path(m, path), higher)
                    if pr is not None:
                        parts[path] = {'value': get_path(m, path), 'percentile': pr, 'n': len(pool_values[path]), 'weight': wgt}
                radar[axis] = {'score': round(sum(x['percentile'] * x['weight'] for x in parts.values()) / sum(x['weight'] for x in parts.values()), 1) if parts else None, 'components': parts}
            m['radar'] = radar
    # Per-player pool: every player's mean raw value over their recorded games, ranked against every other player
    # (Sam: percentiles per player, not per game). Profile radars use these; game pages keep per-game ranks.
    by_player = defaultdict(list)
    for match in matches:
        if (match.get('durationSeconds') or 0) < MIN_GAME_SECONDS:  # games under 10:00 enter neither the pool nor a profile (Sam, 2026-10-28)
            continue
        for m in match['players']:
            if m.get('profileId') is not None:
                by_player[m['profileId']].append(m)
    paths = [p for axis in AXES.values() for p, _, _ in axis]

    def mean_of(rows, path):
        vals = [v for v in (get_path(m, path) for m in rows) if v is not None]
        return sum(vals) / len(vals) if vals else None

    MIN_POOL_GAMES = args.min_pool_games  # games a player needs to enter the percentile pool
    player_means = {pid: {path: mean_of(rows, path) for path in paths} for pid, rows in by_player.items() if len(rows) >= MIN_POOL_GAMES}
    player_pool = {path: [pm[path] for pm in player_means.values() if pm[path] is not None] for path in paths}

    def player_radar(rows):
        means = {path: mean_of(rows, path) for path in paths}
        radar = {}
        for axis, comps in AXES.items():
            parts = {}
            for path, higher, wgt in comps:
                pr = percentile_rank(player_pool[path], means[path], higher)
                if pr is not None:
                    parts[path] = {'value': round(means[path], 3), 'percentile': pr, 'n': len(player_pool[path]), 'weight': wgt, 'games': sum(1 for m in rows if get_path(m, path) is not None)}
            radar[axis] = {'score': round(sum(x['percentile'] * x['weight'] for x in parts.values()) / sum(x['weight'] for x in parts.values()), 1) if parts else None, 'games': len(rows), 'components': parts}
        return radar

    players_out = {}
    for pid_s, requested in manifest['players'].items():
        pid = int(pid_s)
        rows = [(match['gameId'], m) for match in matches for m in match['players'] if m.get('profileId') == pid]
        axes = player_radar([m for _, m in rows]) if rows else {axis: {'score': None, 'games': 0, 'components': {}} for axis in AXES}
        analyzed = [g for g, _ in rows]
        by_civ = {}
        for civ in sorted({m['civ'] for _, m in rows}):
            civ_rows = [m for _, m in rows if m['civ'] == civ]
            by_civ[civ] = {'games': len(civ_rows), 'radar': player_radar(civ_rows)}
        phases = [m['growth']['strongestPhase'] for _, m in rows if m['growth'].get('strongestPhase')]
        # Strongest phase across the player's games: the minute window with the highest mean army percentile
        minute_pct = defaultdict(list)
        for _, m in rows:
            for t, p in m['growth'].get('armyPercentileByMinute', []):
                minute_pct[t].append(p)
        curve = [[t, round(sum(v) / len(v), 1), len(v)] for t, v in sorted(minute_pct.items()) if len(v) >= max(2, len(rows) // 3)]
        strongest = None
        for i in range(len(curve)):
            window = curve[i:i + 5]
            if len(window) < 3:
                break
            mean = sum(p for _, p, _ in window) / len(window)
            if strongest is None or mean > strongest['percentile']:
                strongest = {'from': window[0][0], 'to': window[-1][0] + 60, 'percentile': round(mean, 1), 'games': min(n for _, _, n in window)}
        players_out[pid_s] = {'profileId': pid, 'name': rows[0][1]['name'] if rows else pid_s, 'requestedGames': requested, 'analyzedGames': analyzed, 'missingGames': [g for g in requested if g not in set(analyzed)],
                              'radar': axes, 'byCiv': by_civ, 'armyPercentileCurve': curve, 'strongestPhase': strongest,
                              'matches': [{'gameId': g, 'map': next(mm['map'] for mm in matches if mm['gameId'] == g), 'civ': m['civ'], 'result': (m.get('summary') or {}).get('result'), 'durationSeconds': m['durationSeconds'], 'radar': {a: m['radar'][a]['score'] for a in AXES}, 'strongestPhase': m['growth'].get('strongestPhase')} for g, m in rows]}
    out = {'schemaVersion': 2, 'generatedAt': datetime.now(timezone.utc).isoformat(), 'definitions': __doc__, 'axes': {a: [p for p, _, _ in c] for a, c in AXES.items()}, 'primary': {a: [p for p, _, w in c if w > 1] for a, c in AXES.items()}, 'poolSize': len(pool), 'playerPoolSize': len(player_means),
           'normalization': 'profiles: each component is the player mean over their recorded games, ranked against every other player mean in the dataset (n = players); game pages: each game ranked within all player-matches; axis = weighted mean of component percentiles (primary components double); raw values and n beside every percentile',
           'players': players_out, 'matches': matches}
    (DATA / 'skill-analysis.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print('matches', len(matches), 'pool', len(pool))
    for pid_s, p in players_out.items():
        print(p['name'], {a: v['score'] for a, v in p['radar'].items()}, 'games', len(p['analyzedGames']))


if __name__ == '__main__':
    main()
