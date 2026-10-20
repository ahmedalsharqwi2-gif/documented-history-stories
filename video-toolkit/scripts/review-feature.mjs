import fs from 'node:fs/promises';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderStill} from '@remotion/renderer';
import {chromium} from 'playwright';
const root=path.resolve('..'),plan=JSON.parse(await fs.readFile(path.join(root,'feature-work/plan.json'),'utf8'));
const serveUrl=await bundle({entryPoint:path.resolve('src/abu-simbel-feature.tsx'),publicDir:path.join(root,'feature-work/public')});
await fs.mkdir(path.join(root,'feature-review'),{recursive:true});
for(let i=0;i<plan.scenes.length;i++){
 const scene=plan.scenes[i],words=scene.display_text.split(/\s+/).slice(0,5).map((text,k)=>({text,start:k*.4,end:(k+1)*.4}));
 const inputProps={frames:300,index:i,scene,captions:[{start:0,end:10,words}]};
 const options={serveUrl,id:'AbuSimbelFeature',inputProps,browserExecutable:chromium.executablePath(),chromiumOptions:{gl:'swangle'}};
 const composition=await selectComposition(options);
 await renderStill({...options,composition,frame:135,imageFormat:'jpeg',jpegQuality:80,output:path.join(root,'feature-review',`scene-${String(i).padStart(2,'0')}.jpg`)});
 console.log('Reviewed still',i,scene.visual_type);
}
