import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'out/history-pilot.mp4'
data=json.loads((ROOT/'data/episode.json').read_text())
meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out)]))
v=next(s for s in meta['streams'] if s['codec_type']=='video');a=next(s for s in meta['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'])==(1080,1920)
assert abs(float(meta['format']['duration'])-data['duration'])<.25
assert v['r_frame_rate']=='30/1';assert a['codec_name']=='aac'
subprocess.run(['ffmpeg','-v','error','-i',str(out),'-f','null','-'],check=True)
(ROOT/'out/verification.json').write_text(json.dumps({'verified':True,'width':1080,'height':1920,'duration':meta['format']['duration'],'engine':'Adapted supplied Motion as Code / Three.js','publishing':False,'requested_voice':data['voice'],'actual_voice_providers':list(set(s['voice_provider'] for s in data['scenes'])),'timing':data['timing']},indent=2))
print('PASS: encoded video, audio, dimensions, duration, full decode')
