"""Correct sourced Segovia facts before publication; edit the same three Buffer posts."""
import hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from . import editorial as e
import requests
from scripts.daily_schedule import validate_slot
IDS={'youtube':'6ae48f48abdb62a0e37cc839','facebook':'6ae48f4ae560b6bf642a6b22','instagram':'6ae48f4de560b6bf642a6bc5'}
DUE='2026-10-30T15:00:00Z';SLOT='daily-2026-10-30'
def query(text):
 key=os.environ['BUFFER_API_KEY']
 response=requests.post('https://api.buffer.com',headers={'Authorization':'Bearer '+key},json={'query':text},timeout=60)
 try:payload=response.json()
 except ValueError:payload={'errors':[{'message':'Non-JSON provider response'}]}
 if response.status_code!=200 or payload.get('errors'):
  out=Path('professional_motion/delivery');out.mkdir(exist_ok=True)
  errors=[str(e.get('message','Provider error')).replace(key,'[redacted]')[:600] for e in payload.get('errors',[])]
  (out/'correction-error.json').write_text(json.dumps({'http_status':response.status_code,'messages':errors},ensure_ascii=False,indent=2))
  raise RuntimeError('Buffer correction API failed; safe provider details retained in correction-error.json')
 return payload['data']

def posts():
 validate_slot(DUE);rows={}
 bindings=json.loads(Path('config/professional_destinations.json').read_text())['buffer_channel_ids']
 for service,identifier in IDS.items():
  r=query('query { post(input:{id:'+json.dumps(identifier)+'}) {id channelId status dueAt assets {id source}} }')['post']
  if r['id']!=identifier or r['channelId']!=bindings[service] or r['status']!='scheduled' or datetime.fromisoformat(r['dueAt'].replace('Z','+00:00'))!=datetime.fromisoformat(DUE.replace('Z','+00:00')):raise ValueError('Existing post/channel/schedule changed; refuse correction')
  rows[service]=r
 return rows

def prepare():
 posts();data=e.registry();episode=next(r for r in data['episodes'] if r['slot']==SLOT);story=episode['story']
 if story['topic_key']!='segovia-aqueduct-unesco':raise ValueError('Wrong episode')
 text=e.evidence(story['source']['url'])
 if '128 pillars' not in text:raise ValueError('Official source does not support the reviewed correction')
 story['scenes'][0]['narration']=story['scenes'][0]['narration'].replace('فوق السحاب','فوق الأقواس')
 story['scenes'][4]['narration']='في أوطى نقطة من الوادي، اليونسكو بتسجل ارتفاع القنطرة بثمانية وعشرين متراً ونصف المتر فوق الأرض. وبحسب وصفها، صفوف الأقواس شايلها 128 دعامة. الأرقام دي بتوضح حجم المنشأ اللي باقي لحد النهارده، وبتخلينا نفرق بين وصف الأثر نفسه وبين أي مبانٍ تانية اتذكرت في نفس الصفحة.'
 story['scenes'][5]['narration']='لما تتفرج على القنطرة، بص للمجرى اللي فوق صفوف الأقواس. الفكرة الأساسية للقناطر المائية هي نقل الميه عبر اختلافات في مستوى الأرض. وفي سيغوفيا، المصدر بيسجل ارتفاع المنشأ وطوله وتكوين الأقواس، ودي تفاصيل نقدر نشرحها من غير ما نفترض إن التصميم منع كل تسريب أو ركود.'
 excerpts=e.excerpts(text);idx=next(i for i,x in enumerate(excerpts) if '128' in x);story['scenes'][4]['evidence_excerpt_id']=idx;e.attach_evidence(story,text)
 story['post_edit_review']={'reviewer':'Codex','checks':['Correct the pillar count to the official 128','Remove the unsupported guarantee against all leaks and stagnation','Keep source attribution and distinguish source figures from generic aqueduct function'],'source_body_sha256':hashlib.sha256(text.encode()).hexdigest()}
 episode.update(story=story,status='correction_pending',correction_original_video_sha256=episode['video_sha256']);e.save(data)
 out=Path('professional_motion/delivery');out.mkdir(exist_ok=True);(out/'story.json').write_text(json.dumps(story,ensure_ascii=False,indent=2))
 print('Source-checked same-episode correction prepared; original Buffer IDs retained')

def update():
 before=posts();run=os.getenv('CORRECTED_MEDIA_RUN') or os.environ['GITHUB_RUN_ID'];subprocess.run(['git','fetch','origin','refs/heads/codex/professional-video-'+run],check=True)
 ref=subprocess.check_output(['git','rev-parse','FETCH_HEAD'],text=True).strip()
 out=Path('professional_motion/output');out.mkdir(exist_ok=True);delivery=Path('professional_motion/delivery');delivery.mkdir(exist_ok=True)
 video=out/'corrected.mp4';video.write_bytes(subprocess.check_output(['git','show',ref+':review-1080p.mp4']))
 report=json.loads(subprocess.check_output(['git','show',ref+':verification.json']));checksum=hashlib.sha256(video.read_bytes()).hexdigest()
 data=e.registry();episode=next(r for r in data['episodes'] if r['slot']==SLOT)
 if episode['video_sha256']!=checksum or report['topic_key']!=episode['story']['topic_key'] or not 120<=report['duration']<180:raise ValueError('Corrected movie verification mismatch')
 subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True)
 from film_factory.buffer import ContentPublisher
 os.environ['PRODUCTION_MEDIA_ID']=SLOT+'-corrected';url=ContentPublisher()._release_asset_url(video)
 posts()  # Recheck the deadline and existing scheduled IDs after media upload.
 episode['media_correction']={'status':'updating_existing_posts','old_post_ids':IDS,'corrected_video_sha256':checksum,'media_url':url};e.save(data);subprocess.run([sys.executable,'-m','professional_motion.persist_state'],check=True)
 for service,identifier in IDS.items():
  mutation='mutation { editPost(input:{id:'+json.dumps(identifier)+', assets:[{video:{url:'+json.dumps(url)+'}}], mode:customScheduled, dueAt:'+json.dumps(DUE)+'}) { ... on PostActionSuccess {post {id channelId status dueAt assets {id source}}} ... on MutationError {message} } }'
  result=query(mutation)['editPost'];r=result.get('post')
  (delivery/('edit-response-'+service+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
  if not r or r['id']!=identifier:raise RuntimeError('Buffer did not confirm editing the existing post')
 after=posts();receipts={}
 (delivery/'asset-update-observations.json').write_text(json.dumps(after,ensure_ascii=False,indent=2))
 for service,r in after.items():
  if not any(a.get('source')==url for a in r['assets']):raise ValueError('Buffer asset source does not match the corrected MP4')
  receipts[service]={'id':r['id'],'channel_id':r['channelId'],'scheduled_at':r['dueAt'],'status':r['status'],'media_url':url,'video_sha256':checksum,'verified_at':datetime.now(timezone.utc).isoformat(),'same_post_updated':True}
 episode.update(status='scheduled',receipts=receipts,publication_video_sha256=checksum);episode['media_correction']['status']='verified';e.save(data)
 stock=Path('state/publication_stock.json');s=json.loads(stock.read_text());s['slots']['stock 2026-10-30 17 Cairo'].update(receipts=receipts,confirmed=True);stock.write_text(json.dumps(s,ensure_ascii=False,indent=2))
 (delivery/'publication-result.json').write_text(json.dumps({'due_at':DUE,'scheduled':True,'receipts':receipts,'existing_post_ids_unchanged':True},ensure_ascii=False,indent=2));subprocess.run([sys.executable,'-m','professional_motion.persist_state'],check=True)
 print(json.dumps(receipts,ensure_ascii=False))
if __name__=='__main__':prepare() if sys.argv[1]=='prepare' else update()
