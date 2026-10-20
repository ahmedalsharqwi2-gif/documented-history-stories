"""Strict Gemini-authored feature. No local narration fallback."""
from pathlib import Path
import json,os,re,time,urllib.request,urllib.error,hashlib
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"feature-work";OUT.mkdir(exist_ok=True)
FACTS=json.loads((ROOT/"motion_feature/facts.json").read_text())
VISUALS={"temple","water","map","cutaway","grid","blocks","crane","lift","distance","assembly","sun","timeline","network","legacy"}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def expand(text,mode="plain"):
    for tag,data in FACTS["numeric_policy"]["tokens"].items():text=text.replace(tag,data[mode])
    return text
def check(data):
    scenes=data.get("scenes",[])
    if len(scenes)!=16:raise ValueError("Exactly 16 scenes required")
    all_text=" ".join(s.get("narration","") for s in scenes)
    if re.search(r"\d",all_text):raise ValueError("Numbers must use the four declared tags")
    for tag in FACTS["numeric_policy"]["tokens"]:
        if all_text.count(tag)!=1:raise ValueError("Use each numeric fact tag exactly once: "+tag)
    if re.search(r"\{[^}]+\}",expand(all_text)):raise ValueError("Unknown narration tag")
    count=len(expand(all_text).split())
    if not 340<=count<=460:raise ValueError(f"Need 340-460 words for >2 minutes; received {count}")
    markers=r"\b(?:ده|دي|اللي|عشان|مش|إزاي|ازاي|ليه|دلوقتي|كده|كانوا|بقت|بقى|اتنقل|اتعمل|بنحافظ|هنشوف)\b"
    if len(re.findall(markers,all_text))<18 or sum(bool(re.search(markers,s.get("narration",""))) for s in scenes)<10:
        raise ValueError("Rewrite in natural spoken Egyptian: at least 18 colloquial markers across at least 10 scenes; formal Arabic is rejected")
    if any(term in all_text for term in ["أضخم عملية","تاريخ البشرية","دون إلحاق أي ضرر","أحدث وسائل","مناسبات ملكية","الموحدة"]):
        raise ValueError("Remove unsupported superlatives, absolute damage guarantees and leaked drafting instructions")
    known={s["id"] for s in FACTS["sources"]}
    for i,s in enumerate(scenes):
        if not 19<=len(expand(s.get("narration","")).split())<=34:raise ValueError(f"Scene {i} needs 19-34 words")
        if s.get("visual_type") not in VISUALS:raise ValueError("Unsupported graphic")
        if not s.get("source_ids") or not set(s["source_ids"])<=known:raise ValueError("Source ids required")
        if re.search(r"[A-Za-z]",expand(s["narration"])):raise ValueError("Arabic narration only")
        if len(s.get("title",""))>50 or len(s.get("highlight","").split())>4:raise ValueError("Graphic copy too long")
        s["id"]=f"scene-{i:02d}"
        s["display_text"]=expand(s["narration"],"plain")
        s["spoken_text"]=expand(s["narration"],"spoken")
        s["labels"]=[str(v)[:35] for v in s.get("labels",[])[:3]]
    data["word_count"]=count
    return data
def call(url,key,payload=None):
    headers={"x-goog-api-key":key,"Content-Type":"application/json"}
    req=urllib.request.Request(url,headers=headers,data=None if payload is None else json.dumps(payload).encode())
    with urllib.request.urlopen(req,timeout=100) as r:return json.load(r)
def run():
    key=os.environ.get("GEMINI_API_KEY","").strip()
    if not key:raise RuntimeError("GEMINI_API_KEY missing. No Codex-written substitute is allowed.")
    models=call("https://generativelanguage.googleapis.com/v1beta/models",key).get("models",[])
    names=[m["name"].split("/")[-1] for m in models if "generateContent" in m.get("supportedGenerationMethods",[])]
    # These Flash-Lite models have a documented free tier; never use Pro or paid-only generation.
    order=["gemini-3.5-flash-lite","gemini-flash-lite-latest","gemini-3.1-flash-lite","gemini-2.5-flash-lite"]
    candidates=[m for m in order if m in names][:1]
    (OUT/"model-discovery.json").write_text(json.dumps({"available_text_models":names,"candidates":candidates},indent=2))
    prompt="""You are the sole scriptwriter and storyboard director for a new Egyptian Arabic motion documentary.
This is SPOKEN EGYPTIAN, not Modern Standard Arabic. Use ده، دي، اللي، عشان، مش، إزاي،
ليه، بقى، اتنقل naturally; at least 18 colloquial markers across at least ten scenes.
Begin with a compelling Egyptian question about the practical puzzle of moving a rock-cut temple,
not a formal geography introduction. Explain concrete engineering in plain short spoken sentences.
Avoid ornate adjectives and repeated praise. No unsupported biggest-in-history claims,
no claim of zero damage and no claim of the latest equipment. Do not say the drafting constraints aloud.
The 65-metre rise and 200-metre setback are approximate changes from the OLD SITE,
not a measured height above the lake. Make that reference clear.
Write an ORIGINAL complete story about the supplied Abu Simbel rescue facts. This is not Dunkirk.
Return JSON {"title":"Arabic", "scenes":[16 scene objects]}.
Every scene: narration (Egyptian colloquial Arabic, 26-31 words), title (short Arabic),
highlight (1-4 Arabic words), visual_type (one of the allowed types below),
labels (0-3 short Arabic graphic labels), source_ids (provided IDs supporting its facts).
TOTAL 400-450 spoken words; aim at 430 words, a genuine 150-190 second spoken documentary.
Use a compelling opening, a progressing engineering challenge, clear explanations and a real closing.
Do not add subscriptions or an introduction about the channel. Do not repeat the same point to fill time.
Use only the provided source facts. Do not invent quotations, detailed engineering machinery, block counts,
weights, costs, flood deadlines, solar dates, royal birthdays, or an exact location measurement.
Explain documentation, careful division, lifting, relocation, reassembly and heritage cooperation.
Refer to approximate relocation distances using حوالي or نحو.
Use EACH of these number tags exactly ONCE in narration: {start_year}, {end_year}, {height}, {setback}.
Do not write digits or other numeric years in narration. Numbers will be expanded by a tested speech layer.
Numbers in graphic labels may use Arabic digits, but never introduce a fact outside the source packet.
Keep narration natural to Egyptian ears, short grammatical sentences, no stage directions.
Vary graphic types to match the meaning; minimum 9 distinct types across 16 scenes.
Allowed visual_type: temple, water, map, cutaway, grid, blocks, crane, lift, distance, assembly,
sun, timeline, network, legacy.
SOURCE FACTS:
"""+json.dumps(FACTS,ensure_ascii=False)
    attempts=[];last_error="No supported free-tier Gemini model discovered"
    for model in candidates:
        for attempt in range(6):
            fields={k:{"type":"STRING"} for k in ("narration","title","highlight")}
            fields["visual_type"]={"type":"STRING","enum":sorted(VISUALS)}
            fields["labels"]={"type":"ARRAY","items":{"type":"STRING"}}
            fields["source_ids"]={"type":"ARRAY","items":{"type":"STRING","enum":[x["id"] for x in FACTS["sources"]]}}
            item={"type":"OBJECT","required":list(fields),"properties":fields}
            schema={"type":"OBJECT","required":["title","scenes"],"properties":{"title":{"type":"STRING"},"scenes":{"type":"ARRAY","minItems":16,"maxItems":16,"items":item}}}
            payload={"contents":[{"parts":[{"text":prompt}]}],
                "generationConfig":{"temperature":.55,"maxOutputTokens":12000,"responseMimeType":"application/json","responseSchema":schema}}
            try:
                raw=call("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent",key,payload)
                text="".join(p.get("text","") for p in raw["candidates"][0]["content"]["parts"] if not p.get("thought"))
                (OUT/"gemini-raw-response.json").write_text(json.dumps(raw,ensure_ascii=False,indent=2))
                (OUT/"gemini-original-script.json").write_text(text)
                plan=check(json.loads(text))
                if len({s["visual_type"] for s in plan["scenes"]})<9:raise ValueError("At least nine visual families required")
                attempts.append({"model":model,"attempt":attempt+1,"status":"accepted"})
                plan.update(script_origin="Gemini API original narrative and storyboard; no locally authored fallback",
                    requested_model=model,response_model=raw.get("modelVersion"),usage=raw.get("usageMetadata",{}),
                    sources=FACTS["sources"],numeric_policy=FACTS["numeric_policy"],provider_attempts=attempts,
                    raw_response_sha256=sha(OUT/"gemini-raw-response.json"),minimum_video_seconds=125,status="preview_for_user_review")
                (OUT/"plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2))
                print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True)
                return
            except urllib.error.HTTPError as e:
                body=e.read().decode(errors="replace").replace(key,"[redacted]")
                try:err=json.loads(body).get("error",{});detail={k:err.get(k) for k in ("code","status","message")}
                except ValueError:detail={"message":body[:300]}
                attempts.append({"model":model,"attempt":attempt+1,"http_status":e.code,"detail":detail})
                last_error=f"{model}: HTTP {e.code}"
                print(json.dumps(attempts[-1],ensure_ascii=False),flush=True)
                if e.code in (400,401,403,404,429):break
                time.sleep(5)
            except (ValueError,KeyError,IndexError) as e:
                last_error=str(e);attempts.append({"model":model,"attempt":attempt+1,"validation_error":str(e)})
                print("Gemini draft needs repair:",str(e),flush=True)
                prompt+="\nYour last draft was rejected: "+str(e)+". Each of the 16 scenes must have about 27 words; count the spoken words per scene. Previous JSON for you to REVISE in full, not summarize:\n"+text
            except Exception as e:
                last_error=type(e).__name__;attempts.append({"model":model,"attempt":attempt+1,"error":last_error})
                print("Gemini request failed:",last_error,flush=True)
                time.sleep(3)
    (OUT/"generation-failure.json").write_text(json.dumps({"attempts":attempts,"error":last_error,"substitute_used":False},ensure_ascii=False,indent=2))
    raise RuntimeError("Gemini did not produce a valid original script: "+last_error)
if __name__=="__main__":run()

