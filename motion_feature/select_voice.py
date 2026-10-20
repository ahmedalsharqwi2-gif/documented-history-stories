from pathlib import Path
import json,os
root=Path(__file__).resolve().parent.parent
rows=[]
for p in (root/'audition-input').rglob('sample.audit.json'):
    a=json.loads(p.read_text());rows.append({'speaker':a['speaker'],'numbers':a['number_checks'],'passed':a['all_numbers_passed'],'transcript':a['transcript'],'duration':a['duration']})
valid=[r for r in rows if r['passed']]
if not valid:raise RuntimeError('No trial voice passed all three independent number checks; do not produce a long episode with known bad numbers')
# Trial another built-in male voice when its independent number reading passes.
order=['Youssef','Ahmed','Mohammed'];chosen=sorted(valid,key=lambda r:order.index(r['speaker']))[0]
out={'speaker':chosen['speaker'],'reason':'Passed independent ASR checks for 1964, 65 and 200; alternative trial voice, subjective timbre requires user review','auditions':rows,'production_voice_config_changed':False}
(root/'feature-work/voice-selection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('speaker='+chosen['speaker']+'\n')
