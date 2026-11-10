import unittest
from types import SimpleNamespace
from unittest.mock import patch
from openmontage_factory.run import parse_day, licensed_picks, make_script, subject_query


class ProductionContract(unittest.TestCase):
    def test_subject_query_keeps_the_actual_place_not_generic_shot_words(self):
        story={'source':{'title':'Pre-Hispanic City of Chichen-Itza'},'scenes':[
            {'image_query':'Chichen Itza cenote'}, {'image_query':'Chichen Itza Nunnery building'},
            {'image_query':'El Castillo Chichen Itza architecture'}, {'image_query':'INAH Mexico sign'}]}
        self.assertEqual(subject_query(story),'Chichen Itza')
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

    def test_uncertain_provider_requests_never_generate_again(self):
        for data in ({'phase':'author_requested'}, {'phase':'review_requested'}, {'phase':'length_repair_requested'},
                     {'phase':'editorial_rejected','editorial_review':{'passed':False}}):
            with patch('remotion_factory.author.ask_once') as provider:
                with self.assertRaises((ValueError, RuntimeError)):
                    make_script(SimpleNamespace(data=data))
                provider.assert_not_called()

    def test_acknowledged_script_resumes_without_writing_again(self):
        story={'title':'retained original'}
        with patch('remotion_factory.author.ask_once') as provider:
            self.assertIs(make_script(SimpleNamespace(data={'editorial_review':{'passed':True},'story':story})),story)
            provider.assert_not_called()


if __name__=='__main__':unittest.main()
