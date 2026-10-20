import * as THREE from 'three';
import {Scene,type Frame} from './engine/scene';
import {Layer2D,clearRT,W,H} from './engine/gl';
import {ease,lerp,clamp,hash} from './engine/util';

type Beat={id:string;headline:string;kicker:string;kind:string;text:string;start:number;end:number};
const cream='#ecdfc3',gold='#d3ad6d',muted='#9c9588';
function txt(c:CanvasRenderingContext2D,s:string,x:number,y:number,size:number,color=cream,bold=false){
 c.save();c.font=`${bold?'700':'400'} ${size}px ${bold?'ArabicBold':'Arabic'}`;c.direction='rtl';c.textAlign='center';c.fillStyle=color;c.fillText(s,x,y);c.restore();
}
function path(c:CanvasRenderingContext2D,pts:number[][],color:string,width=3){c.beginPath();pts.forEach(([x,y],i)=>i?c.lineTo(x!,y!):c.moveTo(x!,y!));c.strokeStyle=color;c.lineWidth=width;c.stroke();}

export default class HistoryScene extends Scene{
 world=new THREE.Scene(); camera=new THREE.PerspectiveCamera(36,W/H,.1,100);
 stone=new THREE.Group();dust!:THREE.Points;overlay=new Layer2D();beats:Beat[]=[];
 async init(){
   const ep=await (await fetch('data/episode.json')).json();this.beats=ep.scenes;
   this.world.background=new THREE.Color('#0c1012');this.world.fog=new THREE.FogExp2('#0c1012',.025);
   this.world.add(new THREE.HemisphereLight('#d7e0d3','#1e1720',1.3));
   const key=new THREE.DirectionalLight('#f9d5a2',4.5);key.position.set(-3,5,4);this.world.add(key);
   const rim=new THREE.DirectionalLight('#84b3bc',2.5);rim.position.set(4,1,-2);this.world.add(rim);
   const spot=new THREE.PointLight('#e7ac61',15,12);spot.position.set(-2,2,2);this.world.add(spot);
   const shape=new THREE.Shape();shape.moveTo(-.91,-1.55);shape.lineTo(.94,-1.55);shape.lineTo(.98,1.25);shape.lineTo(.5,1.62);shape.lineTo(.18,1.49);shape.lineTo(-.23,1.7);shape.lineTo(-.82,1.4);shape.lineTo(-1,1.04);shape.closePath();
   const body=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:.27,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:.05,bevelThickness:.045}),new THREE.MeshStandardMaterial({color:'#303135',roughness:.94,metalness:.05}));
   this.stone.add(body);
   const cv=document.createElement('canvas');cv.width=768;cv.height=1280;const c=cv.getContext('2d')!;
   c.fillStyle='#494b4c';c.fillRect(0,0,768,1280);
   for(let j=0;j<35000;j++){
     const x=hash(j*3+1)*768,y=hash(j*3+2)*1280,v=Math.floor(45+hash(j*3+3)*80);
     c.fillStyle=`rgba(${v},${v},${v+2},.35)`;c.fillRect(x,y,1+hash(j)*3,1+hash(j+1)*3);
   }
   // Marks are a schematic reconstruction, not a transcription of the ancient text.
   for(let row=0;row<50;row++)for(let col=0;col<33;col++){
     const x=24+col*22,y=160+row*21+hash(row*40+col)*3;
     c.strokeStyle=`rgba(205,202,184,${.22+hash(row+col)*.2})`;c.lineWidth=1.3;
     c.beginPath();c.moveTo(x,y);c.lineTo(x+hash(col*13+row)*13,y-4);c.lineTo(x+10,y-9);c.stroke();
   }
   const tex=new THREE.CanvasTexture(cv);tex.colorSpace=THREE.SRGBColorSpace;
   const geo=new THREE.ShapeGeometry(shape);const pos=geo.attributes.position!;const uv=geo.attributes.uv!;
   for(let j=0;j<pos.count;j++)uv.setXY(j,(pos.getX(j)+1)/2,(pos.getY(j)+1.6)/3.35);
   const face=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({map:tex,bumpMap:tex,bumpScale:.018,roughness:.95}));face.position.z=.325;this.stone.add(face);
   this.stone.rotation.y=-.27;this.world.add(this.stone);
   const base=new THREE.Mesh(new THREE.CylinderGeometry(1.2,1.35,.14,64),new THREE.MeshStandardMaterial({color:'#232325',roughness:.7}));base.position.set(0,-1.74,0);this.world.add(base);
   const points=new Float32Array(800*3);
   for(let j=0;j<points.length;j++)points[j]=(hash(j+42)-.5)*12;
   const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(points,3));
   this.dust=new THREE.Points(pg,new THREE.PointsMaterial({color:'#d6bf91',size:.012,transparent:true,opacity:.45,depthWrite:false}));this.world.add(this.dust);
 }
 render(f:Frame,out:THREE.WebGLRenderTarget){
   const beat=this.beats.find(s=>f.t>=s.start&&f.t<s.end)??this.beats.at(-1)!;
   const p=clamp((f.t-beat.start)/(beat.end-beat.start));const kind=beat.kind;
   const reveal=ease.outCubic(clamp(p*6));
   const z=kind==='bands'?7.7:kind==='compare'?8.0:8.9;
   this.camera.position.set(Math.sin(f.t*.10)*.32,.18+Math.sin(f.t*.13)*.10,z-.25*p);
   this.camera.lookAt(0,.13,0);
   this.stone.rotation.y=-.24+Math.sin(f.t*.16)*.13;
   this.stone.position.x=kind==='map'?-1.05:kind==='compare'?-.5:0;
   this.stone.scale.setScalar(kind==='map'?.72:1);
   this.dust.rotation.y=f.t*.014;
   clearRT(this.ctx.renderer,out,[.007,.009,.012]);
   this.ctx.renderer.setRenderTarget(out);this.ctx.renderer.render(this.world,this.camera);
   const L=this.overlay;L.clear();const c=L.ctx;
   // Edge gradients allow the scene to remain full-frame behind the typography.
   let g=c.createLinearGradient(0,0,0,620);g.addColorStop(0,'rgba(9,13,15,1)');g.addColorStop(.65,'rgba(9,13,15,.88)');g.addColorStop(1,'rgba(9,13,15,0)');c.fillStyle=g;c.fillRect(0,0,W,620);
   g=c.createLinearGradient(0,1350,0,H);g.addColorStop(0,'rgba(9,13,15,0)');g.addColorStop(.4,'rgba(9,13,15,.9)');g.addColorStop(1,'rgba(9,13,15,1)');c.fillStyle=g;c.fillRect(0,1350,W,H-1350);
   txt(c,'حكايات من التاريخ',W/2,130,27,gold);path(c,[[460,170],[620,170]],gold,1);
   c.globalAlpha=reveal;txt(c,beat.headline,540,350+30*(1-reveal),kind==='timeline'?148:90,cream,true);txt(c,beat.kicker,540,430+20*(1-reveal),32,gold);c.globalAlpha=1;
   if(kind==='map')this.map(c,p);
   if(kind==='bands'||kind==='compare')this.bands(c,p,kind==='compare');
   if(kind==='timeline')this.timeline(c,p);
   // Whole Arabic runs preserve shaping and ligatures; timing is per spoken scene.
   const maxWidth=870;const words=beat.text.split(' ');const rows:string[]=[];let row='';
   c.font='38px Arabic';
   for(const word of words){let test=(row+' '+word).trim();if(c.measureText(test).width>maxWidth&&row){rows.push(row);row=word;}else row=test;}if(row)rows.push(row);
   rows.forEach((s,i)=>txt(c,s,540,1580+i*61,38));
   const width=880;path(c,[[100,1810],[980,1810]],'#39372f',2);path(c,[[100,1810],[100+width*f.t/f.end,1810]],gold,4);
   txt(c,'إعادة بناء توضيحية • المصادر مرفقة',540,1865,22,muted);
   this.ctx.comp.draw(this.ctx.renderer,L.upload(),out);
   return {hud:0,grain:.018,bloom:.12,ca:.12,halation:.03};
 }
 map(c:CanvasRenderingContext2D,p:number){
   const a=ease.inOutCubic(clamp(p*4));c.save();c.globalAlpha=a;
   // Schematic delta with both principal branches. The marker is geographically approximate.
   c.fillStyle='rgba(15,27,29,.94)';c.beginPath();c.roundRect(350,620,630,800,22);c.fill();
   const coast=[[410,790],[480,820],[560,845],[650,820],[740,790],[830,785],[935,815]];
   path(c,coast,'#a99c78',3);path(c,[[675,1300],[680,1130],[675,1030],[600,930],[510,820]],'#76a6b0',7);path(c,[[675,1030],[750,925],[830,790]],'#76a6b0',6);
   const x=510,y=820;c.strokeStyle=gold;c.lineWidth=3;c.beginPath();c.arc(x,y,16+13*(p*3%1),0,Math.PI*2);c.stroke();c.fillStyle=gold;c.beginPath();c.arc(x,y,9,0,Math.PI*2);c.fill();
   txt(c,'رشيد',530,755,42,gold,true);txt(c,'البحر المتوسط',680,680,29,'#8bb9c3');txt(c,'النيل',790,1210,30,'#8bb9c3');txt(c,'خريطة توضيحية للدلتا',665,1365,24,muted);c.restore();
 }
 bands(c:CanvasRenderingContext2D,p:number,compare:boolean){
   const names=['الهيروغليفية','الديموطيقية','اليونانية القديمة'];
   names.forEach((name,i)=>{
     const a=ease.outCubic(clamp((p-i*.12)*5));const y=690+i*235;
     c.save();c.globalAlpha=a;
     c.fillStyle=compare&&i===2?'rgba(90,71,40,.93)':'rgba(14,20,22,.94)';c.strokeStyle=gold;c.lineWidth=1.5;c.beginPath();c.roundRect(555+(1-a)*250,y,425,165,12);c.fill();c.stroke();
     txt(c,name,765+(1-a)*250,y+88,37,i===2?gold:cream,true);
     path(c,[[390,y+90],[530,y+90]],gold,2);c.beginPath();c.arc(390,y+90,5,0,Math.PI*2);c.fillStyle=gold;c.fill();c.restore();
   });
   if(compare){const a=clamp((p-.3)*3);c.save();c.globalAlpha=a;txt(c,'مقارنة النصوص',540,1400,40,gold);c.restore();}
 }
 timeline(c:CanvasRenderingContext2D,p:number){
   c.save();c.globalAlpha=.94;path(c,[[200,1370],[880,1370]],'#75694e',3);
   const x=200+680*ease.inOutCubic(p);path(c,[[200,1370],[x,1370]],gold,5);
   [200,880].forEach(x=>{c.fillStyle=gold;c.beginPath();c.arc(x,1370,7,0,Math.PI*2);c.fill();});
   txt(c,'١٧٩٩',200,1430,30);txt(c,'١٨٢٢',880,1430,30,gold);c.restore();
 }
 dispose(){this.world.traverse((o:any)=>{o.geometry?.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();}});}
}
