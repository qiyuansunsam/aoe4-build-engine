import tempfile
import unittest
from pathlib import Path

from tactical_probe import recorded_sample


class TelemetryTests(unittest.TestCase):
    def test_tc_lifetimes_and_hostile_hits(self):
        text = '\n'.join([
            'HDR|6|0|100|100|2',
            'N|0|1,1,building_town_center_capital_hre,7000,1,0,-30,0,7000;2,2,building_town_center_capital_sul,7000,1,0,30,0,7000;3,1,unit_spearman_2_hre,100,0,50,20,0,100;4,2,unit_villager_1_sul,50,0,60,25,0,50',
            'PQ|0|1,0,-,-;2,1,unit,villager',
            'V|0|3,3',
            'T|0',
            'H|1|3,4,50,0,0,0;3,1,10,6990,0,0',
            'K|1|victim=e4;victimSquad=s60',
            'PQ|5|1,1,unit,villager',
            'T|5',
            'X|10|2',
            'T|10',
            'T|15',
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sample.rlog'
            path.write_text(text)
            result = recorded_sample(path)
        self.assertEqual(result['hostile_damage_events_resolved'], 1)
        self.assertEqual(result['confirmed_enemy_villagers_killed_by_player'], {1:1})
        self.assertEqual(result['observed_tc_queue_empty_seconds'], {1:5})
        self.assertEqual(result['observed_tc_queue_known_seconds'], {1:15, 2:10})
        self.assertEqual(result['first_non_scout_military_in_enemy_half_seconds'], {1:0})
        self.assertEqual(result['military_presence_cell_seconds'], {1:15})


if __name__ == '__main__':
    unittest.main()
