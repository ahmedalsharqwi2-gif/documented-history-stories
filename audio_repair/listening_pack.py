"""Small labeled listening videos: original references and fresh tests stay separate."""
from pathlib import Path
import json,subprocess,math,sys,shutil
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from audio_repair.delivery import probe
out=ROOT/'listening-pack';out.mkdir(exist_ok=True)
def build(paths,target,reference=False):
 clips=[];index=[];cursor=0
 for i,p in enumerate(paths):
  duration=float(probe(p)['format']['duration']);frames=math.ceil(duration*10);length=frames/10
  name=p.stem if reference else p.parent.parent.name
  cond='Library reference' if reference else p.parent.name
  label=name+' / '+cond;card=out/f'{target.stem}-{i:02d}.mp4'
  filters=f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{name}':fontcolor=0xefbe77:fontsize=62:x=(w-tw)/2:y=500,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{cond}':fontcolor=white:fontsize=30:x=(w-tw)/2:y=610"
  subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=0x091b20:s=720x1280:r=10','-i',str(p),'-vf',filters,'-af',f'aresample=48000,apad=whole_dur={length},atrim=duration={length}','-t',str(length),'-c:v','libx264','-preset','ultrafast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','1','-b:a','160k',str(card)],check=True)
  clips.append(card);index.append({'label':label,'start':round(cursor,2),'duration':duration,'source':str(p.relative_to(ROOT)),'new_generation':not reference});cursor+=length
 listing=out/(target.stem+'.txt');listing.write_text('\n'.join("file '"+str(p)+"'" for p in clips))
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(target)],check=True)
 for p in clips:p.unlink()
 listing.unlink();target.with_suffix('.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
 return index
fresh=sorted((ROOT/'voice-comparisons/generated').glob('*/*/sample.mp3'))
refs=sorted((ROOT/'voice-comparisons/catalogue').glob('*.mp3'))
if not fresh:raise ValueError('No real generated samples')
build(fresh,out/'new-common-text-voices.mp4')
if refs:build(refs,out/'original-library-reference-voices.mp4',True)
shutil.copytree(ROOT/'voice-comparisons/generated',out/'generated',dirs_exist_ok=True)
if (ROOT/'voice-comparisons/alternative').exists():shutil.copytree(ROOT/'voice-comparisons/alternative',out/'alternative',dirs_exist_ok=True)
print(json.dumps({'new_tests':len(fresh),'library_references':len(refs),'mixed_reference_with_fresh_generation':False},ensure_ascii=False))
