"""Auditable Egyptian speech test with VoiceTut; no fallback or user voice cloning."""
from pathlib import Path
import hashlib,json,os,subprocess,time,logging
import numpy as np
import soundfile as sf
import torch
from voicetut_tts import VoiceTutTTS
logging.basicConfig(level=logging.INFO)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(20261020)
    out=Path("voicetut-output");out.mkdir(exist_ok=True)
    text=Path("voice_lab/egyptian-sample.txt").read_text(encoding="utf8").strip()
    (out/"new-text.txt").write_text(text,encoding="utf8")
    started=time.time()
    tts=VoiceTutTTS.from_pretrained("mohammedaly22/VoiceTut-TTS",device="cpu",dtype="float32")
    names=[s.speaker_name for s in tts.list_speakers()]
    (out/"available-speakers.json").write_text(json.dumps(names,ensure_ascii=False,indent=2))
    if "Mohammed" not in names:raise ValueError(f"Requested speaker unavailable: {names}")
    reference=tts.registry.get("Mohammed")
    load_seconds=time.time()-started
    started_infer=time.time()
    tts.synthesize(text,speaker="Mohammed",language="arz",num_step=32,
        guidance_scale=2.0,speed=1.0,output=str(out/"sample.wav"))
    wav,sr=sf.read(out/"sample.wav",always_2d=True);duration=len(wav)/sr
    if not 5<duration<90 or not np.isfinite(wav).all() or np.max(np.abs(wav))<.001:
        raise ValueError("Invalid or silent generated sample")
    if sha(out/"sample.wav")==sha(reference.audio_path):raise ValueError("Reference replay detected")
    subprocess.run(["ffmpeg","-y","-v","error","-i",str(out/"sample.wav"),"-c:a","libmp3lame","-b:a","192k",str(out/"sample.mp3")],check=True)
    subprocess.run(["ffmpeg","-v","error","-i",str(out/"sample.mp3"),"-f","null","-"],check=True)
    report={"engine":"VoiceTut-TTS","model":"mohammedaly22/VoiceTut-TTS",
        "wrapper_commit":"44cba00cd3ddb04b5213353e19e960045e332da7","backbone_commit":"08be0b4ccbac3e13e374e86fbfead4b4cac343e2",
        "speaker":"Mohammed","language":"arz","newly_synthesized":True,"reference_replay":False,
        "voice_mode":"project built-in speaker; no user recording supplied",
        "text":text,"duration":duration,"sample_rate":sr,"speed":1.0,"num_step":32,
        "guidance_scale":2.0,"device":"cpu","dtype":"float32","fallback_used":False,
        "reference_sha256":sha(reference.audio_path),"generated_wav_sha256":sha(out/"sample.wav"),
        "generated_mp3_sha256":sha(out/"sample.mp3"),"model_load_seconds":round(load_seconds,2),
        "inference_seconds":round(time.time()-started_infer,2),
        "quality_status":"requires user listening; no automatic artistic or dialect approval"}
    (out/"generation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
