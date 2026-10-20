"""Source-based Dunkirk narration, accepted VoiceTut, vector motion and measured soundtrack."""
from pathlib import Path
import argparse,hashlib,json,math,os,re,shutil,subprocess,time,wave
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parent.parent
PLAN=ROOT/"episode-work/plan.json"
PREPARED=[
 {"id":"beach","title":"البحر طريق النجاة","narration":"في مايو سنة ألف وتسعمية وأربعين، قوات الحلفاء اتحاصرت عند دنكرك في شمال فرنسا، وبقى البحر طريق النجاة."},
 {"id":"evacuation","title":"دور القوارب الصغيرة","narration":"السفن الكبيرة ما كانتش بتوصل لكل مكان على الشاطئ. هنا ظهر دور القوارب الصغيرة، اللي ساعدت تنقل الجنود للسفن."},
 {"id":"boats","title":"مدنيون وبحرية","narration":"قوارب صيد ويخوت ومراكب مدنية شاركت جنب البحرية. عملية الإجلاء استمرت من أواخر مايو لحد أربعة يونيو."},
 {"id":"return","title":"إنقاذ أكثر من ٣٣٨ ألف","narration":"في النهاية، اتنقذ أكتر من تلتمية تمانية وتلاتين ألف جندي. انسحاب دنكرك ما كانش انتصار عسكري، لكنه أنقذ قوات تقدر تكمل القتال."}
]
SOURCES=[
 "https://www.english-heritage.org.uk/visit/places/dover-castle/history-and-stories/operation-dynamo-things-you-need-to-know/",
 "https://www.royalnavy.mod.uk/news/2025/february/05/250205-royal-navy-to-escort-dunkirk-little-ships-for-85th-anniversary"
]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def validate_script(scenes):
    if not isinstance(scenes,list) or len(scenes)!=4:raise ValueError("Four narration-linked scenes required")
    for given,base in zip(scenes,PREPARED):
        if given.get("id")!=base["id"]:raise ValueError("Storyboard topic/order mismatch")
        text=given.get("narration","")
        if not 12<=len(text.split())<=35 or re.search(r"[0-9]",text):raise ValueError("Unsupported narration length or unspoken numeric form")
        if len(re.findall(r"[\u0621-\u064a]",text))<len(text)*.55:raise ValueError("Narration must be Arabic")
        if any(x in text for x in ["جميع الجنود بالقوارب الصغيرة","انتصار ساحق","غرق الجيش الألماني"]):raise ValueError("Unsupported historical claim")
    return scenes
def prepare():
    scenes=PREPARED;origin="Codex prepared Egyptian script, based on reviewed source facts";model=None;attempts=[]
    key=os.getenv("GEMINI_API_KEY","").strip()
    if key:
        import requests
        headers={"x-goog-api-key":key}
        try:
            r=requests.get("https://generativelanguage.googleapis.com/v1beta/models",headers=headers,timeout=30);r.raise_for_status()
            available=[m["name"].split("/")[-1] for m in r.json().get("models",[]) if "generateContent" in m.get("supportedGenerationMethods",[])]
            preferred=[os.getenv("GEMINI_MODEL",""),"gemini-flash-lite-latest","gemini-3.1-flash-lite","gemini-2.5-flash-lite"]
            candidates=[m for m in preferred if m and m in available]
            prompt=("Write Egyptian Arabic narration for a factual Dunkirk documentary, using ONLY the supplied facts. "
                "Return a JSON array of exactly four objects, each with id and narration, preserving IDs and order. "
                "Each paragraph 18-28 words. No extra dates, names, numbers, tactical claims, stage directions, headings or calls to action. "
                "Keep all numerals spelled in Egyptian Arabic. Small boats helped larger naval ships: do not claim civilians alone rescued everyone. "
                "The operation ended on 4 June 1940 and rescued over 338,000 troops. Keep the meaning of each provided paragraph. "
                "Preserve the four storyboard subjects.\n"+json.dumps(PREPARED,ensure_ascii=False))
            for candidate in list(dict.fromkeys(candidates))[:2]:
                try:
                    response=requests.post("https://generativelanguage.googleapis.com/v1beta/models/"+candidate+":generateContent",headers=headers,
                        json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":.35,"maxOutputTokens":1800,"responseMimeType":"application/json"}},timeout=90)
                    attempts.append({"model":candidate,"http_status":response.status_code})
                    response.raise_for_status()
                    text="".join(p.get("text","") for p in response.json()["candidates"][0]["content"]["parts"])
                    draft=validate_script(json.loads(text))
                    scenes=[{**base,"narration":d["narration"]} for base,d in zip(PREPARED,draft)]
                    origin="Gemini constrained rewrite of Codex prepared source-based scene plan";model=candidate;break
                except Exception as exc:
                    print("Script provider attempt did not pass:",candidate,type(exc).__name__,flush=True)
        except Exception as exc:print("Script provider unavailable; using the prepared source-based script:",type(exc).__name__,flush=True)
    validate_script(scenes)
    plan={"title":"دنكرك: القوارب الصغيرة وإنقاذ جيش","topic":"Dunkirk evacuation 1940","script_origin":origin,"text_model":model,
        "provider_attempts":attempts,"scenes":scenes,"sources":SOURCES,"visuals_origin":"Code-native SVG motion graphics; real Natural Earth coastline; illustrative routes",
        "status":"preview_for_user_review"}
    PLAN.parent.mkdir(parents=True,exist_ok=True);PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:f.write('matrix={"part":[0,1,2,3]}\n')
def voice(part):
    from voice_provider.client import generate
    plan=json.loads(PLAN.read_text());out=ROOT/"episode-parts";out.mkdir(exist_ok=True)
    generate(plan["scenes"][part]["narration"],out/f"part-{part}.wav")
def norm(word):
    word=word.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩","0123456789"))
    word=re.sub(r"[\u064b-\u065f\u0670ـ]","",word)
    return re.sub(r"[^\u0621-\u064a0-9]","",word).replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ى","ي")
def caption_timing(model,path,text,duration):
    import numpy as np
    pcm=subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-ar","16000","-ac","1","-f","f32le","-"])
    audio=np.frombuffer(pcm,np.float32)
    segments,_=model.transcribe(audio,language="ar",word_timestamps=True,vad_filter=False,beam_size=5,condition_on_previous_text=False)
    recognized=[{"text":w.word.strip(),"start":float(w.start),"end":float(w.end)} for seg in segments for w in (seg.words or []) if norm(w.word)]
    # ASR often writes a spoken number as digits. Expand only known episode numbers,
    # preserving the recognized span rather than pretending new timestamps were measured.
    expanded=[]
    number_words={"1940":["ألف","وتسعمية","وأربعين"],"338":["تلتمية","تمانية","وتلاتين"],
        "338000":["تلتمية","تمانية","وتلاتين","ألف"],"4":["أربعة"]}
    for w in recognized:
        words=number_words.get(norm(w["text"]),[w["text"]])
        step=(w["end"]-w["start"])/len(words)
        expanded.extend({"text":word,"start":w["start"]+k*step,"end":w["start"]+(k+1)*step} for k,word in enumerate(words))
    raw_recognized=recognized;recognized=expanded
    expected=text.split();clean_expected=[norm(w) for w in expected];clean_actual=[norm(w["text"]) for w in recognized]
    matcher=SequenceMatcher(None,clean_expected,clean_actual,autojunk=False);anchors={}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):anchors[block.a+k]=recognized[block.b+k]
    exact_coverage=len(anchors)/max(1,len(expected));near_matches=[]
    # Accept only long, close spellings in one-to-one replacement blocks bounded
    # by exact matching context. Short function words and token-count changes are excluded.
    for tag,a0,a1,b0,b1 in matcher.get_opcodes():
        if tag!="replace" or a1-a0!=b1-b0:continue
        for ei,ai in zip(range(a0,a1),range(b0,b1)):
            left,right=clean_expected[ei],clean_actual[ai]
            ratio=SequenceMatcher(None,left,right,autojunk=False).ratio()
            if min(len(left),len(right))>=4 and ratio>=.85:
                anchors[ei]=recognized[ai]
                near_matches.append({"expected":expected[ei],"recognized":recognized[ai]["text"],"similarity":round(ratio,4)})
    coverage=len(anchors)/max(1,len(expected))
    if coverage<.72:
        debug=ROOT/"output";debug.mkdir(exist_ok=True)
        (debug/(Path(path).stem+"-alignment-failed.json")).write_text(json.dumps({"coverage":coverage,"expected":text,"recognized":raw_recognized},ensure_ascii=False,indent=2))
        print(json.dumps({"coverage":coverage,"expected":text,"recognized":raw_recognized},ensure_ascii=False),flush=True)
        raise ValueError(f"Insufficient speech timing anchors: {coverage:.3f}. Voice will not be replaced.")
    timed=[None]*len(expected)
    for i,a in anchors.items():timed[i]={"start":max(0,a["start"]),"end":min(duration,a["end"])}
    i=0
    while i<len(timed):
        if timed[i] is not None:i+=1;continue
        start=i
        while i<len(timed) and timed[i] is None:i+=1
        left=timed[start-1]["end"] if start else 0
        right=timed[i]["start"] if i<len(timed) else duration
        if right<left:right=left
        step=(right-left)/max(1,i-start)
        for k in range(start,i):timed[k]={"start":left+(k-start)*step,"end":left+(k-start+1)*step}
    caps=[]
    for start in range(0,len(expected),6):
        stop=min(len(expected),start+6);a=timed[start]["start"];b=timed[stop-1]["end"]
        if b<=a:raise ValueError("Invalid interpolated subtitle span")
        if caps and a<caps[-1]["end"]:a=caps[-1]["end"]
        caps.append({"start":a,"end":max(a+.01,b),"text":" ".join(expected[start:stop])})
    caps[0]["start"]=0;caps[-1]["end"]=duration
    for ci,c in enumerate(caps):
        c["words"]=[{"text":expected[k],**timed[k]} for k in range(ci*6,min(len(expected),(ci+1)*6))]
    return caps,{"matched_word_fraction":round(coverage,4),"exact_word_fraction":round(exact_coverage,4),"near_spelling_matches":near_matches,"recognized_text":" ".join(w["text"] for w in raw_recognized),"timing":"ASR anchors; known digit-form numbers expanded within their recognized spans; long near-spelling matches in equal-length replacement blocks; bounded interpolation for unmatched tokens"}
def map_paths():
    geo=json.loads((ROOT/"history_visual/assets/countries.geojson").read_text())
    paths=[]
    for feature in geo["features"]:
        g=feature["geometry"];polys=g["coordinates"] if g["type"]=="MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            pieces=[]
            for ring in poly:
                coords=[(120+(lon+1.5)*150,140+(52.8-lat)*230) for lon,lat,*_ in ring]
                pieces.append("M"+"L".join(f"{x:.1f},{y:.1f}" for x,y in coords)+"Z")
            paths.append({"name":feature["properties"].get("ADMIN",""),"d":"".join(pieces)})
    return paths
def synth_effects(path,duration,events):
    """Original noise sweeps with short envelopes; no sound for every token."""
    import numpy as np
    rate=48000;rng=np.random.default_rng(20261020);samples=np.zeros(round(duration*rate),np.float32)
    for when in events:
        n=round(.42*rate);noise=rng.standard_normal(n)
        smooth=np.convolve(noise,np.ones(18)/18,mode="same")
        signal=.1*smooth*np.sin(np.pi*np.arange(n)/n)**2
        start=max(0,round(when*rate));end=min(len(samples),start+n)
        samples[start:end]+=signal[:end-start]
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes((np.clip(samples,-1,1)*32767).astype("<i2").tobytes())
def probe(path):
    return json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)]))
def assemble():
    from faster_whisper import WhisperModel
    plan=json.loads(PLAN.read_text());public=ROOT/"episode-work/public";public.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/"photo_motion/assets/NotoSansArabic-Bold.ttf",public/"NotoSansArabic-Bold.ttf")
    output=ROOT/"output";output.mkdir(exist_ok=True)
    model=WhisperModel("small",device="cpu",compute_type="int8")
    captions=[];scenes=[];alignment=[];frames=[];cursor=0.;rate=channels=width=None;reports=[]
    for i,s in enumerate(plan["scenes"]):
        path=ROOT/f"episode-parts/part-{i}.wav"
        with wave.open(str(path),"rb") as f:
            params=(f.getframerate(),f.getnchannels(),f.getsampwidth())
            if rate is None:rate,channels,width=params
            if params!=(rate,channels,width):raise ValueError("Voice chunk formats differ")
            n=f.getnframes();payload=f.readframes(n);duration=n/rate
        caps,metrics=caption_timing(model,path,s["narration"],duration)
        for c in caps:
            captions.append({**c,"start":c["start"]+cursor,"end":c["end"]+cursor,
                "words":[{**w,"start":w["start"]+cursor,"end":w["end"]+cursor} for w in c["words"]]})
        metrics["part"]=i;alignment.append(metrics)
        print(json.dumps({"alignment_part":i,**metrics},ensure_ascii=False),flush=True)
        gap=round(.24*rate)/rate if i<3 else .5
        scenes.append({**s,"start":cursor,"end":cursor+duration+gap})
        frames.append(payload)
        if gap:frames.append(bytes(round(gap*rate)*channels*width))
        reports.append(json.loads(path.with_suffix(".voice.json").read_text()))
        cursor+=duration+gap
    narration=ROOT/"episode-work/narration.wav"
    with wave.open(str(narration),"wb") as f:
        f.setnchannels(channels);f.setsampwidth(width);f.setframerate(rate);f.writeframes(b"".join(frames))
    with wave.open(str(narration)) as f:cursor=f.getnframes()/f.getframerate()
    scenes[-1]["end"]=cursor
    props={"duration":cursor,"scenes":scenes,"captions":captions,"mapPaths":map_paths()}
    (ROOT/"episode-work/render.json").write_text(json.dumps(props,ensure_ascii=False))
    events=[s["start"] for s in scenes]+[scenes[3]["start"]+2.9]
    synth_effects(ROOT/"episode-work/effects.wav",cursor,events)
    subprocess.run(["node","scripts/render-episode.mjs"],cwd=ROOT/"video-toolkit",check=True,timeout=600)
    music=ROOT/"assets/music/history_archive_reflection.mp3"
    video=output/"motion-episode.mp4"
    filters=(
      f"[1:a]loudnorm=I=-16:TP=-2:LRA=7,asplit=2[voice][control];"
      f"[2:a]atrim=duration={cursor},asetpts=PTS-STARTPTS,loudnorm=I=-26:TP=-8:LRA=7,"
      f"afade=t=in:d=1.2,afade=t=out:st={max(0,cursor-2)}:d=2[music];"
      "[music][control]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=350[ducked];"
      "[3:a]volume=0.75[sfx];"
      "[voice][ducked][sfx]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.94:latency=1[mix]")
    subprocess.run(["ffmpeg","-y","-v","warning","-i",str(ROOT/"episode-work/silent.mp4"),"-i",str(narration),
        "-stream_loop","-1","-i",str(music),"-i",str(ROOT/"episode-work/effects.wav"),"-filter_complex",filters,
        "-map","0:v:0","-map","[mix]","-c:v","copy","-c:a","aac","-b:a","192k","-ar","48000",
        "-t",f"{cursor:.6f}","-movflags","+faststart",str(video)],check=True)
    meta=probe(video);v=next(s for s in meta["streams"] if s["codec_type"]=="video");a=next(s for s in meta["streams"] if s["codec_type"]=="audio")
    if (v["width"],v["height"],v["r_frame_rate"])!=(1080,1920,"30/1"):raise ValueError("Wrong delivery format")
    if abs(float(meta["format"]["duration"])-cursor)>.12:raise ValueError("Final video duration drift")
    if video.stat().st_size>90_000_000:raise ValueError("Preview too large for the result branch")
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(video),"-f","null","-"],check=True)
    verification={"passed":True,"duration_seconds":cursor,"width":1080,"height":1920,"fps":30,
        "decoded_complete":True,"scene_count":4,"word_count":sum(len(c["words"]) for c in captions),
        "voice":"New VoiceTut Mohammed speech, four independent segments; no reference-video voice recording",
        "voice_pcm_before_mix_sha256":sha(narration),"music_file":str(music.relative_to(ROOT)),"music_sha256":sha(music),
        "audio_mix":"Narration -16 LUFS, music -26 LUFS before sidechain ducking, original air-sweep SFX on selected events, peak limiter",
        "sfx_events_seconds":events,"visuals":"SVG motion graphics, real Natural Earth coastlines, schematic ship positions and routes",
        "caption_timing":"Whisper small anchors with bounded interpolation. Automatic timing requires user review.",
        "video_sha256":sha(video),"status":"preview_for_user_review"}
    for name,data in [("verification.json",verification),("script-plan.json",plan),("alignment.json",alignment),("voice-parts.json",reports),("storyboard.json",props)]:
        (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(json.dumps(verification,ensure_ascii=False,indent=2),flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["prepare","voice","assemble"]);p.add_argument("--part",type=int);a=p.parse_args()
    if a.mode=="prepare":prepare()
    elif a.mode=="voice":voice(a.part)
    else:assemble()
if __name__=="__main__":main()
