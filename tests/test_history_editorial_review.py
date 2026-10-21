import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import history_editorial_review as editor
class HistoricalEditorialTests(unittest.TestCase):
 def response(self,text):
  class Response:
   status_code=200
   def json(self):return {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps({"narration":text,"edits":[],"needs_review":False})}]}}]}
  return Response()
 def episode(self,folder):
  state=Path(folder)/'state';state.mkdir();p=state/'current_episode.json'
  p.write_text(json.dumps({"title":"القسطنطينية","narration":"المسودة القديمة"}));return p
 def test_short_corrected_script_is_expanded_once(self):
  with tempfile.TemporaryDirectory() as folder:
   p=self.episode(folder);old=os.getcwd()
   try:
    os.chdir(folder)
    short='ده مش عشان اللي '+('كلمة '*138)
    full='ده مش عشان اللي سنة ألف وربعمية وتلاتة وخمسين '+('حكاية '*196)
    with patch.dict(os.environ,{"GEMINI_TEXT_API_KEY":"test-key"}),patch.object(editor,'reserve'),patch.object(editor.requests,'post',side_effect=[self.response(short),self.response(full)]) as post:
     editor.review(p)
    self.assertEqual(post.call_count,2)
    self.assertGreaterEqual(len(json.loads(p.read_text())["narration"].split()),180)
   finally:os.chdir(old)
 def test_wrong_conquest_century_cannot_survive_review(self):
  with tempfile.TemporaryDirectory() as folder:
   p=self.episode(folder);old=os.getcwd()
   try:
    os.chdir(folder)
    wrong='ده مش عشان اللي سنة ألف وخمسمية وتلاتة وخمسين '+('حكاية '*190)
    with patch.dict(os.environ,{"GEMINI_TEXT_API_KEY":"test-key"}),patch.object(editor,'reserve'),patch.object(editor.requests,'post',return_value=self.response(wrong)):
     editor.review(p)
    corrected=json.loads(p.read_text())["narration"]
    self.assertNotIn("خمسمية",corrected)
    self.assertIn("ربعمية",corrected)
   finally:os.chdir(old)

 def test_observed_malformed_date_is_repaired_before_voice(self):
  with tempfile.TemporaryDirectory() as folder:
   p=self.episode(folder);old=os.getcwd()
   try:
    os.chdir(folder)
    text='ده مش عشان اللي سنة ألف وربعمية وتلاتة وخمن '+('حكاية '*190)+' على مر السصول.'
    with patch.dict(os.environ,{"GEMINI_TEXT_API_KEY":"test-key"}),patch.object(editor,'reserve'),patch.object(editor.requests,'post',return_value=self.response(text)):
     editor.review(p)
    result=json.loads(p.read_text())["narration"]
    self.assertIn("ألف وربعمية وتلاتة وخمسين",result)
    self.assertIn("على مر العصور",result)
   finally:os.chdir(old)
 def test_unknown_year_wording_is_blocked_before_voice(self):
  with tempfile.TemporaryDirectory() as folder:
   p=self.episode(folder);old=os.getcwd()
   try:
    os.chdir(folder)
    text='ده مش عشان اللي سنة ألف وربعمية وسبعين '+('حكاية '*190)
    with patch.dict(os.environ,{"GEMINI_TEXT_API_KEY":"test-key"}),patch.object(editor,'reserve'),patch.object(editor.requests,'post',return_value=self.response(text)):
     with self.assertRaisesRegex(ValueError,'1453 anchor'):editor.review(p)
    self.assertEqual(json.loads(p.read_text())["narration"],"المسودة القديمة")
   finally:os.chdir(old)
