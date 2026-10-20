"""Exact-transcript Egyptian narration using Gemini TTS; no provider or recording fallback."""
from pathlib import Path
import urllib.request,json,base64,os,hashlib
MODEL='gemini-3.8-flash-tts'
STYLE='Egyptian Arabic ar-EG, native conversational Cairo accent. Mature warm male documentary storyteller, low resonant register, clear exact articulation, measured pace around 140 words per minute. Say the year numbers naturally in Egyptian Arabic. Preserve every word and sentence of the transcript, finish the last sentence clearly. No music, no sound effects, no singing, no spoken instructions.'
def generate(text,path,voice='Charon'):
 key=os.environ['GEMINI_API_KEY'];payload={'model':MODEL,'input':[{'type':'user_input','content':[{'type':'text','text':text,'annotations':[{'type':'speech_metadata','style':STYLE}]}]}],'response_format':{'type':'audio'},'generation_config':{'speech_config':[{'voice':voice}]}}
 req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/interactions',data=json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=240) as r:raw=json.load(r)
 audio=[c for s in raw.get('steps',[]) if s.get('type')=='model_output' for c in s.get('content',[]) if c.get('type')=='audio' and c.get('data')]
 if not audio:raise ValueError('Gemini did not return audio; no substituted voice is allowed')
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(audio[-1]['data']))
 report={'provider':'Gemini TTS','model':MODEL,'voice':voice,'text':text,'style':STYLE,'interaction_id':raw.get('id'),'newly_synthesized':True,'original_video_audio_used':False,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 path.with_suffix('.source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
