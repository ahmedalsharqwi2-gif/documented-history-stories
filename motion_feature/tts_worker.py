"""New VoiceTut speech with intact number phrases; trial speaker never changes production defaults."""
from pathlib import Path
import argparse,json,hashlib,time,re
ROOT=Path(__file__).resolve().parent.parent
AUDITION="سنة أَلْف تِسْعُمِيَّة أَرْبَعَة وَسِتِّين، بدأت عملية الإنقاذ. والارتفاع كان حوالي خَمْسَة وَسِتِّين مِتْر، والنقل حوالي مِيتِين مِتْر."
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare_spoken(text):
    changes={"أبو سمبل":"أبو سِمْبِل","نفرتاري":"نِفِرْتَارِي","رمسيس":"رَمْسِيس","اليونسكو":"اليُونِسْكُو"}
    for a,b in changes.items():text=text.replace(a,b)
    if re.search(r"\d|\{[^}]+\}",text):raise ValueError("Unexpanded numeric speech")
    return text
def main():
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["audition","scene"]);p.add_argument("--speaker",required=True);p.add_argument("--part",type=int,default=0);p.add_argument("--seed",type=int,default=20261020);a=p.parse_args()
    import numpy as np,soundfile as sf,torch
    from voicetut_tts import VoiceTutTTS
    from voicetut_tts.engine import GenerationParams
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(a.seed+a.part)
    tts=VoiceTutTTS.from_pretrained("mohammedaly22/VoiceTut-TTS",device="cpu",dtype="float32",language="arz")
    speakers={s.speaker_name:s for s in tts.list_speakers()}
    if a.speaker not in speakers:raise ValueError("Trial speaker unavailable")
    if a.mode=="audition":
        text=AUDITION;out=ROOT/"voice-auditions"/a.speaker/"sample.wav"
        source={"type":"independent_new_number_pronunciation_test","speaker":a.speaker,"expected_values":[1964,65,200]}
    else:
        plan=json.loads((ROOT/"feature-work/plan.json").read_text())
        scene=plan["scenes"][a.part];text=scene["spoken_text"]
        out=ROOT/"feature-voices"/f"part-{a.part:02d}.wav"
        source={"type":"new_gemini_scene","scene":scene["id"],"gemini_model":plan["response_model"],
            "original_gemini_narration":scene["narration"],"display_text":scene["display_text"],
            "expected_values":[v["value"] for tag,v in plan["numeric_policy"]["tokens"].items() if tag in scene["narration"]]}
    text=prepare_spoken(text);out.parent.mkdir(parents=True,exist_ok=True)
    started=time.time();sp=speakers[a.speaker]
    params=GenerationParams(num_step=32,guidance_scale=2.0,speed=1.0)
    # Public OmniVoice generate API, same VoiceTut checkpoint and built-in reference.
    # One complete scene bypasses VoiceTut's first-110-character chunk boundary:
    # a multiword number can never be cut between two independent generations.
    result=tts.model.generate(text=text,language="arz",ref_audio=sp.audio_path,ref_text=sp.reference_text,**params.as_kwargs())
    wave=np.asarray(result[0],np.float32).reshape(-1)
    if not np.isfinite(wave).all() or np.max(np.abs(wave))<.001:raise ValueError("Invalid generated audio")
    sf.write(out,wave,tts.sampling_rate,subtype="PCM_16")
    duration=len(wave)/tts.sampling_rate
    if not 2<=duration<=30:raise ValueError("Unexpected scene speech duration")
    report={**source,"speaker":a.speaker,"provider":"VoiceTut-TTS","model":"mohammedaly22/VoiceTut-TTS",
        "spoken_text":text,"normalize":False,"one_shot_scene":True,"num_step":32,"guidance_scale":2.0,"speed":1,
        "duration":duration,"sample_rate":tts.sampling_rate,"elapsed_seconds":round(time.time()-started,2),
        "seed":a.seed+a.part,"sha256":sha(out),"newly_synthesized":True,"reference_video_used":False,
        "wrapper_commit":"44cba00cd3ddb04b5213353e19e960045e332da7","backbone_commit":"08be0b4ccbac3e13e374e86fbfead4b4cac343e2"}
    out.with_suffix(".voice.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if a.mode=="audition":(out.parent/"available-speakers.json").write_text(json.dumps([s.to_public() for s in speakers.values()],ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()

