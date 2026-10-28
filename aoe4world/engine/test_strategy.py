import copy
import json
import unittest
import tempfile
import time
import urllib.parse
from pathlib import Path
from .strategy import ROOT, aggregate, extract, timing
from .collection import Collector, normalize_url, retry_delay, select_sample


class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary=json.loads((ROOT/'data/samples/254412239.json').read_text(encoding='utf-8-sig'))

    def test_real_building_events_and_patch(self):
        players=extract(self.summary)
        japanese=next(p for p in players if p['civilization']=='japanese')
        self.assertEqual(japanese['patch'],'11308')
        self.assertEqual(japanese['secondTC'],701)
        self.assertTrue(any(e['name']=='Barracks' and e['time']==384 for e in japanese['events']))
        self.assertEqual(japanese['landmark']['name'],'Kura Storehouse')
        self.assertEqual(japanese['ages']['feudal'],273)

    def test_game_dedup_and_distinct_vs_player_samples(self):
        result=aggregate([self.summary,copy.deepcopy(self.summary)])
        self.assertEqual(result['coverage']['matches'],1)
        self.assertEqual(result['coverage']['playerAppearances'],8)
        english=next(c for c in result['cohorts'] if c['civilization']=='english')
        self.assertEqual(english['samples'],1)
        self.assertEqual(english['playerSamples'],2)
        self.assertEqual(english['winRate'],50)

    def test_civilization_mode_patch_are_separate(self):
        other=copy.deepcopy(self.summary)
        other['gameId']=123
        other['patch']=999
        other['leaderboard']='rm_2v2'
        result=aggregate([self.summary,other])
        self.assertEqual(result['coverage']['matches'],2)
        self.assertTrue(any(c['mode']=='rm_2v2' and c['patch']=='999' for c in result['cohorts']))
        self.assertTrue(all(c['samples']==1 for c in result['cohorts']))

    def test_short_games_excluded_from_openings_not_army(self):
        short=copy.deepcopy(self.summary)
        short['duration']=500
        result=aggregate([short])
        self.assertTrue(all(not c['builds'] for c in result['cohorts']))
        self.assertTrue(any(c['army'] for c in result['cohorts']))

    def test_production_excludes_initial_and_unpacked_duplicates(self):
        rows=extract(self.summary)
        japanese=next(p for p in rows if p['civilization']=='japanese')
        self.assertFalse(any(u['name']=='Scout' for u in japanese['units']))
        expected=sum(len([t for t in u.get('finished',[]) if t>0]) for p in self.summary['players'] if p['civilization']=='japanese' for u in p['buildOrder'] if u.get('type')=='Unit' and '/ram' in u.get('icon',''))
        self.assertEqual(sum(u['produced'] for u in japanese['units'] if 'Ram' in u['name']),expected)

    def test_url_and_retry_policy(self):
        gid,url=normalize_url('https://aoe4world.com/players/7999822-Zamia/games/254412239?sig=abc')
        self.assertEqual(gid,254412239)
        self.assertIn('sig=abc',url)
        self.assertIn('camelize=true',url)
        with self.assertRaises(ValueError):
            normalize_url('https://evil.example/players/1/games/2')
        self.assertEqual(retry_delay('120',60),120)
        self.assertEqual(retry_delay(None,300),300)

    def test_two_sample_quartiles_bracket_median(self):
        result=timing([250,274])
        self.assertEqual(result,dict(median=262,p25=256,p75=268,samples=2))

    def test_fresh_sample_balances_modes_and_deduplicates(self):
        games=[dict(game_id=i*10+j,kind=mode,state='processed',ongoing=False,teams=[[{'player':{'civilization':'english' if j%2 else 'french','profile_id':j+1}}]]) for i,mode in enumerate(('rm_1v1','rm_2v2','rm_3v3','rm_4v4')) for j in range(10)]
        sample=select_sample(games+games)
        self.assertEqual(len(sample),20)
        self.assertEqual(len({g['game_id'] for g in sample}),20)
        self.assertTrue(all(sum(g['kind']==mode for g in sample)==5 for mode in ('rm_1v1','rm_2v2','rm_3v3','rm_4v4')))

    def test_feed_resumes_after_four_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            worker=Collector(folder);calls=[]
            def request(url,**kwargs):
                params=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                page=int(params['page'][0]);calls.append(params)
                return dict(games=[dict(game_id=1000+page,kind='rm_1v1',started_at='2026-10-04T00:00:00Z',updated_at='2026-10-04T08:00:00Z',ongoing=True)],next_page=page+1 if page<5 else None)
            worker.request=request
            worker.feed()
            self.assertEqual(len(calls),4)
            self.assertEqual(worker.state['feedCursor']['nextPage'],5)
            since=calls[0]['updated_since'][0]
            worker.db.close()
            worker=Collector(folder)
            worker.request=request
            worker.state['nextFeed']=0
            worker.feed()
            self.assertEqual(calls[-1]['page'],['5'])
            self.assertEqual(calls[-1]['updated_since'],[since])
            self.assertEqual(worker.state['feedCursor']['nextPage'],1)
            worker.db.close()

    def test_source_quotas_leave_fresh_capacity_and_status_deduplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            worker=Collector(folder)
            worker.state['summarySources']=[dict(at=time.time(),source='tracked history') for _ in range(4)]
            worker.enqueue('https://aoe4world.com/players/1/games/100','tracked history')
            worker.enqueue('https://aoe4world.com/players/1/games/101','recent feed sample')
            requested=[]
            def request(url,**kwargs):
                requested.append(kwargs['source']);payload=copy.deepcopy(self.summary);payload['gameId']=normalize_url(url)[0];return payload
            worker.request=request
            self.assertTrue(worker.summary())
            self.assertEqual(requested,['recent feed sample'])
            self.assertFalse(worker.summary())
            worker.state['summarySources']=[dict(at=time.time(),source='recent feed sample') for _ in range(20)]
            self.assertTrue(worker.summary())
            self.assertEqual(requested,['recent feed sample','tracked history'])
            # Importing the bundled match again counts its ID once.
            Path(folder,'summaries','254412239.json').write_text(json.dumps(self.summary),encoding='utf-8')
            self.assertEqual(worker.status()['downloaded'],3)
            worker.db.close()


if __name__=='__main__':
    unittest.main()
