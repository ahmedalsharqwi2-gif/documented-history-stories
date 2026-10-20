"""Synthesize complete spoken scenes, then time visuals against measured audio.

No timing is guessed from English forced alignment. Resume keys include the
script, voice and rate. A voice failure stops production before rendering.
"""
import asyncio, hashlib, json, math, subprocess, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(cmd):subprocess.run(cmd,check=True)
async def prepare():
 import edge_tts
 ep=json.loads((ROOT/'episodes/rosetta.json').read_text())
 cache=ROOT/'.cache/voice';cache.mkdir(parents=True,exist_ok=True)
 audio=ROOT/'audio';audio.mkdir(exist_ok=True);data=ROOT/'data';data.mkdir(exist_ok=True)
 offset=0.;pcm=[];lyrics=[]
 for i,s in enumerate(ep['scenes']):
  key=hashlib.sha256((s['text']+ep['voice']+ep['rate']+'tts-policy-v2').encode()).hexdigest()[:20]
  mp3=cache/f'{key}.mp3';wav=cache/f'{key}.wav'
  if not wav.exists():
   provider='edge:'+ep['voice']
   for attempt in range(2):
    try:
     await asyncio.wait_for(edge_tts.Communicate(s['text'],ep['voice'],rate=ep['rate']).save(str(mp3)),timeout=40)
     run(['ffmpeg','-y','-v','error','-i',str(mp3),'-ar','24000','-ac','1','-c:a','pcm_s16le',str(wav)])
     with wave.open(str(wav)) as w:
      if w.getnframes()<2400:raise RuntimeError('Empty voice output')
     break
    except Exception as exc:
     mp3.unlink(missing_ok=True);wav.unlink(missing_ok=True)
     if attempt==1:
      from google_tts import google_arabic_voice
      print(f'Edge unavailable ({type(exc).__name__}); using Google Arabic fallback',flush=True)
      await asyncio.to_thread(google_arabic_voice,s['text'],mp3)
      run(['ffmpeg','-y','-v','error','-i',str(mp3),'-ar','24000','-ac','1','-c:a','pcm_s16le',str(wav)])
      provider='google-arabic-fallback'
      break
     await asyncio.sleep(3*(attempt+1))
   wav.with_suffix('.json').write_text(json.dumps({'provider':provider}))
  provider=json.loads(wav.with_suffix('.json').read_text())['provider']
  with wave.open(str(wav)) as w:
   samples=w.readframes(w.getnframes());seconds=w.getnframes()/w.getframerate()
  s['start']=round(offset,4);s['end']=round(offset+seconds+.16,4);s['voice_provider']=provider
  pcm.extend([samples,b'\0'*round(.16*24000*2)]);offset=s['end']
  # Empty word lists intentionally: these are scene timings, not word alignment.
  lyrics.append({'text':s['text'],'start':s['start'],'end':s['end'],'words':[]})
  print(f"VOICE {i+1}/{len(ep['scenes'])}: {seconds:.2f}s",flush=True)
 with wave.open(str(audio/'voiceover.wav'),'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b''.join(pcm))
 run(['ffmpeg','-y','-v','error','-i',str(audio/'voiceover.wav'),'-c:a','libmp3lame','-q:a','2',str(audio/'voiceover.mp3')])
 ep['duration']=offset;ep['timing']='measured scene audio durations, not word forced alignment'
 (data/'episode.json').write_text(json.dumps(ep,ensure_ascii=False,indent=2))
 (data/'lyrics.json').write_text(json.dumps({'lines':lyrics},ensure_ascii=False))
 (data/'audio.json').write_text(json.dumps({'duration':offset,'bpm':100,'fps':10,'beats':[i*.6 for i in range(math.ceil(offset/.6))],'downbeats':[i*2.4 for i in range(math.ceil(offset/2.4))],'sections':[{'name':s['id'],'start':s['start'],'end':s['end']} for s in ep['scenes']],'features':{},'onsets':{}}))
 print(f'PREPARED {offset:.2f}s',flush=True)
if __name__=='__main__':asyncio.run(prepare())
