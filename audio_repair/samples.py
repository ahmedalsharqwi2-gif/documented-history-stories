from pathlib import Path
import argparse,json,hashlib,time,subprocess,re,os
ROOT=Path(__file__).resolve().parent.parent
TEXTS={
'raw':'في سنة ألف تسعمية تمانية وستين، نقلوا معبد أبو سمبل. وآخر جملة لازم تتقال كاملة.',
'vowelled':'في سَنَة أَلْف تِسْعُمِيَّة تَمَانْيَة وَسِتِّين، نَقَلوا مَعْبَد أبو سِمْبِل. وآخِر جُمْلَة لازِم تِتْقال كامْلَة.',
'slow':'في سَنَة أَلْف تِسْعُمِيَّة تَمَانْيَة وَسِتِّين، نَقَلوا مَعْبَد أبو سِمْبِل. وآخِر جُمْلَة لازِم تِتْقال كامْلَة.',
'msa':'في عام ألف وتسعمائة وثمانية وستين، نُقِل معبد أبو سمبل. ويجب نطق الجملة الأخيرة كاملة.'}
def ff(args):subprocess.run(['ffmpeg','-y','-v','error',*map(str,args)],check=True)
def export():
 from huggingface_hub import snapshot_download
 snap=Path(snapshot_download('mohammedaly22/VoiceTut-TTS',allow_patterns=['reference_speakers/*']))
 data=json.loads((snap/'reference_speakers/references.json').read_text());out=ROOT/'audio-lab/catalogue';out.mkdir(parents=True,exist_ok=True);rows=[]
 for r in data:
  name=r['speaker_name'];path=Path(r['audio_path']);candidates=[snap/'reference_speakers'/path.name,snap/path]
  source=next(p for p in candidates if p.exists());target=out/(name+'.mp3');ff(['-i',source,'-codec:a','libmp3lame','-q:a','2',target])
  rows.append({'speaker':name,'gender':r.get('gender'),'file':target.name,'kind':'original_library_reference_NOT_new_generation','reference_text':r.get('reference_text'),'source':'mohammedaly22/VoiceTut-TTS','snapshot':snap.name})
 (out/'catalogue.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print('Exported',len(rows),'original library reference voices')
def generate(speaker,condition):
 import numpy as np,soundfile as sf,torch
 from voicetut_tts import VoiceTutTTS
 from voicetut_tts.engine import GenerationParams
 torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(20261021)
 tts=VoiceTutTTS.from_pretrained('mohammedaly22/VoiceTut-TTS',device='cpu',dtype='float32',language='arz');sp=next(s for s in tts.list_speakers() if s.speaker_name==speaker)
 speed=.9 if condition=='slow' else 1.;params=GenerationParams(num_step=32,guidance_scale=2,speed=speed)
 text=TEXTS[condition];out=ROOT/'audio-lab/generated'/speaker/condition;out.mkdir(parents=True,exist_ok=True)
 wav=np.asarray(tts.model.generate(text=text,language='arz',ref_audio=sp.audio_path,ref_text=sp.reference_text,**params.as_kwargs())[0],np.float32)
 if not np.isfinite(wav).all():raise ValueError('Invalid waveform')
 sf.write(out/'sample.wav',wav,tts.sampling_rate,subtype='PCM_16');ff(['-i',out/'sample.wav','-codec:a','libmp3lame','-q:a','2',out/'sample.mp3'])
 report={'speaker':speaker,'condition':condition,'text':text,'speed':speed,'steps':32,'newly_generated':True,'model':'mohammedaly22/VoiceTut-TTS','duration':len(wav)/tts.sampling_rate,'sha256':hashlib.sha256((out/'sample.wav').read_bytes()).hexdigest(),'reference_video_used':False}
 (out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
def audit(speaker,condition):
 from faster_whisper import WhisperModel
 out=ROOT/'audio-lab/generated'/speaker/condition;model=WhisperModel('medium',device='cpu',compute_type='int8',cpu_threads=4)
 segs,_=model.transcribe(str(out/'sample.wav'),language='ar',beam_size=5,vad_filter=False,word_timestamps=True,condition_on_previous_text=False)
 words=[{'text':w.word.strip(),'start':w.start,'end':w.end} for s in segs for w in s.words or []];text=' '.join(w['text'] for w in words)
 import sys;sys.path.insert(0,str(ROOT));from motion_feature.audit_voice import number_checks,norm
 values=number_checks(text,[1968]);end=bool(words and norm(words[-1]['text'])==norm('كاملة'))
 report={'transcript':text,'words':words,'number_checks':values,'last_word_complete':end,'automatic_result_only_not_subjective_voice_approval':True}
 (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
def edge():
 out=ROOT/'audio-lab/alternative';out.mkdir(parents=True,exist_ok=True);rows=[]
 for name in ['ar-EG-ShakirNeural','ar-EG-SalmaNeural']:
  for kind in ['raw','msa']:
   target=out/(name+'-'+kind+'.mp3');result=subprocess.run(['edge-tts','--voice',name,'--text',TEXTS[kind],'--write-media',str(target)],capture_output=True,text=True,timeout=100)
   rows.append({'voice':name,'condition':kind,'generated':result.returncode==0 and target.exists(),'error':result.stderr[-600:] if result.returncode else None})
 (out/'provider-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['catalogue','generate','audit','edge']);p.add_argument('--speaker');p.add_argument('--condition',default='vowelled');a=p.parse_args()
 if a.mode=='catalogue':export()
 elif a.mode=='edge':edge()
 elif a.mode=='audit':audit(a.speaker,a.condition)
 else:generate(a.speaker,a.condition)
