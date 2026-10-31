import * as THREE from 'three';

// Deterministic material detail: texture affects shading only, never authored geometry.
export function historySurface(kind='stone',size=128){
 const pixels=new Uint8Array(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const noise=((x*73856093^y*19349663)>>>0)%47;
  const grain=kind==='wood'?Math.sin(x*.18+Math.sin(y*.035)*2)*22:Math.sin(x*.71+y*.37)*8;
  const joint=kind==='stone'&&(y%32<2||(x+(Math.floor(y/32)%2)*32)%64<2)?-30:0;
  const value=Math.max(0,Math.min(255,168+noise+grain+joint));
  const offset=(y*size+x)*4;pixels[offset]=pixels[offset+1]=pixels[offset+2]=value;pixels[offset+3]=255;
 }
 const texture=new THREE.DataTexture(pixels,size,size,THREE.RGBAFormat);
 texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.repeat.set(2,2);
 texture.name='history-v2-'+kind;texture.magFilter=THREE.LinearFilter;texture.minFilter=THREE.LinearFilter;texture.needsUpdate=true;
 return texture;
}

export function installHistoryCinema({renderer,scene,camera,root}){
 const surfaces={stone:historySurface('stone'),wood:historySurface('wood')};
 const adapted=new Map();let shaded=0;
 root.traverse(object=>{
  if(!object.isMesh)return;
  object.castShadow=true;object.receiveShadow=true;
  const improve=material=>{
   if(!material.isMeshStandardMaterial||material.transparent||(material.emissiveIntensity>.5&&material.emissive?.getHex()>0))return material;
   if(adapted.has(material))return adapted.get(material);
   const copy=material.clone();
   const timber=material.color.r<.3&&material.color.r>material.color.b*1.8&&material.metalness<.2;
   if(timber){copy.bumpMap=surfaces.wood;copy.bumpScale=.018;copy.roughnessMap=surfaces.wood;}
   else if(material.roughness>=.65){copy.bumpMap=surfaces.stone;copy.bumpScale=.026;copy.roughnessMap=surfaces.stone;}
   copy.roughness=Math.max(.3,copy.roughness);adapted.set(material,copy);shaded++;
   return copy;
  };
  object.material=Array.isArray(object.material)?object.material.map(improve):improve(object.material);
 });
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 // Existing authored lights remain, but subdued to leave room for one bounded shadow pass.
 scene.traverse(object=>{if(object.isDirectionalLight)object.intensity*=.55;});
 const key=new THREE.DirectionalLight(0xffe4bd,2.5);key.name='history-v2-key';key.position.set(-4,6,5);key.castShadow=true;
 key.shadow.mapSize.set(1024,1024);Object.assign(key.shadow.camera,{left:-6,right:6,top:6,bottom:-5,near:.5,far:25});key.shadow.bias=-.0008;key.shadow.normalBias=.035;scene.add(key);
 const rim=new THREE.DirectionalLight(0xa5c9e8,.85);rim.name='history-v2-rim';rim.position.set(4,3,-5);scene.add(rim);
 const ground=new THREE.Mesh(new THREE.PlaneGeometry(100,100),new THREE.ShadowMaterial({opacity:.22}));
 ground.name='history-v2-ground-shadow';ground.rotation.x=-Math.PI/2;ground.position.y=-1.8;ground.receiveShadow=true;scene.add(ground);
 const target=new THREE.Vector3();
 return {materialCount:shaded,update({progress,index,story}){
  const p=THREE.MathUtils.clamp(progress,0,1),ease=p*p*(3-2*p);
  // A complete subject stays in frame; alternating arcs reveal volume without spinning labels.
  const architecture=story.visual_family==='architecture';
  const radius=architecture?14.4:13.8,arc=(index%2?-1:1)*(.13-.22*ease);
  camera.position.set(Math.sin(arc)*radius,1.15+.2*Math.sin(p*Math.PI),Math.cos(arc)*radius-.9*ease);
  target.set(0,architecture?.3:.4,0);camera.lookAt(target);
  ground.visible=architecture;
 },dispose(){for(const m of adapted.values())m.dispose();for(const t of Object.values(surfaces))t.dispose();key.shadow.map?.dispose();scene.remove(key,rim,ground);ground.geometry.dispose();ground.material.dispose();}};
}
