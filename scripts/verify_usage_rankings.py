"""Independently reconcile tier metrics with official results and source game rows."""
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from export_unit_tiers import HISTORY, SOURCE, CATALOG
from build_winrates import BANDS,rating_in_band

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def close(left, right):
    assert math.isclose(left, right, rel_tol=1e-11, abs_tol=1e-12), (left, right)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=SOURCE);parser.add_argument('--history',type=Path,default=HISTORY);parser.add_argument('--tc-cache',type=Path,default=ROOT/'.cache/tc-milestones.json');args=parser.parse_args()
    data = read(ROOT / 'data/unit-usage-tiers.json')
    audit = read(ROOT / '.cache/usage-ranking-audit.json')
    history, source, catalog = read(args.history), read(args.source), read(CATALOG)
    tc_rows = read(args.tc_cache)['rows']
    keep_civs = {u['civilization'] for u in catalog['buildings'] if 'keep' in u['id'] and not u['id'].startswith(('building_landmark_', 'building_house_of_wisdom_', 'building_wonder_age')) and u['id'] != 'building_defense_fortress_tem'}
    game_ratings={m['id']:sum(p['oldrating'] for p in m['matchhistorymember'])/len(m['matchhistorymember']) for m in history['matchHistory']}
    official = {}
    for match in history['matchHistory']:
        reports = {r['profile_id']: r['resulttype'] for r in match['matchhistoryreportresults']}
        for member in match['matchhistorymember']:
            if member['outcome'] in (0, 1) and reports.get(member['profile_id']) == member['outcome']:
                official[(match['id'], member['profile_id'])] = member['outcome']
    source = {(g['gameId'], g['profileId']): g for g in source if g['durationSeconds'] >= 600 and (g['gameId'], g['profileId']) in official}
    assert len(source) == data['eligiblePlayerGames']
    records = {u['id']: u for kind in ('units', 'buildings', 'technologies') for u in catalog[kind]}
    pbg = defaultdict(list)
    for kind in ('units', 'buildings', 'technologies'):
        for u in catalog[kind]:
            pbg[u['source']['pbgid']].append((kind, u))
    # Recompute military production totals directly from normalized raw rows.
    production = {}
    for identity, game in source.items():
        total = 0
        for row in game['unitAppearances']:
            candidates = pbg[row['pbgid']]
            selected = next((v for v in candidates if v[1]['civilization'] == game['civilization']), None)
            if selected is None and len(candidates) == 1:
                selected = candidates[0]
            if selected is None:
                continue
            kind, unit = selected
            if kind == 'units' and 'military' in unit.get('classes', []) and not re.search(r'dummy|scout|villager|trade_cart|fishing_boat|transport|scholar|priest|monk|abbey_king', unit['id']):
                total += row['nonstartingAppearances']
        production[identity] = total
    indexed = {(r.get('rankBand','all'),r['category'], r['civilization'], r['matchTypeId'], r['id']): r for r in audit}
    assert len(indexed) == len(audit)
    count = 0
    all_unit_totals = defaultdict(int)
    for cohort in data['cohorts']:
        assert all('abbey_king' not in form for item in cohort['items'] for form in item.get('forms',[]))
        rates = [r['winRate'] for r in cohort['items']]
        assert rates == sorted(rates, reverse=True)
        band_def=next(b for b in BANDS if b['id']==cohort.get('rankBand','all'))
        candidates = [g for g in source.values() if (band_def['id']=='all' or rating_in_band(game_ratings[g['gameId']],band_def)) and g['matchTypeId'] == cohort['matchTypeId'] and (cohort['civilization'] == '__all__' or g['civilization'] == cohort['civilization'])]
        assert len(candidates) == cohort['knownOutcomePlayerGames']
        for item in cohort['items']:
            row = indexed[(cohort.get('rankBand','all'),cohort['category'], cohort['civilization'], cohort['matchTypeId'], item['id'])]
            appearances = row['contributions']
            identities = {(g['gameId'], g['profileId']) for g in appearances}
            assert len(identities) == len(appearances) == item['usedIn']
            assert all(g['win'] == official[(g['gameId'], g['profileId'])] for g in appearances)
            wins = sum(g['win'] == 1 for g in appearances)
            losses = sum(g['win'] == 0 for g in appearances)
            assert (wins, losses) == (item['wins'], item['losses'])
            close(item['rawWinRate'], wins / len(appearances))
            for g in appearances:
                identity = (g['gameId'], g['profileId'])
                assert g['civilization'] == source[identity]['civilization']
                if cohort['category'] == 'units':
                    assert g['total'] == production[identity]
                    close(g['share'], g['count'] / production[identity])
                    if cohort['civilization'] == '__all__' and cohort.get('rankBand','all')=='all':
                        all_unit_totals[identity] += g['count']
                else:
                    assert g['share'] == 1
            winning = sum(g['share'] for g in appearances if g['win'] == 1)
            losing = sum(g['share'] for g in appearances if g['win'] == 0)
            close(item['winWeight'], winning)
            close(item['lossWeight'], losing)
            close(item['winRate'], winning / (winning + losing))
            if cohort['category'] == 'units':
                close(item['averageShareWhenUsed'], (winning + losing) / len(appearances))
            else:
                assert item['averageShareWhenUsed'] is None
                close(item['winRate'], wins / len(appearances))
            assert 0 < item['eligiblePlayerGames'] <= len(candidates)
            if item['id'].startswith('generic-tc-'):
                milestone = int(item['id'].rsplit('-', 1)[1])
                assert milestone in (1, 2, 3)
                verified = [g for g in candidates if tc_rows.get(str(g['gameId']) + ':' + str(g['profileId']), {}).get('status') == 'verified-timeline']
                assert item['eligiblePlayerGames'] == len(verified)
                expected = {(g['gameId'], g['profileId']) for g in verified if tc_rows[str(g['gameId']) + ':' + str(g['profileId'])]['maximum'] >= milestone}
                assert identities == expected, (item['id'], len(identities), len(expected))
            elif cohort['civilization'] != '__all__':
                assert item['eligiblePlayerGames'] == len(candidates)
            elif item['id'] == 'generic-keep':
                relevant = keep_civs | {g['civilization'] for g in appearances}
                assert item['eligiblePlayerGames'] == sum(g['civilization'] in relevant for g in candidates)
            elif item['civilization'] not in ('generic', 'common'):
                relevant = {item['civilization']} | {g['civilization'] for g in appearances}
                assert item['eligiblePlayerGames'] == sum(g['civilization'] in relevant for g in candidates)
            elif item['name'] in ('Spearman', 'Battering Ram'):
                relevant = {u['civilization'] for u in catalog['units'] if re.sub(r'^(Elite|Veteran|Hardened|Early|Vanguard)\s+', '', u['name']) == item['name']} | {g['civilization'] for g in appearances}
                assert item['eligiblePlayerGames'] == sum(g['civilization'] in relevant for g in candidates)
            close(item['usageRate'], len(appearances) / item['eligiblePlayerGames'])
            assert 0 <= item['usageRate'] <= 1
            assert (item['tier'] == 'Unrated') == (len(appearances) < 30)
            if cohort['category'] == 'technologies':
                assert not any(form.startswith('upgrade_add_') for form in item['forms'])
            if item['id'].startswith('wing:'):
                assert cohort['category'] == 'buildings'
            if item['id'].startswith('generic-tc-') or item['id'] == 'generic-keep':
                assert item['civilization'] == 'generic'
            count += 1
        names = ('Spearman', 'Battering Ram') if cohort['category'] == 'units' else ('Keep', 'Town Center', 'Second Town Center', 'Third Town Center') if cohort['category'] == 'buildings' else ('Wheelbarrow', 'Bloomery', 'Double Broadax')
        for name in names:
            rows = [r for r in cohort['items'] if r['name'] == name]
            assert len(rows) <= 1, (cohort['category'], name, cohort['civilization'], cohort['matchTypeId'])
            assert all(r['civilization'] == 'generic' for r in rows)
    assert all(all_unit_totals[key] == value for key, value in production.items())
    print(json.dumps({'verifiedRows': count, 'sourceGames': data['sourceGames'], 'checks': 'official outcomes, raw military counts, winning and losing weights, average shares, civ denominators, generic units/buildings, wing classification, unique appearances'}))


if __name__ == '__main__':
    main()
