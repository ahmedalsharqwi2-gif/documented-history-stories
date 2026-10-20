"""Independent, unprompted ASR checks: approximate timing never approves a critical number."""
from pathlib import Path
import argparse,json,re,unicodedata
VARIANTS={1964:['1964','الف تسعمية اربعة وستين','الف وتسعمية واربعة وستين','الف تسعمائة اربعة وستين','الف وتسعمائة واربعة وستين','الف وتسعمئه واربعه وستين'],1968:['1968','الف تسعمية تمانية وستين','الف وتسعمية وتمانية وستين','الف وتسعمائة وثمانية وستين','الف تسعمائة ثمانية وستين'],65:['65','خمسة وستين','خمسه وستين'],200:['200','ميتين','متين','مئتين','مائتين','مئتان','مائتان']}
def norm(t):
    t=''.join(c for c in unicodedata.normalize('NFKD',t) if unicodedata.category(c)!='Mn')
    t=t.translate(str.maketrans('أإآىة٠١٢٣٤٥٦٧٨٩','ااايه0123456789'))
    return re.sub(r'[^\w\s]',' ',t).strip()
def number_checks(text,values):
    t=norm(text);out={}
    for value in values:
        options=VARIANTS[value];matches=[v for v in options if re.search(r'(?<!\w)'+re.escape(norm(v))+r'(?!\w)',t)]
        out[str(value)]={'passed':bool(matches),'matching_forms':matches}
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('wav');p.add_argument('--model',default='medium');a=p.parse_args()
    from faster_whisper import WhisperModel
    path=Path(a.wav);meta=json.loads(path.with_suffix('.voice.json').read_text())
    model=WhisperModel(a.model,device='cpu',compute_type='int8',cpu_threads=4)
    segments,info=model.transcribe(str(path),language='ar',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
    words=[];parts=[]
    for seg in segments:
        parts.append(seg.text)
        for w in seg.words or []:words.append({'text':w.word.strip(),'start':w.start,'end':w.end,'probability':w.probability})
    transcript=' '.join(parts).strip();checks=number_checks(transcript,meta.get('expected_values',[]))
    report={'transcript':transcript,'words':words,'number_checks':checks,'all_numbers_passed':all(v['passed'] for v in checks.values()),'asr_model':a.model,'prompt_used':False,'language_probability':info.language_probability,'speaker':meta['speaker'],'duration':meta['duration']}
    path.with_suffix('.audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='words'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
