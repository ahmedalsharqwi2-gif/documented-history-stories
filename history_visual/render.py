"""Photo-based motion study, using an unchanged excerpt of the supplied audio.

Images are generated illustrative reconstructions, not archival evidence.
Cartography is rendered from Natural Earth, not generated as an image.
"""
from pathlib import Path
from functools import lru_cache
import math, json, subprocess, hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from shapely.geometry import shape,box
ROOT=Path(__file__).resolve().parent
W,H,FPS,DURATION=1080,1920,30,11.5
CREAM='#f5edda';GOLD='#e4bd77';CYAN='#8bcecf'
def ease(v):v=max(0,min(1,v));return v*v*(3-2*v)
def lerp(a,b,t):return a+(b-a)*t
@lru_cache(None)
def font(n,bold=False):return ImageFont.truetype(str(ROOT/'assets'/('NotoSansArabic-Bold.ttf' if bold else 'NotoSansArabic-Regular.ttf')),n)
@lru_cache(200)
def label(s,size=48,col=CREAM,bold=False):
 f=font(size,bold);b=f.getbbox(s,direction='rtl');im=Image.new('RGBA',(b[2]-b[0]+12,b[3]-b[1]+14));d=ImageDraw.Draw(im)
 d.text((6-b[0],7-b[1]),s,font=f,fill=col,direction='rtl');return im
def txt(im,s,x,y,size=48,col=CREAM,bold=False,alpha=1):
 st=label(s,size,col,bold)
 if alpha<1:st=st.copy();st.putalpha(st.getchannel('A').point(lambda a:round(a*max(0,alpha))))
 im.alpha_composite(st,(round(x-st.width/2),round(y)))
def scaled_background(asset,zoom=1,x=0,y=0):
 sw,sh=asset.size;scale=max(W/sw,H/sh)*zoom
 nw,nh=round(sw*scale),round(sh*scale)
 # Transform the source directly: no intermediate full-frame resize/crop jitter.
 return asset.transform((W,H),Image.Transform.AFFINE,(1/scale,0,(nw-W)/2/scale+x/scale,0,1/scale,(nh-H)/2/scale+y/scale),Image.Resampling.BICUBIC)
def paste_alpha(im,asset,pos,size,opacity=1):
 st=asset.resize(size,Image.Resampling.LANCZOS)
 if opacity<1:st=st.copy();st.putalpha(st.getchannel('A').point(lambda a:round(a*opacity)))
 im.alpha_composite(st,(round(pos[0]),round(pos[1])))
def polyline(d,pts,fill,width=3,progress=1):
 if len(pts)<2:return
 spans=[math.dist(a,b) for a,b in zip(pts,pts[1:])];remaining=sum(spans)*max(0,min(1,progress))
 for a,b,length in zip(pts,pts[1:],spans):
  if remaining<=0:break
  k=min(1,remaining/length) if length else 1
  d.line([a,(lerp(a[0],b[0],k),lerp(a[1],b[1],k))],fill=fill,width=width);remaining-=length

BEACH=Image.open(ROOT/'assets/beach.png').convert('RGBA');ROOM=Image.open(ROOT/'assets/warroom.png').convert('RGBA')
SOLDIER=Image.open(ROOT/'assets/soldier.png').convert('RGBA');SOLDIER=SOLDIER.crop(SOLDIER.getchannel('A').getbbox())

def geo(lon,lat):
 # Mercator projection; north is up. Coordinates approximate the regional locator.
 mx=lon;my=math.degrees(math.log(math.tan(math.pi/4+math.radians(lat)/2)))
 return (120+(mx+5.7)*64,1190-(my-56.6)*64)
def map_layer():
 im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im)
 d.rounded_rectangle((75,600,1005,1405),radius=22,fill=(6,22,32,231),outline=(192,167,119,120),width=2)
 for x in range(110,1000,70):d.line((x,625,x,1370),fill=(130,179,185,22))
 for y in range(625,1380,70):d.line((100,y,980,y),fill=(130,179,185,22))
 data=json.loads((ROOT/'assets/countries.geojson').read_text());extent=box(-6,48.2,8,54.8)
 for feature in data['features']:
  if feature['properties'].get('ADMIN') not in ['United Kingdom','France','Belgium','Netherlands','Germany','Ireland']:continue
  g=shape(feature['geometry']).intersection(extent)
  if g.is_empty:continue
  geoms=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
  for p in geoms:
   if p.geom_type!='Polygon':continue
   points=[geo(x,y) for x,y in p.exterior.coords]
   d.polygon(points,fill=(86,105,102,240),outline=(183,183,153,220),width=2)
 txt(im,'بريطانيا',370,695,34,CREAM);txt(im,'فرنسا',645,1195,34,CREAM);txt(im,'بحر المانش',440,1000,30,CYAN)
 txt(im,'موقع تقريبي • خريطة توضيحية',540,1350,22,'#a8b5ac')
 return im
MAP=map_layer()

def beach_shot(t):
 im=scaled_background(BEACH,1.04+t*.007,-15+t*3,15-t*2)
 fg_h=1110+int(t*9);fg_w=round(SOLDIER.width*fg_h/SOLDIER.height)
 paste_alpha(im,SOLDIER,(-110-t*8,805-t*3),(fg_w,fg_h),.94)
 return im
def room_shot(t):
 u=t-2.85;im=scaled_background(ROOM,1.07+u*.004,10-u*2,-8)
 layer=MAP.copy();d=ImageDraw.Draw(layer)
 city=geo(2.376,51.034);cx,cy=city
 radius=19+12*((u*.7)%1);d.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=GOLD,width=3)
 d.ellipse((cx-7,cy-7,cx+7,cy+7),fill=GOLD)
 # Locator lines, not military front lines or claimed battle routes.
 polyline(d,[(cx+2,cy+5),(cx+70,cy+105),(cx+205,cy+105)],GOLD,3,ease(u/.8))
 txt(layer,'دنكرِك',cx+140,cy+125,44,GOLD,True)
 txt(layer,'قوات الحلفاء',540,500,52,CREAM,True)
 im.alpha_composite(layer)
 return im
def tension_shot(t):
 u=t-7.55;im=scaled_background(BEACH,1.18+u*.013,45-u*7,-55)
 # A distant focus marker animates toward the port; no invented exact troop positions.
 d=ImageDraw.Draw(im);cx,cy=750,870
 r=70+10*math.sin(u*1.3)
 d.arc((cx-r,cy-r,cx+r,cy+r),-40,160,fill=GOLD,width=3)
 d.arc((cx-r,cy-r,cx+r,cy+r),190,320,fill=GOLD,width=3)
 polyline(d,[(cx+50,cy+50),(940,1130),(940,1200)],GOLD,3,ease(u/.8))
 # End phrase is the actual spoken text, not a numeric countdown.
 if t>9.6:txt(im,'والوقت بيخلص',540,490,78,CREAM,True,ease((t-9.6)/.4))
 return im

CAPS=[(0,2.94,'في مايو سنة ألف وتسعمية وأربعين،'),(2.94,7.74,'جيوش الحلفاء اتحاصرت على شاطئ دنكرك، في شمال فرنسا.'),(7.74,9.58,'الجيش الألماني كان بيتقدم،'),(9.58,11.5,'والوقت كان بيخلص.')]
def frame(t):
 if t<2.85:im=beach_shot(t)
 elif t<3.2:im=Image.blend(beach_shot(t),room_shot(t),ease((t-2.85)/.35))
 elif t<7.55:im=room_shot(t)
 elif t<7.9:im=Image.blend(room_shot(t),tension_shot(t),ease((t-7.55)/.35))
 else:im=tension_shot(t)
 # Soft readability gradients; imagery remains full-screen.
 shade=Image.new('RGBA',(W,H));a=np.zeros((H,W),np.uint8)
 a[:600,:]=np.linspace(165,0,600,dtype=np.uint8)[:,None]
 a[1430:,:]=np.linspace(0,230,H-1430,dtype=np.uint8)[:,None]
 shade.putalpha(Image.fromarray(a));im.alpha_composite(shade)
 txt(im,'حكايات التاريخ',540,95,27,GOLD)
 if t<2.85:
  alpha=min(ease(t/.45),ease((2.85-t)/.3))
  txt(im,'دنكرِك',540,335,136,CREAM,True,alpha)
  txt(im,'مايو ١٩٤٠',540,525,44,GOLD,False,alpha)
 elif t<7.8:txt(im,'الحصار',540,230,76,CREAM,True,ease((t-2.85)/.45))
 elif t<9.6:txt(im,'الجيش الألماني بيتقدم',540,320,58,CREAM,True,ease((t-7.55)/.4))
 cap=next((x for start,end,x in CAPS if start<=t<end),'')
 words=cap.split();rows=[];row=''
 for word in words:
  v=(row+' '+word).strip()
  if label(v,47,CREAM,True).width>915 and row:rows.append(row);row=word
  else:row=v
 if row:rows.append(row)
 for i,s in enumerate(rows):
  st=label(s,47,CREAM,True);x=(W-st.width)//2;y=1580+i*77
  d=ImageDraw.Draw(im);d.rounded_rectangle((x-17,y-10,x+st.width+17,y+st.height+10),radius=10,fill=(5,10,15,180));im.alpha_composite(st,(x,y))
 d=ImageDraw.Draw(im);d.line((90,1815,990,1815),fill=(240,232,216,90),width=2);d.line((90,1815,90+900*t/DURATION,1815),fill=GOLD,width=4)
 txt(im,'صور توضيحية مولّدة • الصوت من المرجع',540,1860,22,'#d0c5ad')
 return im.convert('RGB')

def main():
 out=ROOT/'output';out.mkdir(exist_ok=True)
 for t in [1.3,4.6,8.8,10.6]:frame(t).save(out/f'frame-{t}.jpg',quality=93)
 cmd=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',str(out/'picture.mp4')]
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
 for n in range(round(DURATION*FPS)):
  p.stdin.write(frame(n/FPS).tobytes())
  if n%90==0:print(f'{n}/{round(DURATION*FPS)} frames',flush=True)
 p.stdin.close()
 if p.wait():raise RuntimeError('Video encoding failed')
 source=ROOT/'assets/reference-audio.flac'
 subprocess.run(['ffmpeg','-y','-v','error','-i',str(out/'picture.mp4'),'-i',str(source),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-t',str(DURATION),'-movflags','+faststart',str(out/'dunkirk-visual-v2.mp4')],check=True)
 (out/'production.json').write_text(json.dumps({'duration':DURATION,'fps':FPS,'width':W,'height':H,'audio':'Unchanged first 11.5 seconds of user-supplied 135999.mp4, re-encoded for final AAC. No new TTS, speed change or pitch change.','images':'Generated illustrative reconstructions using built-in image generation, not archival photos.','cartography':'Natural Earth 1:50m admin0, regional locator only; no claimed battle-front geometry.','limits':'This is a visual/audio reference comparison. Matching the same voice for new text is not solved by reusing this excerpt.'},indent=2))
if __name__ == '__main__':
    raise SystemExit('Retired production path. Run: python -m motion_factory.produce history')
