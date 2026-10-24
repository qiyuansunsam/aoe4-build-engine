"""Reference builds retain source completions and use the installed multi-civ catalog."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
class ReferenceBuildTests(unittest.TestCase):
 def test_four_sources_and_full_completion_coverage(self):
  builds=read(ROOT/'data/build-library.json')['builds'];library=read(ROOT/'data/game-library.json');catalog=read(ROOT/'data/game-catalog.json')
  records={str(r['source']['pbgid']):r for kind in ('units','buildings','technologies') for r in catalog[kind]}
  self.assertEqual({b['civilization'] for b in builds},{'french','mongols','malians','japanese'})
  for build in builds:
   with self.subTest(build=build['id']):
    game=next(g for g in library['games'] if g.get('buildId')==build['id'])
    raw=read(Path(game['source']['localFile']));player=next(p for p in raw['players'] if p['profileId']==game['profileId'])
    self.assertEqual(build['sourceGameId'],game['id']);self.assertEqual(len(build['steps']),len(game['events']))
    self.assertFalse(build['validation']['engineSupported']);self.assertEqual(game['totalResourcesGathered'],player['totalResourcesGathered']);self.assertEqual(game['totalResourcesSpent'],player['totalResourcesSpent'])
    for row in player['buildOrder']:
     if row['type'] not in ('Unit','Building','Upgrade'):continue
     saved=next(r for r in game['completionRows'] if r['pbgid']==row['pbgid'])
     for key in ('finished','constructed','destroyed','transformed'):self.assertEqual(saved[key],row[key])
     times=row['constructed'] if row['type']=='Building' and row['constructed'] else row['finished']
     events=[e for e in game['events'] if e.get('pbgid')==row['pbgid']]
     self.assertEqual(sum(e.get('count',1) for e in events),len(times))
     self.assertEqual([e['t'] for e in events],sorted(set(times)))
     if row['type']=='Unit' and row['pbgid']!=2138188:self.assertIn(str(row['pbgid']),records)
    self.assertEqual([s['t'] for s in game['snapshots']],player['resources']['timestamps'])
    self.assertTrue(all(s['resourcesGathered'] is None for s in game['snapshots']))
    self.assertTrue(all(u['pbgid']!=2138188 for s in game['snapshots'] for u in s['unitCounts']))
  self.assertGreater(len(library['matches']),5800)
  self.assertGreater(len([g for g in library['games'] if not g.get('buildId')]),800)
 def test_non_abbasid_catalog_has_real_stats(self):
  units=read(ROOT/'data/game-catalog.json')['units']
  for civ in ('french','mongol','malian','japanese'):
   rows=[u for u in units if u['civilization']==civ]
   self.assertGreater(len(rows),40);self.assertTrue(all(u['source']['pbgid'] and u['source']['sha256'] for u in rows))
   self.assertTrue(any(u['hp']>0 and u['weapon'] and u['cost'] for u in rows))
if __name__=='__main__':unittest.main()
