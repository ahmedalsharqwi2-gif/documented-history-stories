import unittest
from types import SimpleNamespace
from unittest.mock import patch
from openmontage_factory.run import parse_day, licensed_picks, make_script, subject_query, conservative_commons


class ProductionContract(unittest.TestCase):
    def test_metadata_selection_avoids_bulk_downloads_and_restores_adapter(self):
        candidate=lambda ident:SimpleNamespace(clip_id=ident,width=1600,height=1200,license='CC BY 4.0',
            source_tags='Chichen Itza',source_url='https://commons.wikimedia.org/example',extra={'mime':'image/jpeg'})
        class Source:
            def __init__(self):
                self.candidates=[candidate(str(i)) for i in range(20)]
                self.downloaded=[]
            def search(self,query,filters):return self.candidates
            def download(self,item,path):
                self.downloaded.append(item)
                return path
        old_search,old_download=Source.search,Source.download
        seen=set()
        with (patch('openmontage_factory.run.time.monotonic',return_value=0),
              patch('openmontage_factory.run.time.sleep') as sleep,conservative_commons(seen,Source)):
            source=Source();rows=source.search('Chichen Itza',None)
            self.assertEqual(len(rows),2)
            source.download(rows[0],'one');seen.add(rows[0].clip_id)
            rows2=source.search('Chichen Itza',None)
            self.assertNotEqual(rows2[0].clip_id,rows[0].clip_id)
            source.download(rows2[0],'two');sleep.assert_called_once_with(5)
            self.assertEqual(len(source.downloaded),2)
        self.assertIs(Source.search,old_search);self.assertIs(Source.download,old_download)

    def test_provider_retry_after_is_honored_before_next_download(self):
        import requests
        class Source:
            def __init__(self):
                self.candidates=[]
                self.calls=0
            def search(self,query,filters):return self.candidates
            def download(self,item,path):
                self.calls+=1
                response=requests.Response();response.status_code=429;response.headers['Retry-After']='120'
                raise requests.HTTPError(response=response)
        with (patch('openmontage_factory.run.time.monotonic',return_value=0),
              patch('openmontage_factory.run.time.sleep') as sleep,conservative_commons(set(),Source)):
            source=Source()
            for _ in range(2):
                with self.assertRaises(requests.HTTPError):source.download(None,'test')
            sleep.assert_called_once_with(120)
            self.assertEqual(source.calls,2)

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
        specific={**base,'source_tags':'Chichen Itza Nunnery building','width':1200,'height':1000}
        generic={**base,'source_tags':'Chichen Itza Governor visit','width':4000,'height':3000}
        self.assertIs(licensed_picks([generic,specific],'Chichen Itza Nunnery building')[0],specific)

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
