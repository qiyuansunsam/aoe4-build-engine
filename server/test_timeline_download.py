import copy,json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from app import make_handler
from timeline_download import TimelineDownloader,TimelineError

class DownloadTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'data').mkdir();(self.root/'site/dist').mkdir(parents=True)
  self.match={'id':'online-100','gameId':100,'sourceType':'online','map':'Test map','duration':120,'mode':'rm_1v1','patch':'11308','players':[{'profileId':10,'name':'Test A','civilization':'abbasid'},{'profileId':20,'name':'Test B','civilization':'french'}],'perspectiveIds':[]}
  self.summary={'gameId':100,'duration':120,'players':[{'profileId':pid,'name':f'Test {pid}','civilization':civ,'buildOrder':[{'type':'Unit','pbgid':1,'finished':[0,20,40],'destroyed':[90]}],'resources':{'timestamps':[0,30,60,120],'food':[200,190,180,170],'foodPerMin':[50,60,70,80]},'actions':{'feudalAge':[100]}} for pid,civ in [(10,'abbasid_dynasty'),(20,'french')]]}
  (self.root/'data/game-library.json').write_text(json.dumps({'matches':[self.match],'games':[]}),encoding='utf-8');(self.root/'data/game-catalog.json').write_text(json.dumps({'units':[{'name':'Villager','source':{'pbgid':1}}]}),encoding='utf-8')
  self.urls=[]
  def transport(url):self.urls.append(url);return copy.deepcopy(self.summary)
  self.downloader=TimelineDownloader(self.root,transport)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(None,self.root,self.downloader));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def post(self,body):
  req=Request(f'http://127.0.0.1:{self.server.server_port}/api/games/download',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
  try:
   with urlopen(req) as r:return r.status,json.load(r)
  except HTTPError as e:return e.code,json.load(e)
 def get_summary(self,match='online-100'):
  try:
   with urlopen(f'http://127.0.0.1:{self.server.server_port}/api/games/{match}/summary') as r:return r.status,json.load(r)
  except HTTPError as e:return e.code,json.load(e)
 def test_summary_missing_and_unknown_do_not_download(self):
  self.assertEqual(self.get_summary()[1]['error'],'summary_not_downloaded')
  self.assertEqual(self.get_summary('unknown')[0],404);self.assertFalse(self.urls)
 def test_public_summary_cached_statistics_and_no_internal_data(self):
  self.summary['_recentGameHash']='private';self.summary['winReason']='elimination';self.summary['players'][0].update(apm=160,scores={'total':900},_stats={'secret':1},totalResourcesGathered={'food':500},totalResourcesSpent={'wood':400})
  self.post({'matchId':'online-100'})
  status,data=self.get_summary();self.assertEqual(status,200);self.assertEqual(data['players'][0]['apm'],160);self.assertEqual(data['players'][0]['scores']['total'],900)
  self.assertEqual(data['players'][0]['resources']['food'],[200,190,180,170]);self.assertEqual(data['winReason'],'elimination')
  self.assertNotIn('_stats',data['players'][0]);self.assertNotIn('_recentGameHash',data);self.assertNotIn('localFile',json.dumps(data));self.assertEqual(len(self.urls),1)
 def test_legacy_summary_source_and_mismatched_game(self):
  legacy=self.root/'legacy.json';legacy.write_text(json.dumps(self.summary),encoding='utf-8')
  library=json.loads((self.root/'data/game-library.json').read_text());library['matches'][0]['perspectiveIds']=['old'];library['games']=[{'id':'old','gameId':100,'source':{'localFile':str(legacy)}}]
  (self.root/'data/game-library.json').write_text(json.dumps(library),encoding='utf-8')
  self.assertEqual(self.get_summary()[0],200);self.assertFalse(self.urls)
  wrong={**self.summary,'gameId':101};legacy.write_text(json.dumps(wrong),encoding='utf-8');self.assertEqual(self.get_summary()[1]['error'],'invalid_summary')
 def test_cached_perspective_without_raw_recovers_summary(self):
  self.post({'matchId':'online-100'});(self.root/'data/downloaded-summaries/100.json').unlink();self.downloader.cooldown=0
  status,result=self.post({'matchId':'online-100'});self.assertEqual(status,200);self.assertFalse(result['cached']);self.assertEqual(len(self.urls),2);self.assertEqual(self.get_summary()[0],200)
 def test_download_persist_cache(self):
  code,result=self.post({'matchId':'online-100','profileId':10});self.assertEqual(code,200);self.assertEqual(len(result['perspectives']),2);self.assertFalse(result['cached']);self.assertEqual(self.urls,['https://aoe4world.com/players/10/games/100/summary?camelize=true'])
  file=self.root/'data/game-perspectives/aoe4world-100-10.json';d=json.loads(file.read_text(encoding='utf-8'));self.assertEqual([m['t'] for m in d['snapshots']],[0,60,120]);self.assertEqual(d['snapshots'][1]['stock']['food'],180);self.assertIsNone(d['snapshots'][1]['spent']);self.assertNotIn('split',d['snapshots'][1]);self.assertEqual(d['completionRows'][0]['finished'],[0,20,40]);self.assertTrue((self.root/'site/dist/game-perspectives/aoe4world-100-10.json').exists());self.assertTrue((self.root/'data/downloaded-summaries/100.json').exists());self.assertTrue(self.post({'matchId':'online-100','profileId':20})[1]['cached']);self.assertEqual(len(self.urls),1)
 def test_reject_unknown_and_arbitrary_urls(self):
  for body,status in [({'matchId':'online-999'},404),({'matchId':'online-100','profileId':999},400),({'matchId':'online-100','url':'http://localhost'},400),({'matchId':'online-100','profileId':True},400)]:self.assertEqual(self.post(body)[0],status)
  self.assertFalse(self.urls)
 def test_wrong_match_does_not_mutate(self):
  before=(self.root/'data/game-library.json').read_bytes();self.summary['gameId']=999;self.assertEqual(self.post({'matchId':'online-100'})[0],502);self.assertEqual((self.root/'data/game-library.json').read_bytes(),before);self.assertFalse((self.root/'data/downloaded-summaries').exists())
 def test_provider_error_retains_collection(self):
  def fail(url):raise TimelineError('timeline_unavailable','Unavailable',404)
  self.downloader.transport=fail;self.assertEqual(self.post({'matchId':'online-100'})[0],404);self.assertEqual(json.loads((self.root/'data/game-library.json').read_text())['games'],[])
 def test_concurrent_duplicate_is_downloaded_once(self):
  results=[];threads=[threading.Thread(target=lambda:results.append(self.post({'matchId':'online-100','profileId':10}))) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual([x[0] for x in results],[200,200]);self.assertEqual(len(self.urls),1);self.assertEqual(sorted(x[1]['cached'] for x in results),[False,True])

if __name__=='__main__':unittest.main()
