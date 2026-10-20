"""Second ASR pass bans digit tokens, so a year cannot be normalized twice."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from motion_feature.audit_voice import norm
PATTERNS={1964:r'الفو?تسع(?:ميه|مايه|مائه|مياء)و?اربعهو?ستين',1968:r'الفو?تسع(?:ميه|مايه|مائه|مياء)و?(?:تمانيه|ثمانيه)و?ستين',65:r'خمسه?و?ستين',200:r'(?:ميتين|متين|ماتين|مايتين|ماتان|ميتان)'}
def main():
    from faster_whisper import WhisperModel
    output=ROOT/'number-word-review';output.mkdir(exist_ok=True);reports=[]
    for size in ['small','medium']:
        model=WhisperModel(size,device='cpu',compute_type='int8',cpu_threads=4)
        # Prevent only numeric output tokens, without revealing a target sentence or a number.
        vocab=model.hf_tokenizer.get_vocab();suppress=[-1]+[i for i in vocab.values() if re.search(r'\d',model.hf_tokenizer.decode([i]))]
        for part in [3,9,13]:
            path=ROOT/f'number-review-input/part-{part:02d}.wav'
            segs,_=model.transcribe(str(path),language='ar',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False,suppress_tokens=suppress)
            words=[{'text':w.word.strip(),'start':w.start,'end':w.end} for s in segs for w in (s.words or [])]
            text=' '.join(w['text'] for w in words);compact=re.sub(r'\s+','',norm(text));expected={3:[1964],9:[65,200],13:[1968]}[part]
            checks={}
            for value in expected:
                m=re.search(PATTERNS[value],compact)
                duplicate=bool(m and re.match(r'و?ستين',compact[m.end():])) if value in (1964,1968,65) else False
                checks[str(value)]={'matched_spoken_words':m.group() if m else None,'duplicated_suffix':duplicate,'passed':bool(m) and not duplicate}
            r={'part':part,'asr_model':size,'digit_tokens_suppressed':True,'initial_prompt_used':False,'transcript':text,'words':words,'checks':checks,'passed':all(c['passed'] for c in checks.values())}
            reports.append(r);print(json.dumps({k:v for k,v in r.items() if k!='words'},ensure_ascii=False),flush=True)
        del model
    (output/'number-word-review.json').write_text(json.dumps({'reports':reports,'all_passed':all(r['passed'] for r in reports)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
