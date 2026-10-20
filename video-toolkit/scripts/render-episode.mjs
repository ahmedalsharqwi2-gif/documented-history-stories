import fs from 'node:fs/promises';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderMedia,renderStill} from '@remotion/renderer';
import {chromium} from 'playwright';
const root=path.resolve('..');
const props=JSON.parse(await fs.readFile(path.join(root,'episode-work/render.json'),'utf8'));
const serveUrl=await bundle({entryPoint:path.resolve('src/motion-episode.tsx'),publicDir:path.join(root,'episode-work/public')});
const options={serveUrl,id:'MotionEpisode',inputProps:props,browserExecutable:chromium.executablePath(),chromiumOptions:{gl:'swangle'}};
const composition=await selectComposition(options);
await fs.mkdir(path.join(root,'output'),{recursive:true});
for(let i=0;i<props.scenes.length;i++){
 const frame=Math.min(composition.durationInFrames-1,Math.round((props.scenes[i].start+Math.min(3,(props.scenes[i].end-props.scenes[i].start)*.5))*30));
 await renderStill({...options,composition,frame,imageFormat:'jpeg',jpegQuality:80,output:path.join(root,'output','scene-'+i+'.jpg')});
}
let last=-1;
await renderMedia({...options,composition,codec:'h264',crf:18,pixelFormat:'yuv420p',outputLocation:path.join(root,'episode-work/silent.mp4'),concurrency:1,disableSharedMemoryCapture:true,disallowParallelEncoding:true,imageFormat:'png',logLevel:'verbose',onProgress:({progress,renderedFrames,encodedFrames})=>{const p=Math.floor(progress*10);if(p!==last){console.log('Rendering',p*10+'%',{renderedFrames,encodedFrames});last=p;}}});
await fs.writeFile(path.join(root,'output/render-settings.json'),JSON.stringify({width:1080,height:1920,fps:30,frames:composition.durationInFrames,codec:'h264',crf:18,sharedMemoryCapture:false,parallelEncoding:false},null,2));
