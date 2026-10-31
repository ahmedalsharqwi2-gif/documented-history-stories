import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../professional_motion/node_modules/three/build/three.module.js';
import {historySurface,installHistoryCinema} from '../professional_motion/cinema_v2.js';
import {channelStage} from '../professional_motion/channels.js';

test('surface shading is deterministic, bounded, and differs between timber and stone',()=>{
 const first=historySurface(),again=historySurface(),wood=historySurface('wood');
 assert.deepEqual(first.image.data,again.image.data);assert.notDeepEqual(first.image.data,wood.image.data);
 assert.equal(first.image.width,128);assert.equal(first.image.height,128);
});

test('cinema preserves sourced two-tier aqueduct geometry and uses bounded shadow resources',()=>{
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(40,1080/1920,.1,100),channel=channelStage(scene);
 const story={visual_family:'architecture',variant:'aqueduct',visual_contract:{focus:'aqueduct',tier_count:2,allowed_modes:['hero']},scenes:Array.from({length:8},()=>({visual_mode:'hero'}))};
 channel.update(story,0,0,0,0);
 const geometry=()=>{const records=[];channel.root.traverse(o=>{if(o.isMesh)records.push([o.uuid,o.geometry.uuid,o.geometry.attributes.position.count,Array.from(o.geometry.attributes.position.array)]);});return records;};
 const before=geometry(),renderer={shadowMap:{enabled:false}},cinema=installHistoryCinema({renderer,scene,camera,root:channel.root});
 assert.deepEqual(geometry(),before);assert.ok(cinema.materialCount>0);assert.equal(renderer.shadowMap.enabled,true);
 const surfaces=new Set();channel.root.traverse(o=>{if(o.isMesh&&o.material.bumpMap)surfaces.add(o.material.bumpMap.name);});assert.ok(surfaces.has('history-v2-stone'));assert.ok(surfaces.has('history-v2-wood'));
 const bridge=channel.root.getObjectByName('aqueduct');assert.equal(bridge.children.filter(o=>o.userData.tier!==undefined&&o.visible).length,2);
 cinema.update({progress:0,index:0,story});const start=camera.position.clone();
 cinema.update({progress:1,index:0,story});assert.ok(camera.position.distanceTo(start)>.5);
 assert.ok(camera.position.z>12);const key=scene.getObjectByName('history-v2-key');assert.equal(key.shadow.mapSize.width,1024);
 assert.deepEqual(geometry(),before);cinema.dispose();assert.equal(scene.getObjectByName('history-v2-key'),undefined);
});
