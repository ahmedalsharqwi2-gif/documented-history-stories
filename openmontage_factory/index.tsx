import React,{useEffect,useState} from 'react';
import {AbsoluteFill,Audio,Composition,Img,Sequence,continueRender,delayRender,interpolate,registerRoot,staticFile,useCurrentFrame,useVideoConfig,Easing} from 'remotion';

type Scene={id:string;label:string;start:number;end:number;photo:string;creator:string;license:string;shot_type?:string};
type Props={title:string;source:{title:string;url:string;publisher:string};duration:number;scenes:Scene[];captions:{text:string;start:number;end:number}[]};
const clamp={extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const copper='#e1b37b',ivory='#fff8e8';
const Font=()=>{const [h]=useState(()=>delayRender('Load Arabic font'));useEffect(()=>{new FontFace('HistoryArabic',`url(${staticFile('arabic.ttf')})`).load().then(f=>{document.fonts.add(f);continueRender(h)}).catch(()=>continueRender(h));},[h]);return null};
const Shot:React.FC<{scene:Scene;index:number}>=({scene,index})=>{
 const frame=useCurrentFrame();const {fps}=useVideoConfig();const seconds=frame/fps;const duration=scene.end-scene.start;
 const wide=index%3===1;const turn=index%2===0?1:-1;
 return <AbsoluteFill style={{background:'#18201d',overflow:'hidden'}}>
   <Img src={staticFile(scene.photo)} style={{position:'absolute',width:'100%',height:'100%',objectFit:'cover',filter:wide?'blur(18px) brightness(.4)':'saturate(.72) contrast(1.06)',scale:interpolate(frame,[0,duration*fps],[1.04,1.16],clamp),translate:`${turn*interpolate(frame,[0,duration*fps],[-8,8],clamp)}px 0`}}/>
   {wide&&<Img src={staticFile(scene.photo)} style={{position:'absolute',top:305,left:32,width:656,height:650,objectFit:'contain',borderTop:`2px solid ${copper}`,borderBottom:`1px solid ${copper}`,scale:interpolate(frame,[0,duration*fps],[.97,1.03],clamp)}}/>}
   <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(8,19,18,.8) 0%,transparent 43%,rgba(8,19,18,.9) 100%)'}}/>
   <div dir="rtl" style={{position:'absolute',top:185,left:48,right:48,fontSize:index===0?45:37,lineHeight:1.8,color:ivory,opacity:interpolate(frame,[0,.45*fps],[0,1],clamp),translate:`0 ${interpolate(frame,[0,.7*fps],[28,0],{...clamp,easing:Easing.bezier(.22,1,.36,1)})}px`}}>{index===0?'حكاية موثّقة':scene.label}</div>
   {index===0&&<div dir="rtl" style={{position:'absolute',top:335,left:48,right:48,color:copper,fontSize:35,lineHeight:1.9}}>{scene.label}</div>}
   <div style={{position:'absolute',left:48,right:48,bottom:345,fontSize:12,lineHeight:1.6,fontFamily:'Arial',color:'#eee',textShadow:'0 1px 4px #000'}}>{scene.creator.slice(0,65)} · {scene.license}<br/>Wikimedia Commons · animated photograph</div>
   <div style={{position:'absolute',top:130,left:48,fontFamily:'Georgia',fontSize:20,color:copper}}>{String(index+1).padStart(2,'0')} / 08</div>
 </AbsoluteFill>
};
const Film:React.FC<Props>=(props)=>{
 const frame=useCurrentFrame();const {fps}=useVideoConfig();const time=frame/fps;
 const caption=props.captions.find(x=>time>=x.start&&time<x.end);
 return <AbsoluteFill style={{background:'#18201d',color:ivory,fontFamily:'HistoryArabic',overflow:'hidden'}}>
  <Font/>
  {props.scenes.map((s,i)=><Sequence key={s.id} from={Math.round(s.start*fps)} durationInFrames={Math.max(1,Math.round(s.end*fps)-Math.round(s.start*fps))} premountFor={fps}><Shot scene={s} index={i}/></Sequence>)}
  <div dir="rtl" style={{position:'absolute',top:65,left:48,right:48,display:'flex',justifyContent:'space-between',fontSize:16,zIndex:10}}><span style={{borderTop:`2px solid ${copper}`,paddingTop:10}}>قصص التاريخ الموثّق</span><span style={{border:'1px solid #ffffff66',padding:'7px 12px',fontSize:13}}>عينة إنتاج آلي</span></div>
  {caption&&<div dir="rtl" style={{position:'absolute',bottom:175,left:48,right:48,textAlign:'center',zIndex:20}}><span style={{display:'inline-block',background:'#071713ed',borderRight:`3px solid ${copper}`,padding:'14px 20px',fontSize:27,lineHeight:1.85}}>{caption.text}</span></div>}
  <div dir="rtl" style={{position:'absolute',bottom:118,left:48,right:48,fontSize:12,color:'#d2ddd7',zIndex:10}}>المصدر: {props.source.publisher} • الصور للتوضيح وليست تصويرًا للحدث</div>
  <div style={{position:'absolute',bottom:90,left:48,right:48,height:2,background:'#ffffff33',zIndex:15}}><div style={{height:2,width:`${Math.min(100,time/props.duration*100)}%`,background:copper}}/></div>
  <Audio src={staticFile('voice.wav')}/>
  <Audio src={staticFile('music.mp3')} loop volume={f=>.07*interpolate(f,[0,fps,(props.duration-2)*fps,props.duration*fps],[0,1,1,0],clamp)}/>
 </AbsoluteFill>
};
registerRoot(()=> <Composition id="AutomaticHistory" component={Film} width={720} height={1280} fps={30} durationInFrames={3000} calculateMetadata={({props})=>({durationInFrames:Math.ceil(props.duration*30)})} defaultProps={{title:'',source:{title:'',url:'',publisher:''},duration:100,scenes:[],captions:[]}}/>);
