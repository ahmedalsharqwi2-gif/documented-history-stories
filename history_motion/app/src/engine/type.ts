// Arabic shaping is performed by the browser on complete text runs.
// Replaces the kit's Latin-only per-glyph typography registry for this pilot.
export const F={mono:(_w=400,_i=false)=>'Arabic',archivo:(_a=100,_b=700)=>'ArabicBold',serif:(_w=400,_i=false)=>'Arabic'};
export const font=(family:string,size:number)=>`${size}px "${family}"`;
export const smart=(s:string)=>s;
export async function loadFonts(){
  for(const [name,file] of [['Arabic','NotoSansArabic-Regular.ttf'],['ArabicBold','NotoSansArabic-Bold.ttf']]){
    const f=new FontFace(name!,`url(fonts/${file})`);await f.load();document.fonts.add(f);
  }
  await document.fonts.ready;
}
