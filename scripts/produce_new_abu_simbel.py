"""Produce a brand-new, self-contained Abu Simbel documentary review, NEVER publish."""
import os,math,subprocess,urllib.request,wave,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from film_factory.voice import generate

OUT=Path('output/new_abu_simbel');OUT.mkdir(parents=True,exist_ok=True)
PARAS=[
'في جنوب مصر، على ضفة النيل، كان معبد أبو سمبل واقف في الصخر من أيام رمسيس التاني. لكن في الستينيات ظهر خطر جديد: المياه اللي كانت هتتجمع ورا السد العالي.',
'بحيرة ناصر كانت هترتفع وتغطي مواقع أثرية مهمة في النوبة. وكان لازم يبقى فيه حل يحمي المعبد، من غير ما نضيع تفاصيله أو مكانته التاريخية.',
'بمساعدة اليونسكو وخبراء من دول مختلفة، بدأ مشروع إنقاذ ضخم. العمال قطعوا أجزاء المعبد الصخرية لكتل، ورقموها بعناية، علشان يقدروا ينقلوها.',
'بعد كده الكتل اترفعت واتنقلت لمكان أعلى، وبعيد عن المياه. واتركبت من جديد فوق هيكل داعم، مع الحفاظ قدر الإمكان على شكل المعبد واتجاهه.',
'عملية الإنقاذ استمرت من سنة ألف تسعمية أربعة وستين لألف تسعمية تمانية وستتين. وفي النهاية، المعبد رجع يقف قدام الزوار، لكن فوق أرض أعلى من مكانه الأصلي.',
'قصة أبو سمبل مش مجرد نقل حجارة. دي حكاية تعاون عالمي لإنقاذ تراث عمره آلاف السنين، قبل ما تختفي معالمه تحت المياه.'
]
speech=' '.join(PARAS)
(OUT/'script.txt').write_text(speech,encoding='utf-8')
audio=generate(speech,str(OUT/'narration.wav'),'Natural clear Egyptian Arabic documentary narration. Pronounce أبو سمبل correctly as Abu Simbel, not Abu Zabal. Keep numbers clear. No extra speech.')
with wave.open(str(audio)) as w:dur=w.getnframes()/w.getframerate()
if dur<45 or dur>170:raise RuntimeError(f'Unexpected narration duration {dur}')
url='https://commons.wikimedia.org/wiki/Special:Redirect/file/Entrance_to_the_Great_Temple_of_Ramses_II_at_Abu_Simbel%2C_Egypt.jpg'
req=urllib.request.Request(url,headers={'User-Agent':'NeurofusionHistoricalDocumentary/1.0'})
with urllib.request.urlopen(req,timeout=60) as r:(OUT/'temple.jpg').write_bytes(r.read())
img=cv2.imread(str(OUT/'temple.jpg'))
if img is None:raise RuntimeError('Could not load source photograph')
H,W=960,540;rate=24;n=int(dur*rate)
im_h,im_w=img.shape[:2]
if im_w < 700:raise RuntimeError('Photo source resolution too low')
# Camera and lighting vary across the six narration chapters.
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font1=ImageFont.truetype(font,38);font2=ImageFont.truetype(font,20)
titles=['المعبد قبل الخطر','المياه تقترب','عملية الإنقاذ','إعادة التركيب','١٩٦٤ — ١٩٦٨','تراث نجا من الغرق']
subtitles=['جنوب مصر — النوبة','مشروع السد العالي','حجرًا حجرًا','فوق مستوى البحيرة','إنقاذ تاريخي','حكاية تعاون عالمي']
p=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(rate),'-i','-','-i',str(audio),'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-shortest',str(OUT/'abu-simbel-new-full.mp4')],stdin=subprocess.PIPE)
xx=np.broadcast_to(np.arange(W,dtype=np.float32)[None,:],(H,W))
yy=np.broadcast_to(np.arange(H,dtype=np.float32)[:,None],(H,W))
for i in range(n):
 t=i/rate;section=min(5,int(t/dur*6));progress=(t/(dur/6))%1
 scale=max(H/im_h,W/im_w)*(1.02+.09*progress)
 cropw=W/scale;croph=H/scale
 # Pan each section over another temple part; never leave original photo's boundaries.
 cx=im_w*(.50+.13*math.sin(section*1.42)+.03*math.cos(t*.14))
 cy=im_h*(.50+.07*math.cos(section*1.1))
 sx=np.clip(cx-cropw/2,0,im_w-cropw);sy=np.clip(cy-croph/2,0,im_h-croph)
 frame=cv2.remap(img,(sx+xx/scale).astype('float32'),(sy+yy/scale).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
 frame=frame.astype('float32')
 shade=(.74+.27*(1-((xx-W*.5)/(W*.75))**2)) *(.85+.16*math.sin(t*.14+1))
 frame*=shade[:,:,None]
 frame[:,:,2]=np.clip(frame[:,:,2]*1.10+9,0,255)
 frame=np.clip(frame,0,255).astype('uint8')
 canvas=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
 d=ImageDraw.Draw(canvas,'RGBA')
 d.rectangle((0,0,W,142),fill=(3,10,16,190))
 d.rectangle((0,805,W,H),fill=(3,10,16,211))
 # native RTL shaping in pillow RAQM; don't run bidi twice
 d.text((W//2,50),titles[section],font=font1,anchor='mt',direction='rtl',fill=(255,219,163,255))
 d.text((W//2,850),subtitles[section],font=font2,anchor='mt',direction='rtl',fill=(251,241,226,255))
 d.line((48,909,48+round((W-96)*t/dur),909),fill=(245,182,95,230),width=5)
 frame=cv2.cvtColor(np.array(canvas),cv2.COLOR_RGB2BGR)
 p.stdin.write(frame.tobytes())
p.stdin.close()
if p.wait()!=0:raise RuntimeError('Encoding failed')
subprocess.run(['ffmpeg','-v','error','-i',str(OUT/'abu-simbel-new-full.mp4'),'-f','null','-'],check=True)
(OUT/'manifest.json').write_text(json.dumps({'new_narration':True,'new_render':True,'duration':dur,'published':False,'source_url':url},ensure_ascii=False,indent=2))
