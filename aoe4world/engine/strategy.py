"""Descriptive openings and army production from locally cached public summaries."""
import collections
import datetime as dt
import hashlib
import functools
import json
import math
import os
import time
import uuid
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'data/strategy'


@functools.lru_cache(maxsize=1)
def catalog():
    by_pbg={}; by_icon={}; manifest={}
    try:
        manifest=json.loads((ROOT/'public/assets/manifest.json').read_text(encoding='utf-8-sig'))
        entities=list(manifest.get('units',[]))
        for filename in ('buildings.json','technologies.json'):
            entities.extend(json.loads((ROOT/'data/catalog'/filename).read_text(encoding='utf-8-sig')).get('data',[]))
        for entity in entities:
            by_pbg[str(entity.get('pbgid'))]=entity
            icon=entity.get('icon','').rsplit('/',1)[-1].replace('.png','').replace('_','-')
            by_icon[icon]=entity
    except (OSError,ValueError):
        pass
    return by_pbg,by_icon,manifest


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        # Windows readers/antivirus can briefly hold a destination without delete
        # sharing. Keep the complete old JSON visible while retrying promotion.
        for attempt in range(12):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if os.name != 'nt' or attempt == 11:
                    raise
                time.sleep(min(0.05 * 2 ** attempt, 0.5))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def wilson(wins, n):
    if not n:
        return [0, 100]
    z = 1.95996398454
    p = wins / n
    center = (p + z*z/(2*n))/(1+z*z/n)
    width = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [round(100*(center-width), 2), round(100*(center+width), 2)]


def timing(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return dict(median=None, p25=None, p75=None, samples=0)
    def percentile(fraction):
        index=(len(values)-1)*fraction
        low=math.floor(index);high=math.ceil(index)
        return round(values[low]+(values[high]-values[low])*(index-low))
    return dict(median=round(statistics.median(values)), p25=percentile(.25), p75=percentile(.75), samples=len(values))


def pretty(icon):
    name = icon.rsplit('/', 1)[-1]
    name = re.sub(r'^(unit_|building_)', '', name)
    name = re.sub(r'_[1-4]$', '', name)
    return name.replace('_', ' ').replace('-', ' ').title()


def icon_url(icon):
    return icon if icon.startswith('https://') else 'https://data.aoe4world.com/' + icon + '.png'


def event_times(row):
    # Buildings use constructed in the actual provider schema. Never add
    # finished+constructed: a siege engine can have both lifecycle events.
    return row.get('constructed', []) or row.get('finished', []) if row.get('type') == 'Building' else row.get('finished', [])


def is_army(row):
    return row.get('type') == 'Unit' and not any(x in row.get('icon', '').lower() for x in ('villager', 'trader', 'fishing', 'transport', 'scholar', 'monk', 'prelate', 'imperial_official'))


def extract(summary):
    recent = summary.get('_recentGameHash') or summary.get('RecentGameHash') or summary.get('recentGameHash') or {}
    patch = summary.get('patch') or recent.get('patch') or 'unknown'
    if isinstance(patch, dict):
        patch = patch.get('app_version') or patch.get('appVersion') or 'unknown'
    game_id = summary['gameId']
    records = []
    for player in summary.get('players', []):
        if player.get('result') not in ('win', 'loss'):
            continue
        landmarks = {str(x['pbgid']): x for x in player.get('analysis', {}).get('landmarks', [])}
        events, units, military, tcs = [], [], [], []
        for row in player.get('buildOrder', []):
            rawicon = row.get('icon', '')
            key = str(row.get('pbgid', row.get('id', 'unknown')))
            mark = landmarks.get(key, {})
            by_pbg,by_icon,manifest=catalog()
            entity=by_pbg.get(key) or by_icon.get(rawicon.rsplit('/',1)[-1].replace('_','-'),{})
            source_icon=mark.get('icon') or entity.get('icon') or icon_url(rawicon)
            local_icon=manifest.get('pbgids',{}).get(key) or manifest.get('icons',{}).get(rawicon) or manifest.get('icons',{}).get(source_icon) or source_icon
            item = dict(id=key, pbgid=row.get('pbgid'), name=mark.get('name') or entity.get('name') or pretty(rawicon), icon=local_icon, type=row.get('type'))
            times = [t for t in event_times(row) if isinstance(t, (int, float)) and t > 0]
            if row.get('type') == 'Building':
                if any(x in rawicon for x in ('barracks', 'archery', 'stable')):
                    military.extend((t, item['name']) for t in times)
                if any(x in rawicon for x in ('town_center', 'town_centre')):
                    tcs.extend(times)
            if row.get('type') in ('Building', 'Unit', 'Upgrade'):
                # Icon lanes show first occurrences, with total opening count.
                opening = [t for t in times if t <= 720]
                if opening and not any(x in rawicon for x in ('villager', 'sheep', 'wheat_field')):
                    events.append(dict(item, time=min(opening), count=len(opening)))
            if is_army(row):
                finished = [t for t in row.get('finished', []) if t > 0]
                # Construction-only siege entries can be the unpacked form of an
                # already-finished unit. Count finished production once only.
                if finished:
                    units.append(dict(item, produced=len(finished), lost=len(row.get('destroyed', [])), earlyProduced=sum(t <= 720 for t in finished), first=min(finished)))
        actions = player.get('actions', {})
        age = {label: min([t for t in actions.get(key, []) if t > 0], default=None) for label, key in [('feudal', 'feudalAge'), ('castle', 'castleAge'), ('imperial', 'imperialAge')]}
        landmark = next((dict(name=m['name'], icon=m['icon'], pbgid=m['pbgid']) for m in landmarks.values() if m.get('newAge') == 2), None)
        first_military = min(military)[1] if military else None
        second_tc = min(tcs, default=None)
        opening_units = sorted([u for u in units if u['earlyProduced'] and 'Scout' not in u['name']], key=lambda u: (-u['earlyProduced'], u['id']))[:2]
        # These are explicit observed signatures, not learned strength clusters.
        build_key = '|'.join([str(landmark['pbgid']) if landmark else 'no-landmark', '2tc' if second_tc and second_tc <= 720 else '1tc', first_military or 'no-military-building'])
        label = ' · '.join(filter(None, [landmark['name'] if landmark else first_military or 'Recorded opening', '2 TC' if second_tc and second_tc <= 720 else None]))
        events.sort(key=lambda e: (e['time'], e['id']))
        records.append(dict(gameId=game_id, profileId=player['profileId'], name=player.get('name'), civilization=player['civilization'], mode=summary.get('leaderboard', 'unknown'), patch=str(patch), startedAt=summary.get('startedAt'), duration=summary.get('duration', 0), win=player['result']=='win', events=events, units=units, ages=age, landmark=landmark, secondTC=second_tc, openingUnits=opening_units, buildKey=build_key, label=label, url=f'https://aoe4world.com/players/{player["profileId"]}/games/{game_id}'))
    return records


def army(items):
    groups = collections.defaultdict(list)
    for item in items:
        for unit in item['units']:
            groups[unit['id']].append((item, unit))
    total = sum(u['produced'] for rows in groups.values() for _, u in rows)
    output = []
    for key, rows in groups.items():
        first = rows[0][1]
        n = len(rows)
        wins = sum(item['win'] for item, _ in rows)
        produced = sum(u['produced'] for _, u in rows)
        output.append(dict(id=key, pbgid=first['pbgid'], name=first['name'], icon=first['icon'], produced=produced, lost=sum(u['lost'] for _, u in rows), games=len({x['gameId'] for x, _ in rows}), playerSamples=n, wins=wins, winRate=round(100*wins/n, 2), interval=wilson(wins,n), share=round(100*produced/total,2) if total else 0, averageProduced=round(produced/n,1), earlyProduced=sum(u['earlyProduced'] for _, u in rows)))
    return sorted(output, key=lambda x: -x['produced'])


def aggregate(summaries):
    unique = {s['gameId']: s for s in summaries if s.get('gameId') and isinstance(s.get('players'), list)}
    records = [row for s in unique.values() for row in extract(s)]
    groups = collections.defaultdict(list)
    for row in records:
        groups[(row['civilization'], row['mode'], row['patch'])].append(row)
    cohorts = []
    for (civ, mode, patch), items in sorted(groups.items()):
        def stats(rows):
            n=len(rows); wins=sum(x['win'] for x in rows)
            return dict(games=len({x['gameId'] for x in rows}), playerSamples=n, wins=wins, winRate=round(100*wins/n,2), interval=wilson(wins,n))
        def ages(rows):
            return {k:timing([x['ages'][k] for x in rows]) for k in ('feudal','castle','imperial')}
        builds = []
        by_build = collections.defaultdict(list)
        for item in items:
            if item['duration'] >= 720:
                by_build[item['buildKey']].append(item)
        for key, members in by_build.items():
            median = statistics.median(x['ages']['feudal'] or 720 for x in members)
            representative = min(members, key=lambda x:abs((x['ages']['feudal'] or 720)-median))
            builds.append(dict(id=hashlib.sha1(f'{civ}|{mode}|{patch}|{key}'.encode()).hexdigest()[:12], label=representative['label'], **stats(members), status='observed' if len({x['gameId'] for x in members})>=30 else 'exploratory', representative={k:representative[k] for k in ('gameId','profileId','name','url','events','units')}, landmark=representative['landmark'], ageTimings=ages(members), secondTC=timing([x['secondTC'] for x in members]), units=army(members)))
        cohort_stats=stats(items)
        cohorts.append(dict(id=f'{civ}|{mode}|{patch}', civilization=civ, mode=mode, patch=patch, samples=cohort_stats['games'], **cohort_stats, builds=sorted(builds,key=lambda x:-x['playerSamples']), army=army(items), timings=ages(items)))
    dates=[x['startedAt'] for x in records if isinstance(x['startedAt'],(int,float))]
    return dict(schemaVersion=1, generatedAt=utcnow(), coverage=dict(matches=len(unique), playerAppearances=len(records), civilizations=len({x['civilization'] for x in records}), **{'from':dt.datetime.fromtimestamp(min(dates),dt.timezone.utc).isoformat() if dates else None, 'to':dt.datetime.fromtimestamp(max(dates),dt.timezone.utc).isoformat() if dates else None}, complete=False, source='Bounded public match sample + local imports'), methodology=dict(openingWindowSeconds=720,minimumObservedGames=30,rateUnit='percent',winRate='Unadjusted player appearances',interval='95% Wilson; repeated players and teammates are not independent',army='Observed produced units and recorded losses; not standing army or attributed kills',builds='Feudal landmark + additional TC by 12m + first military building; games under 12m excluded'), cohorts=cohorts)


def refresh(directory=DIRECTORY):
    catalog.cache_clear()
    summaries=[]
    for folder in (ROOT/'data/samples', Path(directory)/'summaries'):
        for path in folder.glob('*.json'):
            try:
                payload=json.loads(path.read_text(encoding='utf-8-sig'))
                summaries.append(payload.get('data',payload))
            except (ValueError,OSError):
                continue
    output=aggregate(summaries)
    write_json(Path(directory)/'aggregate.json',output)
    return output


if __name__ == '__main__':
    print(json.dumps(refresh()['coverage']))
