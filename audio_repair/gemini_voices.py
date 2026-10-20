"""Actual free-tier Gemini TTS trials, with the existing GitHub secret; no substituted audio."""
from pathlib import Path
import urllib.request,urllib.error,json,os,base64,subprocess,hashlib,sys
ROOT=Path(__file__).resolve().parent.parent;out=ROOT/'gemini-voice-tests';out.mkdir(exist_ok=True)
key=os.environ['GEMINI_API_KEY'];text='في سنة ألف تسعمية تمانية وستين، نقلوا معبد أبو سِمْبِل. وآخر جملة لازم تتقال كاملة. الصوت واضح، ومن غير تقطيع في النهاية.'
style='Egyptian Arabic (ar-EG), natural Cairo pronunciation, mature male documentary narrator with a low resonant voice. Clear precise articulation, relaxed measured pace, no singing, no music. Read the transcript verbatim, preserve all words and say the year naturally in Egyptian Arabic. Do not read instructions aloud.'
rows=[]
for voice in ['Charon','Orus']:
 for model in ['gemini-3.8-flash-tts','gemini-3.8-flash-lite-tts']:
  payload={'model':model,'input':[{'type':'user_input','content':[{'type':'text','text':text,'annotations':[{'type':'speech_metadata','style':style}]}]}],'response_format':{'type':'audio'},'generation_config':{'speech_config':[{'voice':voice}]}}
  try:
   req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/interactions',data=json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=150) as response:raw=json.load(response)
   blocks=[c for s in raw.get('steps',[]) if s.get('type')=='model_output' for c in s.get('content',[]) if c.get('type')=='audio' and c.get('data')]
   if not blocks:raise ValueError('No audio returned')
   wav=out/(voice+'.wav');wav.write_bytes(base64.b64decode(blocks[-1]['data']))
   subprocess.run(['ffmpeg','-y','-v','error','-i',str(wav),'-codec:a','libmp3lame','-q:a','2',str(out/(voice+'.mp3'))],check=True)
   rows.append({'voice':voice,'model':model,'generated':True,'text':text,'style':style,'sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),'interaction_id':raw.get('id'),'newly_synthesized':True,'reference_video_used':False})
   print(json.dumps(rows[-1],ensure_ascii=False),flush=True);break
  except urllib.error.HTTPError as e:
   detail=e.read().decode(errors='replace').replace(key,'[redacted]')
   rows.append({'voice':voice,'model':model,'generated':False,'http_status':e.code,'error':detail[:1000]});print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
   if e.code in (401,403,429):break
  except Exception as e:
   rows.append({'voice':voice,'model':model,'generated':False,'error':type(e).__name__});print(json.dumps(rows[-1]),flush=True)
 (out/'generation-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
files=list(out.glob('*.mp3'))
if files:
 from faster_whisper import WhisperModel
 sys.path.insert(0,str(ROOT));from motion_feature.audit_voice import number_checks
 model=WhisperModel('medium',device='cpu',compute_type='int8',cpu_threads=4);transcripts=[]
 for p in files:
  segs,_=model.transcribe(str(p),language='ar',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
  words=[w for seg in segs for w in seg.words or []];transcript=' '.join(w.word.strip() for w in words)
  record={'file':p.name,'transcript':transcript,'number_checks':number_checks(transcript,[1968]),'last_word':words[-1].word.strip() if words else None,'not_subjective_voice_approval':True};transcripts.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
 (out/'independent-transcripts.json').write_text(json.dumps(transcripts,ensure_ascii=False,indent=2))
