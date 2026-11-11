import copy
import json
import pathlib
import struct
import tempfile
import types
import unittest
from unittest.mock import patch

import collect_tierlists as collector


class TierCollectionTests(unittest.TestCase):
    def match(self):
        return {'id': 71, 'matchtype_id': 1, 'startgametime': 100, 'completiontime': 500,
                'matchurls': [{'url': 'https://example/replay/windows/4.0.0/12260/test.gz'}],
                'matchhistoryreportresults': [
                    {'profile_id': 11, 'civilization_id': 1, 'teamid': 0, 'resulttype': 1},
                    {'profile_id': 22, 'civilization_id': 2, 'teamid': 1, 'resulttype': 0}],
                'matchhistorymember': [{'profile_id': 11, 'oldrating': 1250}, {'profile_id': 22, 'oldrating': 1300}]}

    def test_patch_and_outcomes_fail_closed(self):
        match = self.match()
        self.assertEqual(collector.match_patch(match), 12260)
        self.assertTrue(collector.eligible_match(match, ['rm_1v1']))
        match['matchurls'].append({'url': 'https://example/replay/windows/4.0.0/11308/test.gz'})
        self.assertIsNone(collector.match_patch(match))
        match['matchhistoryreportresults'][1]['resulttype'] = 1
        self.assertFalse(collector.eligible_match(match, ['rm_1v1']))

    def test_ambiguous_player_join_is_rejected(self):
        replay = {'players': [{'pid': 0, 'civ': 'english', 'team': 0, 'name': 'Changed'},
                              {'pid': 1, 'civ': 'english', 'team': 0, 'name': 'B'}]}
        match = self.match()
        match['matchhistoryreportresults'][1].update(civilization_id=1, teamid=0)
        with self.assertRaises(ValueError):
            collector.bind_players(replay, match, {'11': 'A', '22': 'B'}, {1: 'english', 2: 'french'})

    def test_changed_alias_joins_only_a_unique_team_civilization(self):
        replay = {'players': [{'pid': 0, 'civ': 'english', 'team': 0, 'name': 'Old name'},
                              {'pid': 1, 'civ': 'french', 'team': 1, 'name': 'B'}]}
        self.assertEqual(collector.bind_players(replay, self.match(), {'11': 'New name', '22': 'B'}, {1: 'english', 2: 'french'}), {0: 11, 1: 22})

    def test_proportions_deduplication_and_missing_coverage(self):
        catalog = {'civilizations': [{'id': 'english', 'name': 'English'}, {'id': 'french', 'name': 'French'}],
                   'records': [
                       {'pbgid': 1, 'id': 'archer', 'name': 'Archer', 'kind': 'units', 'commandKind': 'train', 'civs': ['english', 'french']},
                       {'pbgid': 2, 'id': 'knight', 'name': 'Knight', 'kind': 'units', 'commandKind': 'train', 'civs': ['english', 'french']},
                       {'pbgid': 3, 'id': 'villager', 'name': 'Villager', 'kind': 'nonmilitary', 'commandKind': 'train', 'civs': []},
                       {'pbgid': 7, 'id': 'ram', 'name': 'Ram', 'kind': 'units', 'commandKind': 'build', 'civs': []},
                       {'pbgid': 1, 'id': 'wheelbarrow', 'name': 'Wheelbarrow', 'kind': 'technologies', 'commandKind': 'research', 'civs': []},
                       {'pbgid': 4, 'id': 'wing', 'name': 'Wing', 'kind': 'landmarks', 'commandKind': 'research', 'civs': ['english']}]}
        replay = {'patch': 12260, 'players': [{'pid': 0, 'civ': 'english', 'team': 0, 'name': 'A'}, {'pid': 1, 'civ': 'french', 'team': 1, 'name': 'B'}],
                  'commands': [[0, 'train', 1, 1], [0, 'train', 1, 2], [0, 'train', 2, 3], [0, 'train', 3, 4],
                               [0, 'research', 1, 5], [0, 'research', 1, 6], [0, 'research', 4, 7],
                               [0, 'build', 7, 8], [1, 'train', 99, 1], [1, 'research', 1, 2]]}
        manifest = {'generatedAt': '2026-11-10', 'sampling': [], 'errors': [], 'aliases': {'11': 'A', '22': 'B'},
                    'races': [{'id': 1, 'name': 'English'}, {'id': 2, 'name': 'French'}], 'matches': [self.match()]}
        old_match = copy.deepcopy(self.match())
        old_match['id'] = 72
        old_match['matchurls'][0]['url'] = 'https://example/replay/windows/4.0.0/11308/a.gz'
        manifest['matches'].append(old_match)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            replay_path = root / 'cache/replays/71.rec'
            replay_path.parent.mkdir(parents=True)
            replay_path.write_bytes(b'fixture')
            with patch.object(collector, 'ROOT', root), patch.object(collector, 'CACHE', root / 'cache'), patch.object(collector, 'parse', return_value=replay):
                result = collector.export(manifest, 12260, catalog)
        winner, loser = result['observations']
        self.assertEqual(winner['units'], {'archer': 2, 'knight': 1, 'ram': 1})
        self.assertEqual(winner['technologies'], ['wheelbarrow'])
        self.assertEqual(winner['landmarks'], ['wing'])
        self.assertTrue(winner['unitChoicesAvailable'])
        self.assertFalse(loser['unitChoicesAvailable'])
        self.assertTrue(loser['technologyChoicesAvailable'])
        self.assertEqual(loser['result'], 'loss')
        self.assertEqual(winner['rating'], 1250)
        self.assertEqual(result['coverage']['matches'], 1)
        self.assertEqual(result['coverage']['excludedOtherPatchOrUnknown'], 1)

    def test_invalid_replay_is_rejected(self):
        with self.assertRaises(ValueError):
            collector.unpack(b'<html>Unavailable</html>')

    def test_replay_budget_is_balanced_across_modes(self):
        matches = [{'id': mode * 100 + i, 'matchtype_id': mode} for mode in range(1, 5) for i in range(10)]
        sample = collector.replay_sample(matches, 12)
        self.assertEqual(len({m['id'] for m in sample}), 12)
        self.assertEqual([sum(m['matchtype_id'] == mode for m in sample) for mode in range(1, 5)], [3, 3, 3, 3])
        self.assertEqual(sample, collector.replay_sample(list(reversed(matches)), 12))

    def test_player_upgrade_commands_are_included(self):
        payload = bytes.fromhex('2300820660040000090000000200000006010000ee030000000000061405016b6d1f00')
        player = types.SimpleNamespace(pid=6, name='A', civ='ottoman', team=0)
        replay = types.SimpleNamespace(players=[player], version=12260, duration_seconds=400,
                                       ticks=lambda: iter([types.SimpleNamespace(tick=3102, blocks=[(0, payload)])]))
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / 'example.rec'
            path.write_bytes(b'fixture')
            with patch.object(collector, 'CACHE', root), patch.object(collector.recfile, 'load', return_value=replay):
                parsed = collector.parse(path)
        self.assertEqual(parsed['commands'], [[6, 'research', 2059627, 3102]])

    def test_public_means_include_zero_share_without_publishing_players(self):
        rows = []
        for gid, result, units in [(1, 'win', {'archer': 2, 'spear': 8}), (2, 'win', {'spear': 10}), (3, 'loss', {'archer': 5, 'spear': 5})]:
            rows.append({'gameId': gid, 'profileId': 99, 'civ': 'english', 'mode': 'rm_1v1', 'rating': 1200,
                         'result': result, 'choicesAvailable': True, 'unitChoicesAvailable': True,
                         'technologyChoicesAvailable': True, 'landmarkChoicesAvailable': True,
                         'units': units, 'technologies': [], 'landmarks': []})
        data = {'observations': rows, 'generatedAt': '2026-11-10', 'patch': {'id': 12260}, 'notes': [],
                'civilizations': [], 'items': {}, 'coverage': {}, 'provenance': {'sampling': [{'profiles': [99]}]},
                'audit': {'unknownBlueprints': [], 'parseErrors': [], 'downloadErrors': [], 'discoveryErrors': []}}
        public = collector.aggregate_public(data)
        group = public['groups'][0]['units']
        archer = group['items']['archer']
        self.assertEqual((group['games'], group['wins'], archer['uses'], archer['wins']), (3, 2, 2, 1))
        self.assertAlmostEqual(archer['winShareSum'] / group['wins'], .1)
        self.assertAlmostEqual(archer['lossShareSum'] / (group['games'] - group['wins']), .5)
        self.assertAlmostEqual(archer['shareSum'] / group['games'], .7 / 3)
        self.assertNotIn('profileId', json.dumps(public))
        self.assertNotIn('gameId', json.dumps(public))
        self.assertNotIn('sampling', public['provenance'])


if __name__ == '__main__':
    unittest.main()
