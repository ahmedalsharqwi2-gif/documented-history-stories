from pathlib import Path
import subprocess,sys,json,shutil
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from motion_feature.assemble import alignment
part=int(sys.argv[1]);speaker=sys.argv[2];wav=ROOT/f'feature-voices/part-{part:02d}.wav'
scene=json.loads((ROOT/'feature-work/plan.json').read_text())['scenes'][part]
for attempt in range(2):
    subprocess.run([str(Path(__import__('os').environ['VOICETUT_PYTHON'])),'motion_feature/tts_worker.py','scene','--speaker',speaker,'--part',str(part),'--seed',str(20261020+attempt*1000)],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'motion_feature/audit_voice.py',str(wav)],check=True,cwd=ROOT)
    audit=json.loads(wav.with_suffix('.audit.json').read_text())
    try:
        if not audit['all_numbers_passed']:raise ValueError('Independent ASR did not confirm critical numbers')
        _,metrics=alignment(scene,audit,audit['duration'])
        print('Scene voice passed',part,metrics['coverage'],flush=True);break
    except ValueError as e:
        if attempt:raise
        failed=ROOT/'feature-voices/rejected';failed.mkdir(exist_ok=True)
        for p in wav.parent.glob(wav.stem+'.*'):shutil.copy2(p,failed/p.name)
        print('Regenerating scene after failed pronunciation/timing audit:',e,flush=True)
