import * as THREE from 'three';
import {historyPlan,HISTORY_WORLDS} from './director_catalog.js';
const smooth=p=>{p=Math.max(0,Math.min(1,p));return p*p*(3-2*p);};
export function createHistoryDirector(scene,story){
 const plan=historyPlan(story),root=new THREE.Group();root.name='history-topic-'+plan.world;scene.add(root);
 const materials={stone:new THREE.MeshStandardMaterial({color:0xc0a27d,roughness:.94}),iron:new THREE.MeshStandardMaterial({color:0x394a51,metalness:.7,roughness:.4}),sand:new THREE.MeshStandardMaterial({color:0xba9b6f,roughness:1}),grass:new THREE.MeshStandardMaterial({color:0x4c6d48,roughness:1}),water:new THREE.MeshStandardMaterial({color:0x3998ac,roughness:.25,metalness:.2,transparent:true,opacity:.76}),marker:new THREE.MeshBasicMaterial({color:0xf0d883}),road:new THREE.MeshStandardMaterial({color:0x8b816b,roughness:1})};
 const mesh=(group,geometry,material,x=0,y=0,z=0)=>{const m=new THREE.Mesh(geometry,material);m.position.set(x,y,z);group.add(m);return m;};
 const box=(g,w,h,d,mat,x=0,y=0,z=0)=>mesh(g,new THREE.BoxGeometry(w,h,d),mat,x,y,z);
 const stages=[],animations=[];
 const group=name=>{const g=new THREE.Group();g.name=name;root.add(g);return g;};
 function floor(g,arena=false){box(g,15,.2,12,arena?materials.sand:materials.grass,0,-1.7,0);if(!arena){for(const side of [-1,1]){const hill=mesh(g,new THREE.SphereGeometry(3,16,8),materials.grass,side*5,-1.2,-2);hill.scale.set(1,.55,1.3);}box(g,1.4,.06,12,materials.water,-1.6,-1.56,0);}}
 function arch(g,x,y,r=.43){
  const a=mesh(g,new THREE.TorusGeometry(r,.11,5,18,Math.PI),materials.stone,x,y,0);a.name='source-supported-arch';
  box(g,.22,.65,.45,materials.stone,x-r,y-.32,0);box(g,.22,.65,.45,materials.stone,x+r,y-.32,0);
 }
 function bridge(g,tiers){
  const b=new THREE.Group();g.add(b);b.name='aqueduct-exact-'+tiers+'-tiers';
  for(let level=0;level<tiers;level++){const tier=new THREE.Group();tier.name='tier-'+(level+1);b.add(tier);for(let n=0;n<6;n++)arch(tier,(n-2.5)*.9,level*.88-1);box(tier,5.8,.14,.55,materials.stone,0,level*.88-1.08,0);}
  const top=tiers*.88-1.1;box(b,5.9,.14,.7,materials.stone,0,top,0);box(b,5.8,.09,.36,materials.water,0,top+.12,0);return b;
 }
 function arena(g,tiers,cutaway=false){
  const b=new THREE.Group();g.add(b);b.name='arena-exact-'+tiers+'-tiers';
  for(let level=0;level<tiers;level++){const tier=new THREE.Group();tier.name='tier-'+(level+1);b.add(tier);for(let n=0;n<24;n++){
   if(cutaway&&n>4&&n<11)continue;
   const a=n/24*Math.PI*2;const pier=box(tier,.22,.7,.28,materials.stone,Math.cos(a)*3,level*.8-.9,Math.sin(a)*2.1);pier.rotation.y=-a;
   const beam=box(tier,.73,.16,.3,materials.stone,Math.cos(a+.13)*3,level*.8-.49,Math.sin(a+.13)*2.1);beam.rotation.y=-a;
   const vault=mesh(tier,new THREE.TorusGeometry(.34,.085,5,12,Math.PI),materials.stone,Math.cos(a+.13)*3,level*.8-.85,Math.sin(a+.13)*2.1);vault.rotation.y=Math.PI/2-a-.13;vault.name='arena_round_arch';
  }}
  for(let level=0;level<5;level++){const ring=mesh(b,new THREE.RingGeometry(1.1+level*.28,1.38+level*.28,48),materials.stone,0,-1.18+level*.1,0);ring.rotation.x=-Math.PI/2;ring.scale.y=.72;}
  return b;
 }
 function trough(g,section=false){
  const b=new THREE.Group();g.add(b);b.name='cast-iron-illustrative-trough-section';
  box(b,6,.18,1.1,materials.iron,0,.1,0);box(b,6,.6,.13,materials.iron,0,.45,-.57);
  if(!section)box(b,6,.6,.13,materials.iron,0,.45,.57);
  box(b,5.9,.07,.95,materials.water,0,.42,0);box(b,6,.15,.7,materials.road,0,.17,1);
  box(b,.72,1.7,.92,materials.stone,0,-.85,0);
  for(let row=0;row<5;row++)for(let col=0;col<2;col++){const offset=row%2?.12:0;const slab=box(b,.32,.3,.028,materials.stone,-.19+col*.38+offset,-1.5+row*.32,.475);slab.material=materials.stone.clone();slab.material.color.offsetHSL(0,0,(row+col)%2?.035:-.035);}
  for(let panel=0;panel<8;panel++){const x=-2.65+panel*.75;box(b,.022,.55,.018,materials.road,x,.44,.645);for(const y of [.22,.65])mesh(b,new THREE.SphereGeometry(.025,6,4),materials.iron,x,y,.667);box(b,.022,.55,.018,materials.road,x,.44,-.645);}

  for(let n=0;n<10;n++){box(b,.045,.04,.04,materials.marker,-2.7+n*.6,.59,-.48);}
  return b;
 }
 for(let sequenceIndex=0;sequenceIndex<8;sequenceIndex++){
  const beat=plan.scenes[sequenceIndex],i=HISTORY_WORLDS[plan.world].settings.indexOf(beat.setting),g=group(beat.setting);stages.push(g);const moves=[];animations.push(moves);
  const isArena=plan.world==='arena_complex',isCanal=plan.world==='canal_trough';
  floor(g,isArena);
  const tiers=story.visual_contract.tier_count;
  if(i===1||i===6){
   box(g,4,.25,2.3,materials.road,0,-.5,0);
   const detail=box(g,isCanal?2.6:1.9,isCanal?.15:1.1,1.2,isCanal?materials.iron:materials.stone,0,.2,0);detail.rotation.y=.25;
   for(let n=0;n<7;n++)box(g,.035,isCanal?.18:.75,.035,materials.marker,-.75+n*.25,.2,.62);
   moves.push(p=>detail.rotation.y=.25+smooth(p)*.65);
  }else if(isArena){
   const structure=arena(g,tiers,i===3);if(i===2){structure.visible=false;for(const side of [-1,1]){box(g,.35,2.4,5.5,materials.stone,side*1.2,-.1,-.5);}box(g,2.7,.2,5.5,materials.stone,0,1.2,-.5);}
   if(i===4){structure.visible=false;arch(g,0,-.1,1);const load=box(g,.24,.5,.24,materials.marker,0,1.3,0);moves.push(p=>load.position.y=1.3-.45*smooth(p));}
   if(i===5){for(let n=0;n<14;n++){const dot=mesh(g,new THREE.SphereGeometry(.065,6,4),materials.marker);moves.push(p=>{const a=n/14*Math.PI*2;const r=3.8-2.7*smooth(p);dot.position.set(Math.cos(a)*r,-1,Math.sin(a)*r*.7);});}}
  }else if(isCanal){
   const structure=trough(g,i===4);if(i===2){structure.visible=false;box(g,1,2.7,1.3,materials.stone,0,-.25,0);box(g,2.1,.2,1.5,materials.iron,0,1.2,0);}
   if(i===3){const join=box(g,2,.16,1.1,materials.iron,0,.1,0);moves.push(p=>join.position.x=4*(1-smooth(p)));}
   for(let n=0;n<14;n++){const dot=mesh(g,new THREE.SphereGeometry(.045,6,4),materials.marker);moves.push(p=>dot.position.set(-2.8+((p*5+n*.45)%5.6),.49,(n%3-1)*.22));}
  }else{
   const structure=bridge(g,tiers);if(i===2){structure.visible=false;box(g,1,2.5,.9,materials.stone,0,-.2,0);}
   if(i===3){structure.visible=false;arch(g,0,-.1,1);const key=box(g,.3,.35,.45,materials.stone,0,1.4,0);moves.push(p=>key.position.y=1.7-.65*smooth(p));}
   if(i===4){structure.visible=false;box(g,5,.2,1,materials.stone,0,.1,0);box(g,5,.6,.15,materials.stone,0,.4,-.5);box(g,4.9,.08,.8,materials.water,0,.45,0);}
   if(i===5||i===4){for(let n=0;n<14;n++){const dot=mesh(g,new THREE.SphereGeometry(.05,6,4),materials.marker);moves.push(p=>dot.position.set(-2.6+((p*5+n*.4)%5.2),i===4?.52:tiers*.88-.91,0));}}
  }
 }
 const views={wide_establishing:[5,3.5,8],macro_detail:[2,1.3,4],low_angle:[2,.3,5],lateral_close:[5,2.1,5],section_push:[4,3.5,5],tracking:[4,2.3,5],inspection_close:[1.8,1.4,3.7],interior_orbit:[3.3,3.5,4.5],corridor_tracking:[0,.3,4],overhead:[.1,7,1],pullback:[5,4,8]};
 return {root,plan,stages,update(index,p,time,camera){
  stages.forEach((stage,i)=>stage.visible=i===index);animations[index].forEach(fn=>fn(p));
  const beat=plan.scenes[index],view=views[beat.shot];const q=smooth(p);
  camera.position.set(view[0]+Math.sin(q*Math.PI)*.65,view[1],view[2]-(beat.shot==='pullback'?-1:1)*q*.8);camera.lookAt(0,plan.world==='arena_complex'?-.25:0,0);
  if(scene.fog){scene.fog.color.setHex(plan.world==='arena_complex'?0x786047:0x789aab);scene.fog.density=.025;}
  return {world:plan.world,setting:beat.setting,action:beat.action,shot:beat.shot};
 }};
}
