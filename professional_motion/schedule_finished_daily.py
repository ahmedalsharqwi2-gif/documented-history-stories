"""Schedule the already rendered, hash-pinned current daily film; never regenerate or post immediately."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from .schedule_window import daily_window
from .publisher import publish
from .editorial import registry
MEDIA='70008938c3de5bb21710778feeb283b94e7e0e94'
EVIDENCE='9958396aa6f628ae93f22095875c0c617c9ce446'
VIDEO='b76bc2a6e2037514fd533a0500af833b6c16fe2f1950bf469c2609a481dcfefc'
def main():
 for branch in ['codex/professional-video-41053670613','codex/professional-review-run-41053670613']:subprocess.run(['git','fetch','origin','refs/heads/'+branch],check=True)
 def blob(ref,name):return subprocess.check_output(['git','show',ref+':'+name])
 out=Path('professional_motion/output');delivery=Path('professional_motion/delivery');out.mkdir(exist_ok=True);delivery.mkdir(exist_ok=True)
 data=blob(MEDIA,'review-1080p.mp4')
 if hashlib.sha256(data).hexdigest()!=VIDEO:raise ValueError('Completed movie checksum changed')
 report=json.loads(blob(MEDIA,'verification.json'));story=blob(EVIDENCE,'professional_motion/delivery/story.json')
 if report['story_sha256']!=hashlib.sha256(story).hexdigest() or not report['visual_gate']['passed'] or not report['audio_tail']['audio_tail_checked']:raise ValueError('Completed media evidence mismatch')
 _,due,slot=daily_window(datetime.now(timezone.utc))
 if slot!='daily-2026-10-30' or report['profile']!='history':raise ValueError('Wrong day/profile; never recycle a film')
 episode=next(r for r in registry()['episodes'] if r.get('slot')==slot)
 if episode.get('video_sha256')!=VIDEO:raise ValueError('Durable registry does not match the finished episode')
 (out/'professional-review.mp4').write_bytes(data);(out/'verification.json').write_text(json.dumps(report));(delivery/'story.json').write_bytes(story)
 subprocess.run(['ffmpeg','-v','error','-i',str(out/'professional-review.mp4'),'-f','null','-'],check=True)
 publish('history',slot,due.isoformat().replace('+00:00','Z'))
if __name__=='__main__':main()
