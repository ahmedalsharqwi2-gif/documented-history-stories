from pathlib import Path
import subprocess,json,hashlib,importlib.metadata,sys
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from audio_repair.delivery import probe
from motion_feature.audit_voice import number_checks,norm
out=ROOT/'neural-review';out.mkdir(exist_ok=True)
plan=json.loads((ROOT/'feature-work/plan.json').read_text())
forms={'{start_year}':'ألف وتسعمائة وأربعة وستين','{end_year}':'ألف وتسعمائة وثمانية وستين','{height}':'خمسة وستين','{setback}':'مائتين'}
text=' '.join(s['narration'] for s in plan['scenes'])
for tag,spoken in forms.items():text=text.replace(tag,spoken)
text=text.replace('أبو سمبل','أبو سِمْبِل').replace('نفرتاري','نِفِرْتَارِي').replace('رمسيس','رَمْسِيس')
path=out/'Shakir-full-story.mp3';subprocess.run(['edge-tts','--voice','ar-EG-ShakirNeural','--rate=-10%','--text',text,'--write-media',str(path)],check=True,timeout=250)
(out/'source.json').write_text(json.dumps({'voice':'ar-EG-ShakirNeural','engine':'Microsoft Edge online speech via edge-tts','client_version':importlib.metadata.version('edge-tts'),'text':text,'script_origin':plan['script_origin'],'model':plan['response_model'],'newly_synthesized':True,'number_wording':'Standard Arabic number forms; same numeric values, original Gemini narrative retained','duration':float(probe(path)['format']['duration']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
# Original provider samples already generated in the earlier job; preserve exact bytes.
import shutil
for p in (ROOT/'edge-input').glob('*.mp3'):shutil.copy2(p,out/p.name)
from faster_whisper import WhisperModel
model=WhisperModel('medium',device='cpu',compute_type='int8',cpu_threads=4);reports=[]
for p in sorted(out.glob('*.mp3')):
 segs,_=model.transcribe(str(p),language='ar',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
 words=[{'text':w.word.strip(),'start':w.start,'end':w.end} for seg in segs for w in seg.words or []];transcript=' '.join(w['text'] for w in words)
 full=p.name=='Shakir-full-story.mp3';checks=number_checks(transcript,[1964,1968,65,200] if full else [1968]);ending='كلها' if full else 'كاملة'
 report={'file':p.name,'transcript':transcript,'number_checks':checks,'expected_final_word':ending,'actual_final_word':words[-1]['text'] if words else None,'ending_word_recognized':bool(words and norm(words[-1]['text'])==norm(ending)),'not_subjective_voice_approval':True}
 reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
(out/'independent-transcripts.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
