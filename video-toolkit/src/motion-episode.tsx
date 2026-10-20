import React,{useEffect,useState} from 'react';
import {AbsoluteFill,Composition,registerRoot,useCurrentFrame,useVideoConfig,interpolate,Easing,staticFile,delayRender,continueRender} from 'remotion';
const C={bg:'#08191f',paper:'#f0e9db',gold:'#e9b875',muted:'#7d9a9c',teal:'#35666b'};
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const ease=(t:number,a=0,b=1)=>interpolate(t,[a,b],[0,1],{...clamp,easing:Easing.bezier(.2,.8,.2,1)});
const arab=(n:number)=>Math.round(n).toLocaleString('ar-EG');
function Ship({x,y,s=1,large=false,rotation=0,color=C.paper}:{x:number,y:number,s?:number,large?:boolean,rotation?:number,color?:string}){
 return <g transform={'translate('+x+' '+y+') rotate('+rotation+') scale('+s+')'} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round">
  <path d={large?'M-105 12 L-80 44 H65 L105 12 Z':'M-52 5 L-32 28 H33 L55 5 Z'} fill={color} fillOpacity=".13"/>
  {large?<><path d="M-60 10 V-15 H43 V10 M-35-15 V-38 H-8 V-15 M12-15 V-30 H33 V-15 M-12-38 V-68"/><path d="M-12-68 L15-53 H-12" fill={C.gold}/></>:<><path d="M-20 5 V-18 H18 V5 M0-18 V-49 M0-48 L35-5 H0" fill={color} fillOpacity=".08"/></>}
  <path d="M-65 57 Q-45 46-25 57 T15 57 T55 57" opacity=".35"/>
 </g>
}
function Person({x,y,opacity=1}:{x:number,y:number,opacity?:number}){return <g transform={'translate('+x+' '+y+')'} fill={C.paper} opacity={opacity}><circle cy="-13" r="5"/><path d="M-7-4H7L10 16H4V31H-4V16H-10Z"/></g>}
function Mark({x,y,label,t}:{x:number,y:number,label:string,t:number}){
 return <g transform={'translate('+x+' '+y+')'}><circle r={10+((t*.6)%1)*35} stroke={C.gold} fill="none" opacity={1-((t*.6)%1)}/><circle r="7" fill={C.gold}/><text x="22" y="-18" fill={C.paper} fontSize="34" fontFamily="Arabic" direction="rtl" textAnchor="end">{label}</text></g>
}
function MapScene({t,paths,route=false}:{t:number,paths:any[],route?:boolean}){
 const routeP=ease(t,.7,3.6);const drift=Math.sin(t*.22)*5;
 return <svg width="1080" height="900" viewBox="0 0 1080 900" style={{position:'absolute',top:350,left:0}}>
  <defs><pattern id="sea" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M0 60H60V0" fill="none" stroke={C.muted} strokeOpacity=".09"/></pattern><clipPath id="mapclip"><rect x="55" y="5" width="970" height="850" rx="24"/></clipPath></defs>
  <g clipPath="url(#mapclip)"><rect width="1080" height="900" fill="url(#sea)"/><g transform={'translate('+drift+' 0)'}>
   {paths.map((p,i)=><path key={i} d={p.d} fill={p.name==='United Kingdom'?'#1d4148':'#243d40'} stroke="#668587" strokeWidth="1.5"/>)}
   <text x="150" y="240" fill={C.muted} fontSize="40" fontFamily="Arabic">بريطانيا</text>
   <text x="690" y="780" fill={C.muted} fontSize="40" fontFamily="Arabic">فرنسا</text>
   <text x="185" y="665" fill={C.muted} fontSize="26" letterSpacing="6" transform="rotate(-15 185 665)">ENGLISH CHANNEL</text>
   <path d="M701 546 Q655 390 542 525" fill="none" stroke={C.gold} strokeWidth={route?5:3} strokeDasharray="260" strokeDashoffset={260*(1-routeP)}/>
   <path d="M701 546 Q655 390 542 525" fill="none" stroke={C.gold} strokeOpacity=".14" strokeWidth="25" opacity={routeP}/>
   {route&&[0,1,2].map(i=>{const p=(t*.12+i*.3)%1;const x=(1-p)*(1-p)*701+2*(1-p)*p*655+p*p*542;const y=(1-p)*(1-p)*546+2*(1-p)*p*390+p*p*525;return <Ship key={i} x={x} y={y} s={.35} rotation={-30}/>;})}
   <Mark x={701} y={546} label="دنكرك" t={t}/><Mark x={542} y={525} label="دوفر" t={t+.5}/>
  </g></g>
  <text x="80" y="884" fontSize="20" fill={C.muted} fontFamily="Arabic">خريطة توضيحية · المسارات رمزية</text>
 </svg>
}
function ShoreScene({t,transfer=4}:{t:number,transfer?:number}){
 const move=ease(t,transfer,transfer+2.4);return <svg width="1080" height="900" viewBox="0 0 1080 900" style={{position:'absolute',top:350}}>
  <defs><linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={C.teal} stopOpacity=".35"/><stop offset="1" stopColor={C.bg}/></linearGradient></defs>
  <path d="M70 615 L300 615 Q360 615 410 675 L1000 790 V855 H70Z" fill="#6c624a" opacity=".35"/>
  <path d="M310 565H1010V850H650L410 675Z" fill="url(#water)"/>
  {[0,1,2,3].map(i=><path key={i} d={'M'+(330+Math.sin(t+i)*12)+' '+(575+i*54)+' Q500 '+(550+i*54)+' 700 '+(575+i*54)+' T1010 '+(575+i*54)} fill="none" stroke={C.muted} strokeOpacity={.3-i*.045} strokeWidth="2"/>)}
  {Array.from({length:15},(_,i)=><Person key={i} x={100+(i%5)*38} y={440+Math.floor(i/5)*62} opacity={.25+.75*ease(t,i*.055,i*.055+.7)}/>)}
  <Ship x={445+move*180} y={530+Math.sin(t*1.4)*4} s={1.12}/>
  <Ship x={880} y={525+Math.sin(t)*3} s={1.1} large/>
  <path d="M485 365H740" fill="none" stroke={C.gold} strokeDasharray="6 10" strokeWidth="3" strokeDashoffset={-t*35}/>
  <path d="M724 354L741 365L724 376" fill="none" stroke={C.gold} strokeWidth="3"/>
  <text x="275" y="320" textAnchor="middle" fontFamily="Arabic" fill={C.paper} fontSize="35">الشاطئ</text>
  <text x="525" y="730" textAnchor="middle" fontFamily="Arabic" fill={C.gold} fontSize="34">القوارب الصغيرة</text>
  <text x="867" y="345" textAnchor="middle" fontFamily="Arabic" fill={C.paper} fontSize="34">السفن الكبيرة</text>
  <text x="540" y="845" textAnchor="middle" fontFamily="Arabic" fill={C.muted} fontSize="25">نقل الجنود من الشاطئ إلى السفن</text>
 </svg>
}
function FleetScene({t,timeline=3}:{t:number,timeline?:number}){
 const p=ease(t,timeline,timeline+3);
 return <svg width="1080" height="900" viewBox="0 0 1080 900" style={{position:'absolute',top:350}}>
  <circle cx="540" cy="410" r="260" fill="none" stroke={C.muted} strokeOpacity=".15" strokeWidth="1"/>
  <circle cx="540" cy="410" r="185" fill="none" stroke={C.muted} strokeOpacity=".1" strokeDasharray="3 12"/>
  {[-1,1].map((a,i)=><g key={i} opacity={ease(t,i*.4,.9+i*.4)}><path d={'M'+(540+a*280)+' 290 Q'+(540+a*210)+' 540 540 580'} stroke={C.gold} strokeWidth="2" strokeDasharray="400" strokeDashoffset={400*(1-p)} fill="none"/><Ship x={540+a*260} y={300+Math.sin(t+i)*6} s={1.3}/></g>)}
  <Ship x={540} y={535+Math.sin(t)*4} large s={1.7}/>
  <text x="280" y="190" fill={C.paper} fontFamily="Arabic" textAnchor="middle" fontSize="33">قوارب مدنية</text>
  <text x="800" y="190" fill={C.paper} fontFamily="Arabic" textAnchor="middle" fontSize="33">قوارب صيد ويخوت</text>
  <text x="540" y="690" fill={C.gold} fontFamily="Arabic" textAnchor="middle" fontSize="38">جنب البحرية</text>
  <path d="M160 790H920" stroke={C.muted} strokeWidth="2" opacity=".5"/>
  <path d="M160 790H920" stroke={C.gold} strokeWidth="5" strokeDasharray="760" strokeDashoffset={760*(1-p)}/>
  <circle cx={160+760*p} cy="790" r="8" fill={C.gold}/>
  <text x="160" y="852" fontSize="30" fill={C.paper} fontFamily="Arabic">أواخر مايو</text><text x="920" y="852" textAnchor="end" fontSize="30" fill={C.paper} fontFamily="Arabic">٤ يونيو ١٩٤٠</text>
 </svg>
}
function RescueScene({t,countAt=.3}:{t:number,countAt?:number}){
 const p=ease(t,countAt,countAt+2.3);return <div style={{position:'absolute',top:430,width:'100%',textAlign:'center'}}>
  <div style={{fontSize:31,color:C.muted,letterSpacing:4}}>DUNKIRK / OPERATION DYNAMO</div>
  <div style={{fontSize:54,color:C.paper,marginTop:48}}>أكثر من</div>
  <div style={{fontSize:202,lineHeight:1.4,color:C.gold,fontWeight:700,fontVariantNumeric:'tabular-nums',textShadow:'0 0 70px #e9b87520'}}>{arab(338000*p)}</div>
  <div style={{fontSize:48,color:C.paper,marginTop:-5}}>جندي تم إجلاؤهم</div>
  <svg width="880" height="200" viewBox="0 0 880 240" style={{marginTop:25}}>
   {Array.from({length:126},(_,i)=><circle key={i} cx={20+(i%21)*42} cy={25+Math.floor(i/21)*36} r="4" fill={i/126<p?C.gold:C.muted} opacity={i/126<p?.8:.12}/>)}
  </svg>
  <div style={{position:'absolute',top:845,left:0,right:0,fontSize:20,color:C.muted}}>تمثيل بصري للعدد · وليس عدًّا فرديًّا</div>
 </div>
}
function Words({captions,t}:{captions:any[],t:number}){
 const c=captions.find(c=>t>=c.start&&t<c.end);if(!c)return null;
 return <div dir="rtl" style={{position:'absolute',left:80,right:80,top:1455,display:'flex',flexWrap:'wrap',justifyContent:'center',alignContent:'center',gap:'4px 15px',minHeight:210,fontSize:61,lineHeight:1.65,fontWeight:700}}>
  {c.words.map((w:any,i:number)=>{const a=ease(t,w.start-.03,w.start+.17);const active=t>=w.start&&t<w.end;return <span key={i} style={{display:'inline-block',whiteSpace:'nowrap',opacity:a,transform:'translateY('+((1-a)*22)+'px)',color:active?C.gold:C.paper,textShadow:active?'0 0 30px #e9b87550':'none'}}>{w.text}</span>;})}
 </div>
}
function Episode(props:any){
 const frame=useCurrentFrame();const {fps,durationInFrames}=useVideoConfig();const t=frame/fps;
 const [handle]=useState(()=>delayRender('Load bundled Arabic font'));
 useEffect(()=>{const font=new FontFace('Arabic','url('+staticFile('NotoSansArabic-Bold.ttf')+')');font.load().then(f=>{document.fonts.add(f);continueRender(handle);}).catch(e=>{throw e;});},[handle]);
 const idx=Math.max(0,props.scenes.findIndex((s:any)=>t>=s.start&&t<s.end));
 const s=props.scenes[idx];const local=t-s.start;
 const allWords=props.captions.flatMap((c:any)=>c.words);
 const cue=(term:string,fallback:number)=>{const w=allWords.find((w:any)=>w.start>=s.start&&w.start<s.end&&w.text.includes(term));return w?w.start-s.start:fallback;};const intro=ease(local,0,.65);const outro=ease(s.end-t,0,.32);
 return <AbsoluteFill style={{background:C.bg,color:C.paper,fontFamily:'Arabic',overflow:'hidden'}}>
  <AbsoluteFill style={{background:'radial-gradient(ellipse at 65% 38%,#20404780,transparent 65%)'}}/>
  <svg width="1080" height="1920" style={{position:'absolute',opacity:.1}}><defs><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".75" numOctaves="3" stitchTiles="stitch"/></filter></defs><rect width="100%" height="100%" filter="url(#grain)" opacity=".25"/></svg>
  <div style={{position:'absolute',left:75,right:75,top:76,display:'flex',justifyContent:'space-between',fontSize:23,color:C.muted,letterSpacing:3}}>
   <span>HISTORY / 1940</span><span dir="rtl">التاريخ الموثّق</span>
  </div>
  <div style={{position:'absolute',top:145,left:80,width:70,height:4,background:C.gold}}/>
  <div style={{opacity:intro*outro,transform:'translateY('+((1-intro)*25)+'px)'}}>
   <div dir="rtl" style={{position:'absolute',top:195,left:90,right:90,fontSize:idx===3?67:72,lineHeight:1.65,textAlign:'right'}}>{s.title}</div>
   {idx===0?<MapScene t={local} paths={props.mapPaths}/>:idx===1?<ShoreScene t={local} transfer={cue("تنقل",4)}/>:idx===2?<FleetScene t={local} timeline={cue("الإجلاء",3)}/>:<RescueScene t={local} countAt={cue("تلتمية",.3)}/>}
  </div>
  <div style={{position:'absolute',top:1320,left:80,right:80,height:1,background:'#7d9a9c40'}}/>
  <div style={{position:'absolute',top:1352,left:80,color:C.gold,fontSize:22,letterSpacing:3}}>{String(idx+1).padStart(2,'0')} / 04</div>
  <div dir="rtl" style={{position:'absolute',top:1345,right:80,color:C.muted,fontSize:24}}>دنكرك · عملية الإجلاء</div>
  <Words captions={props.captions} t={t}/>
  <div style={{position:'absolute',left:80,right:80,bottom:110,color:C.muted,fontSize:20,display:'flex',justifyContent:'space-between'}}><span>MOTION DOCUMENTARY</span><span dir="rtl">رسوم توضيحية · صوت مولّد</span></div>
  <div style={{position:'absolute',left:80,right:80,bottom:78,height:3,background:'#ffffff12'}}><div style={{height:3,width:(frame/(durationInFrames-1)*100)+'%',background:C.gold}}/></div>
  <AbsoluteFill style={{background:C.bg,opacity:1-ease(t,0,.3)+ease(t,props.duration-.45,props.duration)}}/>
 </AbsoluteFill>
}
registerRoot(()=> <Composition id="MotionEpisode" component={Episode} width={1080} height={1920} fps={30} durationInFrames={30} defaultProps={{duration:1,scenes:[{start:0,end:1,title:''}],captions:[],mapPaths:[]}} calculateMetadata={({props})=>({durationInFrames:Math.ceil(props.duration*30)})}/>);
