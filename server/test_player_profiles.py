import json,tempfile,unittest
from pathlib import Path
from player_profiles import build_snapshot, normalize_mode, normalize_profile, normalize_game, reference_players
from timeline_download import TimelineError

LIBRARY={'matches':[{'id':'online-500','gameId':500,'perspectiveIds':['aoe4world-500-10'],'players':[{'profileId':10},{'profileId':11}]},{'id':'online-501','gameId':501,'perspectiveIds':[],'players':[{'profileId':10}]}],
 'games':[{'id':'aoe4world-500-10','buildId':'french-observed-4v4','sourceType':'observed','profileId':10,'gameId':500,'matchId':'online-500','playerName':'epsilon','title':'French reference game','civilization':'french','map':'Dry Arabia','mode':'rm_4v4','result':'win','duration':2907},
  {'id':'aoe4world-600-12','sourceType':'observed','profileId':12,'gameId':600},
  {'id':'aoe4world-500-10b','buildId':'other','sourceType':'observed','profileId':10,'gameId':500}]}

PROFILE={'profile_id':10,'name':'epsilon','country':'cn','avatars':{'medium':'https://x/avatar.jpg'},'modes':{
 'rm_team':{'rating':1403,'max_rating':1466,'rank':3474,'rank_level':'conqueror_1','streak':1,'games_count':76,'wins_count':35,'losses_count':41,'win_rate':46.1,'season':14,
  'rating_history':{'1792906451':{'rating':1403,'streak':1,'wins_count':35,'games_count':76},'1791715817':{'rating':1432,'streak':-1,'wins_count':32,'games_count':66},'bad':{'rating':1}},
  'civilizations':[{'civilization':'abbasid_dynasty','win_rate':50.0,'pick_rate':42.5,'games_count':32},{'civilization':'malians','win_rate':40.0,'pick_rate':10.0,'games_count':8}],
  'previous_seasons':[{'season':12,'rating':1429,'rank':4309,'rank_level':'conqueror_1','games_count':60,'wins_count':30,'losses_count':30,'win_rate':50.0},{'season':13,'rating':1400,'games_count':10,'wins_count':5,'losses_count':5}]},
 'rm_solo':{'rank_level':'unranked','games_count':0,'wins_count':0,'season':14,'previous_seasons':[],'civilizations':[]},
 'rm_1v1_elo':{'rating':1605,'games_count':3,'wins_count':2,'losses_count':1}}}

def game(gid,result='win',started='2026-10-25T05:08:47.000Z',ongoing=False):
 return {'game_id':gid,'started_at':started,'duration':1524,'map':'Dry Arabia','kind':'rm_3v3','leaderboard':'rm_team','season':14,'patch':11308,'ongoing':ongoing,
  'teams':[[{'player':{'profile_id':10,'name':'epsilon','civilization':'abbasid_dynasty','result':result,'rating':1403,'rating_diff':28}}],[{'player':{'profile_id':99,'name':'foe','civilization':'french','result':'loss' if result=='win' else 'win','rating':1390,'rating_diff':-28}}]]}

class PlayerProfilesTests(unittest.TestCase):
 def test_reference_players_are_the_reference_game_players_once(self):
  refs=reference_players(LIBRARY);self.assertEqual([r['profileId'] for r in refs],[10]);self.assertEqual(refs[0]['reference']['buildId'],'french-observed-4v4');self.assertEqual(refs[0]['reference']['matchId'],'online-500')
 def test_normalize_mode_sorts_history_and_civs_and_drops_empty(self):
  m=normalize_mode(PROFILE['modes']['rm_team']);self.assertEqual([h['rating'] for h in m['ratingHistory']],[1432,1403]);self.assertEqual(m['civilizations'][0]['civilization'],'abbasid');self.assertEqual(m['civilizations'][1]['civilization'],'malians');self.assertEqual([s['season'] for s in m['previousSeasons']],[13,12]);self.assertEqual(m['rankLevel'],'conqueror_1')
  self.assertIsNone(normalize_mode(PROFILE['modes']['rm_solo']));self.assertIsNone(normalize_mode(None))
 def test_normalize_profile(self):
  p=normalize_profile(PROFILE);self.assertEqual(p['avatar'],'https://x/avatar.jpg');self.assertEqual(sorted(p['modes']),['rm_1v1_elo','rm_team']);self.assertEqual(p['siteUrl'],'https://aoe4world.com/players/10')
  with self.assertRaises(TimelineError):normalize_profile({'name':'x'})
 def test_normalize_game_from_player_perspective(self):
  g=normalize_game(game(7),10);self.assertEqual((g['civilization'],g['result'],g['ratingDiff'],g['team'],g['matchId']),('abbasid','win',28,0,'online-7'));self.assertEqual(len(g['players']),2)
  self.assertIsNone(normalize_game(game(8),12));self.assertIsNone(normalize_game(game(9,ongoing=True),10))
 def test_build_snapshot_pages_and_collection_links(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir();(root/'data/game-library.json').write_text(json.dumps(LIBRARY),encoding='utf-8')
   calls=[]
   def fetch(url):
    calls.append(url)
    if url.endswith('/players/10'):return PROFILE
    if 'page=1' in url:return {'games':[game(500),game(501,'loss','2026-10-24T05:08:47.000Z'),game(502,'win','2026-10-26T05:08:47.000Z')]+[game(1000+i) for i in range(37)],'next_page':2}
    return {'games':[game(2000)],'next_page':None}
   snap=build_snapshot(root,fetch,pages=3,now=0)
   self.assertEqual(snap['generatedAt'],'1970-01-01T00:00:00Z');self.assertEqual(len(calls),3);self.assertIn('include_alts=false',calls[1])
   p=snap['players'][0];self.assertEqual(p['reference']['buildId'],'french-observed-4v4');self.assertEqual(len(p['recentGames']),41);self.assertEqual(p['recentGames'][0]['gameId'],502)
   by={g['gameId']:g for g in p['recentGames']};self.assertTrue(by[500]['inCollection'] and by[500]['timeline']);self.assertTrue(by[501]['inCollection'] and not by[501]['timeline']);self.assertNotIn('inCollection',by[502])
   self.assertEqual((p['collectionMatches'],p['collectionTimelines']),(2,1))
   self.assertEqual(build_snapshot(root,fetch,only={99})['players'],[])

if __name__=='__main__':unittest.main()
