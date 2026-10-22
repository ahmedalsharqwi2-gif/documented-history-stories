import os,math,random,subprocess,urllib.request
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
random.seed(11)
PHOTO='https://commons.wikimedia.org/wiki/Special:Redirect/file/Entrance_to_the_Great_Temple_of_Ramses_II_at_Abu_Simbel%2C_Egypt.jpg'
p='abu-simbel-cc0.jpg'
if not os.path.exists(p):
 req=urllib.request.Request(PHOTO,headers={'User-Agent':'Mozilla/5.0 (MotionKit historical documentary prototype)'})
 with urllib.request.urlopen(req,timeout=50) as r:open(p,'wb').write(r.read())
im=cv2.imread(p)
if im is None:raise RuntimeError('CC0 photo failed to decode')
W,H=540,960;fps=24;frames=9*fps
# Real photographic source with cinematic reframing; preserve sculptures and temple facade.
# Poster is created from image itself, not a sketch or 3D-reconstruction claim.
base=cv2.resize(im,(1500,1064),interpolation=cv2.INTER_CUBIC)
bh,bw=base.shape[:2]
# use wide crop into portrait by slowly trucking from left colossal to central doorway
y,x=np.mgrid[0:H,0:W].astype(np.float32)
xx=x/W; yy=y/H
rng=np.random.default_rng(9)
dust=np.column_stack([rng.uniform(0,W,105),rng.uniform(0,H,105),rng.uniform(.3,1.5,105)])
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
shape=lambda s:s
f1=ImageFont.truetype(font,40); f2=ImageFont.truetype(font,22)
pr=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-c:v','libx264','-crf','21','-preset','veryfast','-pix_fmt','yuv420p','abu-simbel-cinematic-proof.mp4'],stdin=subprocess.PIPE)
for j in range(frames):
 t=j/fps
 # soft zoom and camera track; separate sky/foreground tones create depth impression
 zoom=1.0+t*.037
 scale=.87*zoom
 crop_w=W/scale;crop_h=H/scale
 cx=750 + math.sin(t*.20)*75
 cy=540-48*math.sin(t*.21)
 mapx=(cx-crop_w/2)+xx*crop_w
 mapy=(cy-crop_h/2)+yy*crop_h
 frame=cv2.remap(base,mapx,mapy,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT)
 # warm sandstone mids / dark teal shadows, gradual sun beam
 arr=frame.astype(np.float32)/255
 lumin=.2126*arr[:,:,2]+.7152*arr[:,:,1]+.0722*arr[:,:,0]
 arr[:,:,0]=np.clip(arr[:,:,0]*.73+.035,0,1)
 arr[:,:,1]=np.clip(arr[:,:,1]*.87+.017,0,1)
 arr[:,:,2]=np.clip(arr[:,:,2]*1.08+.065,0,1)
 beam=np.exp(-((xx-(.13+t*.026))/.39)**2)*(.09+.05*math.sin(t*.25))
 arr[:,:,2]+=beam*.30;arr[:,:,1]+=beam*.20
 # cinema vignette and 2.39 style readability
 vig=np.maximum(.45,1-.40*((xx-.5)**2*3+(yy-.48)**2*2))
 arr*=vig[:,:,None]
 frame=np.uint8(np.clip(arr,0,1)*255)
 overlay=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).convert('RGBA')
 d=ImageDraw.Draw(overlay,'RGBA')
 for i,(dx,dy,spd) in enumerate(dust):
  px=float((dx+math.sin(i)*t*spd*3)%W);py=float((dy-t*spd*6)%H)
  rad=1 if i%4 else 2
  d.ellipse((px-rad,py-rad,px+rad,py+rad),fill=(255,213,150,35+i%60))
 fade=min(1,t/1.1,(9-t)/1.4);fade=max(0,fade)
 # frame treatments, restrained title card rather than decorative lines across subject
 d.rectangle((0,0,W,160),fill=(3,11,19,int(130*fade)))
 d.rectangle((0,770,W,H),fill=(3,11,19,int(168*fade)))
 d.text((W/2,46),shape('أبو سمبل'),font=f1,anchor='mt',direction='rtl',fill=(247,213,161,int(255*fade)),stroke_width=1,stroke_fill=(15,18,20,int(180*fade)))
 d.text((W/2,828),shape('حين انتقل المعبد لينجو من الغرق'),font=f2,anchor='mt',direction='rtl',fill=(240,242,230,int(255*fade)))
 d.text((W/2,892),'ABU SIMBEL  •  1964—1968',font=f2,anchor='mt',fill=(231,180,113,int(220*fade)))
 frame=cv2.cvtColor(np.array(overlay.convert('RGB')),cv2.COLOR_RGB2BGR)
 pr.stdin.write(frame.tobytes())
pr.stdin.close()
if pr.wait()!=0:raise SystemExit('video encoding failed')
cv2.imwrite('abu-simbel-proof-preview.jpg',frame)
