import type {Lyrics} from './engine/lyrics';
import type {AudioData} from './engine/audio';
export function makeTimeline(_ly:Lyrics,au:AudioData){return [{id:'rosetta',start:0,end:au.duration,load:()=>import('./history'),post:{hud:0,grain:.018,ca:.1,bloom:.12,halation:.03,vignette:.24}}];}
