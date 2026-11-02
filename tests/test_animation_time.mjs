import assert from 'node:assert/strict';
import * as THREE from '../professional_motion/node_modules/three/build/three.module.js';
import {loopPhase} from '../professional_motion/animation_time.mjs';
const curve=new THREE.CatmullRomCurve3([new THREE.Vector3(),new THREE.Vector3(1,1,0),new THREE.Vector3(2,0,0),new THREE.Vector3(3,1,0)]);
assert.throws(()=>curve.getPoint(-1e-14));
for(const value of [-1e-14,0,1-1e-14,1,7.3,-7.3]){
 const phase=loopPhase(value);assert(phase>=0&&phase<1);assert(curve.getPoint(phase).toArray().every(Number.isFinite));
}
assert.throws(()=>loopPhase(NaN));
