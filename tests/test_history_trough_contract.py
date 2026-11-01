import unittest
from unittest.mock import Mock
import requests
from professional_motion.historical_sources import visual_contract,candidates,parse_candidates

class CastIronContractTests(unittest.TestCase):
 def test_trough_is_not_guessed_as_a_roman_arch_or_tier_count(self):
  contract=visual_contract('1303','Pontcysyllte Aqueduct and Canal','A cast iron trough carried above the valley.')
  self.assertEqual(contract['focus'],'cast_iron_trough')
  self.assertEqual(contract['material'],'cast_iron')
  self.assertNotIn('tier_count',contract)
  self.assertNotIn('arch',contract['allowed_modes'])
  self.assertIn('arches',contract['forbidden_features'])
 def test_verified_unused_starter_survives_feed_failure(self):
  def failed(*args,**kwargs):raise requests.ConnectionError('test only')
  rows=candidates(fetch=failed)
  row=next(r for r in rows if r['key']=='unesco-1303-cast_iron_trough')
  self.assertEqual(row['url'],'https://whc.unesco.org/en/list/1303/')
  self.assertEqual(row['variant'],'cast_iron_trough')
 def test_xml_trough_does_not_require_fabricated_tiers(self):
  raw=b'<root><row><id_number>1303</id_number><category>Cultural</category><site>Pontcysyllte Aqueduct and Canal</site><short_description>A cast iron trough with source described supporting stone piers; the description is retained only for its structural scope and not guessed dimensions.</short_description></row></root>'
  rows=parse_candidates(raw)
  self.assertEqual(rows[0]['visual_contract']['focus'],'cast_iron_trough')

if __name__=='__main__':unittest.main()
