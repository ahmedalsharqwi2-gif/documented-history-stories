from pathlib import Path
import sys,json,subprocess
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from audio_repair.gemini_client import generate
from audio_repair.delivery import probe
from audio_repair.quality import speech_accuracy
from motion_feature.audit_voice import number_checks,norm
plan=json.loads((ROOT/'feature-work/plan.json').read_text());text=' '.join(s['spoken_text'] for s in plan['scenes'])
for a,b in {'أبو سمبل':'أبو سِمْبِل','نفرتاري':'نِفِرْتَارِي','رمسيس':'رَمْسِيس'}.items():text=text.replace(a,b)
out=ROOT/'gemini-long-narration';out.mkdir(exist_ok=True);wav=out/'Charon-full-Abu-Simbel.wav';report=generate(text,wav)
mp3=out/'Charon-full-Abu-Simbel.mp3';subprocess.run(['ffmpeg','-y','-v','error','-i',str(wav),'-codec:a','libmp3lame','-q:a','2',str(mp3)],check=True)
from faster_whisper import WhisperModel
model=WhisperModel('medium',device='cpu',compute_type='int8',cpu_threads=4)
segs,_=model.transcribe(str(wav),language='ar',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
words=[{'text':w.word.strip(),'start':w.start,'end':w.end} for s in segs for w in s.words or []];actual=' '.join(w['text'] for w in words)
quality=speech_accuracy(text,actual);checks=number_checks(actual,[1964,1968,65,200])
result={'model':report['model'],'voice':report['voice'],'duration':float(probe(mp3)['format']['duration']),'expected':text,'transcript':actual,'words':words,'number_checks':checks,**quality,'expected_final_word':'كلها','last_word_complete':bool(words and norm(words[-1]['text'])==norm('كلها')),'subjective_voice_approval':False,'production_defaults_changed':False}
(out/'long-reading-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('words','expected_tokens','recognized_tokens')},ensure_ascii=False),flush=True)
subprocess.run(['ffmpeg','-y','-v','error','-sseof','-20','-i',str(mp3),'-codec:a','libmp3lame','-q:a','2',str(out/'Charon-last-20-seconds.mp3')],check=True)
