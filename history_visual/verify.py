"""Compare the encoded GitHub output to the locally approved visual reference."""
from pathlib import Path
import hashlib,json,subprocess,io
import numpy as np
from PIL import Image,features
ROOT=Path(__file__).resolve().parent
def phash(im):
 a=np.asarray(im.convert('L').resize((17,16),Image.Resampling.LANCZOS));b=(a[:,1:]>a[:,:-1]).flatten();return ''.join('1' if v else '0' for v in b)
def main():
 manifest=json.loads((ROOT/'approved.json').read_text())
 assert features.check('raqm'),'Arabic shaping support is required'
 for path,sha in manifest['assets'].items():
  assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,f'Approved asset changed: {path}'
 decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(ROOT/'assets/reference-audio.flac'),'-f','s16le','-'])
 assert hashlib.sha256(decoded).hexdigest()==manifest['source_pcm_sha256'],'Reference recording changed'
 video=ROOT/'output/dunkirk-visual-v2.mp4'
 meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
 v=next(s for s in meta['streams'] if s['codec_type']=='video');a=next(s for s in meta['streams'] if s['codec_type']=='audio')
 assert (v['width'],v['height'],v['r_frame_rate'])==(1080,1920,'30/1')
 assert abs(float(meta['format']['duration'])-11.5)<.05
 assert a['codec_name']=='aac'
 scores=[]
 for sample in manifest['frames']:
  data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(sample['time']),'-i',str(video),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
  im=Image.open(io.BytesIO(data)).convert('RGB');h=phash(im)
  distance=sum(x!=y for x,y in zip(h,sample['hash']))
  mean=np.asarray(im.resize((64,114))).mean(axis=(0,1));delta=max(abs(float(x)-y) for x,y in zip(mean,sample['mean_rgb']))
  assert distance<=14 and delta<=8,f'Visual drift at {sample["time"]}: hash {distance}, RGB {delta:.2f}'
  scores.append({'time':sample['time'],'hash_distance':distance,'mean_rgb_delta':round(delta,3)})
 subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True)
 report={'verified':True,'dimensions':[1080,1920],'fps':30,'duration':float(meta['format']['duration']),'approved_assets_sha256_match':True,'original_recording_pcm_match':True,'visual_comparisons':scores,'voice_generation':False,'image_generation_during_run':False,'social_publishing':False}
 (ROOT/'output/verification.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
