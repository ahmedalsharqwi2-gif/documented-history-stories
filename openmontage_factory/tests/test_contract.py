import unittest
from openmontage_factory.run import parse_day, licensed_picks


class ProductionContract(unittest.TestCase):
    def test_review_date_cannot_be_a_path(self):
        for invalid in ('../main','2026-2-1','2026-02-30','2026-11-10/secret'):
            with self.assertRaises(ValueError):parse_day(invalid)
        self.assertEqual(parse_day('2026-11-10'),'2026-11-10')

    def test_assets_require_subject_match_license_and_pixels(self):
        base={'width':1600,'height':1000,'license':'CC BY-SA 4.0',
              'source_tags':'Pontcysyllte Aqueduct Wales','source_url':'https://commons.wikimedia.org/example'}
        self.assertEqual(len(licensed_picks([base],'Pontcysyllte Aqueduct')),1)
        for changes in ({'license':'All rights reserved'},{'height':200},{'source_tags':'Roman temple Italy'}):
            self.assertEqual(licensed_picks([{**base,**changes}],'Pontcysyllte Aqueduct'),[])
        self.assertEqual(licensed_picks([base],''),[])


if __name__=='__main__':unittest.main()
