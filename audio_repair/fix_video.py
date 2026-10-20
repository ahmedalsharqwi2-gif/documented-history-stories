from pathlib import Path
import sys,json,subprocess,hashlib,shutil
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from audio_repair.delivery import mix_audio,verify_tail,probe,run
work=ROOT/'feature-work';duration=float(probe(work/'narration.wav')['format']['duration']);out=ROOT/'audio-fixed';out.mkdir(exist_ok=True)
source=ROOT/'polished-source/abu-simbel-gemini.mp4';mixed=ROOT/'audio-prepared/mix.wav'
voice=mix_audio(work/'narration.wav',ROOT/'assets/music/history_archive_reflection.mp3',work/'effects.wav',duration,mixed)
video=out/'abu-simbel-audio-fixed.mp4';run(['-i',source,'-i',mixed,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-t',duration,'-movflags','+faststart',video])
report=verify_tail(video,voice,duration)
subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True)
report.update(video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),fix='Normalize voice/music to full-length 48 kHz PCM before sidechain mixing; reject duration drift and missing ending words',pronunciation_changed=False,full_decode_passed=True,voice='Original Youssef narration retained; this fixes tail truncation only')
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
run(['-sseof','-18','-i',video,'-vn','-codec:a','libmp3lame','-q:a','2',out/'last-18-seconds.mp3']);print(json.dumps(report,ensure_ascii=False,indent=2))
