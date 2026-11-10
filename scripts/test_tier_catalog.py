import unittest

from build_tier_catalog import build, family_name, technology_name, classify


def base_catalog(units):
    return {'provenance': {'patch': '17.0.12260'}, 'units': units,
            'buildings': [], 'technologies': [], 'civilizations': []}


def unit(name, blueprint, squad, entity):
    return {'id': blueprint, 'name': name, 'civilization': 'english', 'classes': ['military'],
            'source': {'pbgid': squad}, 'entitySource': {'pbgid': entity}}


class InstalledIdentityTests(unittest.TestCase):
    def test_named_families_and_tiers(self):
        self.assertNotEqual(family_name('Ghillie'), family_name('Scout'))
        self.assertEqual(family_name('Elite Archer'), family_name('Archer'))
        for name in ('Champion', 'Rider'):
            self.assertEqual(family_name("Jeanne's Elite " + name), family_name("Jeanne's " + name))

    def test_field_and_workshop_ram_share_family(self):
        local = base_catalog([unit('Battering Ram', 'unit_ram_3_eng', 166409, 166303),
                              unit('Battering Ram', 'unit_workshop_ram_3_eng', 900001, 900002)])
        _, records, omitted = build(local)
        idx = {(r['commandKind'], r['pbgid']): r for r in records}
        self.assertEqual({idx[k]['id'] for k in [('build', 166303), ('train', 166409), ('train', 900001)]}, {'units:battering-ram'})
        self.assertEqual(idx[('build', 166303)]['kind'], 'units')
        self.assertTrue(all(r['identityPatchVerified'] for r in records))
        self.assertEqual(omitted, [])

    def test_ambiguous_entity_is_not_assigned_arbitrarily(self):
        _, records, omitted = build(base_catalog([unit('Hulk', 'hulk', 1, 10), unit('War Cog', 'war_cog', 2, 10)]))
        self.assertFalse(any(r['commandKind'] == 'build' for r in records))
        self.assertEqual(omitted[0]['pbgid'], 10)

    def test_missing_unit_classes_remain_unknown(self):
        row = unit('Bondi', 'dummy_bondi', 1, 2)
        row['classes'] = []
        _, records, omitted = build(base_catalog([row]))
        self.assertEqual(records, [])
        self.assertEqual(omitted[0]['pbgid'], 1)

    def test_upgrade_target_disambiguates_generic_names(self):
        self.assertEqual(technology_name({'name': 'Upgrade to Elite', 'id': 'x',
                                         'description': 'Upgrade Hirdman to Elite Hirdman.'}), 'Upgrade to Elite Hirdman')
        self.assertEqual(technology_name({'name': 'Upgrade to Elite', 'id': 'y',
                                         'description': 'Upgrade Riddari into Elite Riddari.'}), 'Upgrade to Elite Riddari')

    def test_landmarks_wings_and_ordinary_buildings(self):
        self.assertEqual(classify('technologies', {'id': 'upgrade_add_economy_wing_feudal'}), 'landmarks')
        self.assertEqual(classify('buildings', {'id': 'building_landmark_age1_westminster_hall_eng'}), 'landmarks')
        for blueprint in ('building_town_center_capital_eng', 'building_resource_fish_pond_sco', 'building_sacred_grove_vik'):
            self.assertEqual(classify('buildings', {'id': blueprint}), 'buildings')


if __name__ == '__main__':
    unittest.main()
