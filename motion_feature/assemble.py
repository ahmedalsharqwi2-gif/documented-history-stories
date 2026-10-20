"""Audited scene timing, frame-exact assembly and delivery verification."""
from pathlib import Path
import argparse,json,math,wave,shutil,subprocess,hashlib,re,sys
from difflib import SequenceMatcher
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from motion_feature.audit_voice import norm
from motion_episode.produce import synth_effects,probe

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def alignment(scene,audit,duration):
    actual=[];numbers={'1964':'ألف تسعمية أربعة وستين','1968':'ألف تسعمية تمانية وستين','65':'خمسة وستين','200':'ميتين'}
    for w in audit['words']:
        text=numbers.get(norm(w['text']),w['text']).split();span=max(.01,w['end']-w['start'])/len(text)
        actual.extend({'text':x,'start':w['start']+i*span,'end':w['start']+(i+1)*span} for i,x in enumerate(text))
    expected=scene['display_text'].split();a=[norm(x) for x in expected];b=[norm(w['text']) for w in actual]
    matcher=SequenceMatcher(None,a,b,autojunk=False);anchors={}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):anchors[block.a+k]=actual[block.b+k]
    exact=len(anchors)/len(expected);near=[]
    for tag,a0,a1,b0,b1 in matcher.get_opcodes():
        if tag!='replace' or a1-a0!=b1-b0:continue
        for i,j in zip(range(a0,a1),range(b0,b1)):
            ratio=SequenceMatcher(None,a[i],b[j],autojunk=False).ratio()
            if min(len(a[i]),len(b[j]))>=4 and ratio>=.85:
                anchors[i]=actual[j];near.append({'expected':expected[i],'recognized':actual[j]['text']})
    coverage=len(anchors)/len(expected)
    if coverage<.72:raise ValueError(f"Scene {scene['id']} speech mismatch, coverage {coverage:.3f}: {audit['transcript']}")
    timed=[None]*len(expected)
    for i,w in anchors.items():timed[i]={'start':max(0,w['start']),'end':min(duration,w['end'])}
    i=0
    while i<len(timed):
        if timed[i] is not None:i+=1;continue
        start=i
        while i<len(timed) and timed[i] is None:i+=1
        left=timed[start-1]['end'] if start else 0;right=timed[i]['start'] if i<len(timed) else duration
        right=max(left,right);step=(right-left)/max(1,i-start)
        for k in range(start,i):timed[k]={'start':left+(k-start)*step,'end':left+(k-start+1)*step}
    caps=[]
    for i in range(0,len(expected),5):
        words=[{'text':expected[k],**timed[k]} for k in range(i,min(len(expected),i+5))]
        caps.append({'start':words[0]['start'],'end':max(words[0]['start']+.02,words[-1]['end']),'words':words})
    caps[0]['start']=0;caps[-1]['end']=duration
    return caps,{'coverage':coverage,'exact_coverage':exact,'near_spellings':near,'transcript':audit['transcript'],'unmatched_words_interpolated':True}

def prepare():
    plan=json.loads((ROOT/'feature-work/plan.json').read_text());public=ROOT/'feature-work/public';public.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'photo_motion/assets/NotoSansArabic-Bold.ttf',public/'NotoSansArabic-Bold.ttf')
    out=ROOT/'feature-work/parts';out.mkdir(exist_ok=True);pcm=[];metrics=[];total=0;spoken=0;rate=24000
    reports=[];speaker=None
    for i,scene in enumerate(plan['scenes']):
        stem=ROOT/f'feature-voices/part-{i:02d}';wav=stem.with_suffix('.wav')
        audit=json.loads(stem.with_suffix('.audit.json').read_text());voice=json.loads(stem.with_suffix('.voice.json').read_text())
        if not audit['all_numbers_passed']:raise ValueError(f"Critical number pronunciation not verified in scene {i}: {audit['number_checks']}")
        if speaker is None:speaker=voice['speaker']
        if speaker!=voice['speaker']:raise ValueError('Mixed speakers are prohibited')
        with wave.open(str(wav)) as f:
            if f.getnchannels()!=1 or f.getsampwidth()!=2:raise ValueError('Expected mono PCM16')
            if i and rate!=f.getframerate():raise ValueError('Sample rates differ')
            rate=f.getframerate();samples=f.getnframes();payload=f.readframes(samples)
        duration=samples/rate;caps,m=alignment(scene,audit,duration)
        frames=math.ceil((duration+.16)*30);padded=round(frames/30*rate)
        pcm.append(payload+bytes((padded-samples)*2));spoken+=duration
        props={'index':i,'frames':frames,'scene':scene,'captions':caps}
        (out/f'part-{i:02d}.json').write_text(json.dumps(props,ensure_ascii=False))
        metrics.append({'part':i,'start':total/30,'frames':frames,'duration':duration,**m});total+=frames
        reports.append({'voice':voice,'audit':{k:v for k,v in audit.items() if k!='words'}})
    if spoken<125:raise ValueError(f'Actual narration only {spoken:.2f} sec; expand Gemini content, never pad to fake length')
    with wave.open(str(ROOT/'feature-work/narration.wav'),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(b''.join(pcm))
    events=[m['start'] for m in metrics]+[m['start']+3 for m in metrics if plan['scenes'][m['part']]['visual_type'] in ('crane','blocks','assembly')]
    synth_effects(ROOT/'feature-work/effects.wav',total/30,events)
    report={'frames':total,'duration_seconds':total/30,'actual_narration_seconds':spoken,'speaker':speaker,'part_metrics':metrics,'voices':reports,'sfx_events':events,'gemini_model':plan['response_model'],'script_origin':plan['script_origin'],'raw_gemini_sha256':plan['raw_response_sha256']}
    (ROOT/'feature-work/assembly.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('voices','part_metrics')},ensure_ascii=False))

def finish():
    assembly=json.loads((ROOT/'feature-work/assembly.json').read_text());duration=assembly['duration_seconds'];out=ROOT/'feature-output';out.mkdir(exist_ok=True)
    files=[]
    for i,m in enumerate(assembly['part_metrics']):
        path=ROOT/f'feature-renders/part-{i:02d}.mp4';v=next(s for s in probe(path)['streams'] if s['codec_type']=='video')
        if (int(v['nb_frames']),v['width'],v['height'],v['r_frame_rate'])!=(m['frames'],1080,1920,'30/1'):raise ValueError('Scene render format/length mismatch')
        files.append("file '"+str(path)+"'")
    listing=ROOT/'feature-work/concat.txt';listing.write_text('\n'.join(files))
    silent=ROOT/'feature-work/silent.mp4'
    subprocess.run(['ffmpeg','-y','-v','warning','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(silent)],check=True)
    filters=(f'[1:a]loudnorm=I=-16:TP=-2:LRA=7,asplit=2[voice][control];[2:a]atrim=duration={duration},asetpts=PTS-STARTPTS,loudnorm=I=-27:TP=-9:LRA=7,afade=t=in:d=1.2,afade=t=out:st={duration-2}:d=2[music];[music][control]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=350[ducked];[3:a]volume=.65[sfx];[voice][ducked][sfx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=.94:latency=1[mix]')
    video=out/'abu-simbel-gemini.mp4'
    subprocess.run(['ffmpeg','-y','-v','warning','-i',str(silent),'-i',str(ROOT/'feature-work/narration.wav'),'-stream_loop','-1','-i',str(ROOT/'assets/music/history_archive_reflection.mp3'),'-i',str(ROOT/'feature-work/effects.wav'),'-filter_complex',filters,'-map','0:v:0','-map','[mix]','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-t',str(duration),'-movflags','+faststart',str(video)],check=True)
    meta=probe(video);v=next(s for s in meta['streams'] if s['codec_type']=='video')
    if abs(float(meta['format']['duration'])-duration)>.15 or int(v['nb_frames'])!=assembly['frames']:raise ValueError('Delivery duration mismatch')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True)
    if video.stat().st_size>95_000_000:raise ValueError('Video exceeds Git branch file limit')
    verification={**{k:v for k,v in assembly.items() if k not in ('voices','part_metrics')},'width':1080,'height':1920,'fps':30,'scene_count':16,'all_critical_numbers_asr_checked':True,'full_decode_passed':True,'video_sha256':sha(video),'newly_synthesized_speech':True,'reference_video_audio_used':False,'motion_renderer':'Code-native SVG/Remotion; diagrams illustrative, not survey drawings','timing':'Independent Whisper medium anchors with bounded interpolation; user review required','status':'preview_for_user_review'}
    (out/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2))
    shutil.copy2(ROOT/'feature-work/plan.json',out/'gemini-script-and-storyboard.json');shutil.copy2(ROOT/'feature-work/assembly.json',out/'speech-and-timing-audit.json')
    for p in (ROOT/'feature-renders').glob('*.jpg'):shutil.copy2(p,out/p.name)
    print(json.dumps(verification,ensure_ascii=False,indent=2))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','finish']);args=a.parse_args();prepare() if args.mode=='prepare' else finish()
