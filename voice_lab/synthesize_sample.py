"""Generate genuinely new Egyptian-dialect speech; never replay reference audio."""
from pathlib import Path
import hashlib, json, os, subprocess, time
import numpy as np
import soundfile as sf
import torch
from silma_tts.api import SilmaTTS
from scripts.voice_profiles import resolve_reference_profile

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    out=Path("voice-lab-output");out.mkdir(exist_ok=True)
    text=Path("voice_lab/egyptian-sample.txt").read_text(encoding="utf8").strip()
    profile,label,reference,reference_text=resolve_reference_profile("mohamed_elbed")
    if text==reference_text or len(text.split())<20:
        raise ValueError("A new full paragraph is required")
    (out/"new-text.txt").write_text(text,encoding="utf8")
    started=time.time()
    model=SilmaTTS(device="cpu",enable_normalizer=False,force_tashkeel=False)
    wav,sr,_=model.infer(ref_file=str(reference),ref_text=reference_text,
        gen_text=text,file_wave=str(out/"sample.wav"),seed=20261020,
        speed=1.0,nfe_step=32,cross_fade_duration=0.10,
        normalize_numbers=False,force_tashkeel=False,remove_silence=False)
    actual,rate=sf.read(out/"sample.wav",always_2d=True)
    duration=len(actual)/rate
    if not 5<duration<90 or not np.isfinite(actual).all() or np.max(np.abs(actual))<0.001:
        raise ValueError("Synthesizer returned invalid or silent audio")
    if sha(out/"sample.wav")==sha(reference):
        raise ValueError("Reference replay detected")
    subprocess.run(["ffmpeg","-y","-v","error","-i",str(out/"sample.wav"),
        "-c:a","libmp3lame","-b:a","192k",str(out/"sample.mp3")],check=True)
    subprocess.run(["ffmpeg","-v","error","-i",str(out/"sample.mp3"),"-f","null","-"],check=True)
    report={"engine":"SILMA TTS v1 Small","source_commit":"2816b5a548c3ccdeea389ebc2db2d246a25d01fd",
        "newly_synthesized":True,"reference_replay":False,"voice_reference_profile":profile,
        "reference_label":label,"reference_sha256":sha(reference),
        "generated_wav_sha256":sha(out/"sample.wav"),"generated_mp3_sha256":sha(out/"sample.mp3"),
        "text":text,"duration":duration,"sample_rate":rate,"speed":1.0,
        "seed":20261020,"nfe_step":32,"automatic_fusha_diacritization":False,
        "time_stretch_or_pitch_shift":False,"fallback_used":False,
        "inference_seconds":round(time.time()-started,2),
        "pronunciation_and_similarity":"requires user listening; not automatically certified"}
    (out/"generation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
