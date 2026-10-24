import json,tempfile,threading,unittest
from pathlib import Path
from player_search import PlayerSearch
from timeline_download import TimelineError

class PlayerSearchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'data').mkdir()
  self.old={'id':'online-100','gameId':100,'sourceType':'online','perspectiveIds':['saved'],'timelineDownloadedAt':'today','players':[{'profileId':10,'perspectiveId':'saved'}]}
  (self.root/'data/game-library.json').write_text(json.dumps({'matches':[self.old],'games':[{'id':'saved'}]}),encoding='utf-8')
  self.calls=[];self.payload={}
  def fetch(url):self.calls.append(url);return self.payload
  self.api=PlayerSearch(self.root,threading.Lock(),fetch)
 def tearDown(self):self.tmp.cleanup()
 def test_search_exact_name_first_and_cache(self):
  self.payload={'players':[{'profile_id':2,'name':'A epsilon'},{'profile_id':10,'name':'epsilon','country':'cn','leaderboards':{'rm_team':{'rating':1381,'rank_level':'diamond_3'}}}]}
  first=self.api.search('epsilon');self.assertEqual(first['players'][0]['profileId'],10);self.assertEqual(first['players'][0]['rankLevel'],'diamond_3');self.api.search('epsilon');self.assertEqual(len(self.calls),1)
 def test_exact_profile_id(self):
  self.payload={'profile_id':10,'name':'epsilon'};self.assertEqual(self.api.search('10')['players'][0]['profileId'],10);self.assertTrue(self.calls[0].endswith('/players/10'))
 def test_validation(self):
  for q in ('','ab','x'*101):
   with self.assertRaises(TimelineError):self.api.search(q)
  with self.assertRaises(TimelineError):self.api.games(10,0)
  self.assertFalse(self.calls)
 def test_games_preserves_downloads_and_paginates(self):
  self.payload={'games':[{'game_id':100,'kind':'rm_2v2','patch':11308,'map':'Cliffside','teams':[[{'player':{'profile_id':10,'name':'epsilon','civilization':'abbasid_dynasty','rating':1200}}]]},{'game_id':101,'teams':[]}],'next_page':2}
  result=self.api.games(10);self.assertTrue(result['hasMore']);self.assertEqual(result['matches'][0]['perspectiveIds'],['saved']);self.assertEqual(result['matches'][0]['players'][0]['perspectiveId'],'saved');self.assertEqual(result['matches'][0]['players'][0]['civilization'],'abbasid')
  self.assertEqual(result['matches'][0]['timelineDownloadedAt'],'today');self.assertIn('include_alts=false',self.calls[0]);self.api.games(10);self.assertEqual(len(self.calls),1)
  data=json.loads((self.root/'data/game-library.json').read_text());self.assertEqual(len(data['matches']),2);self.assertEqual(data['games'],[{'id':'saved'}])
 def test_invalid_response_and_provider_error(self):
  self.payload={'error':'bad'}
  with self.assertRaises(TimelineError):self.api.games(10)
  def fail(url):raise TimelineError('provider_error','Unavailable',502)
  self.api.transport=fail
  with self.assertRaises(TimelineError):self.api.search('epsilon')

if __name__=='__main__':unittest.main()
