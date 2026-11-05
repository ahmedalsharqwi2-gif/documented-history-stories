import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {proceduralDirector} from './procedural_story.js';
const spec=motion=>({environment:'molecular_water',camera_start:[0,0,10],camera_end:[0,0,10],objects:[{kind:'egypt_temple',position:[0,0,0],scale:[1,1,1],rotation:[0,0,0],motion,color:'#fff8e8'}]});
const build=motion=>proceduralDirector(new THREE.Scene(),{profile:'history',locked_template_version:1,visual_plan:{world:'procedural_story'},scenes:Array.from({length:9},()=>spec(motion))});
test('Abu Simbel schematic uses four seated colossi and no Greek pediment or column geometry',()=>{
 const d=build('none'),o=d.stages[0].objects[0].object;let heads=0,columns=0,pediments=0;
 o.traverse(n=>{heads+=n.geometry?.type==='SphereGeometry';columns+=n.geometry?.type==='CylinderGeometry';pediments+=n.geometry?.type==='ConeGeometry';});
 assert.equal(heads,4);assert.equal(columns,0);assert.equal(pediments,0);assert.equal(o.userData.templeBlocks.length,24);
});
test('Dismantling separates facade pieces rather than translating the entire temple; assembly restores them',()=>{
 const d=build('split'),o=d.stages[0].objects[0].object;d.update(0,0,0);const first=o.userData.templeBlocks[0],origin=first.position.clone();d.update(0,1,5);
 assert.ok(first.position.distanceTo(origin)>.1);assert.deepEqual(o.position.toArray(),[0,0,0]);
 const a=build('assemble'),assembled=a.stages[0].objects[0].object;a.update(0,0,0);assert.ok(assembled.userData.templeBlocks[0].position.distanceTo(assembled.userData.templeBlocks[0].userData.home)>.1);a.update(0,1,5);
 for(const b of assembled.userData.templeBlocks)assert.ok(b.position.distanceTo(b.userData.home)<1e-9);
});
