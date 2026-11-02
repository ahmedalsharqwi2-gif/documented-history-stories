"""Bounded read-only reconciliation evidence for a retained historical slot."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from .publish import query,destinations,instant
from .health import read_json,write_json,target_due

def main():
 request=read_json('.github/remotion-health-request.json',{})
 day=instant(request['date']+'T12:00:00Z').date();due=target_due(day)
 fields='id channelId status dueAt sentAt externalLink assets{source}'
 try:schema=query('query {__type(name:"Post"){fields{name type{kind name ofType{kind name}}}}}')
 except RuntimeError:schema={}
 selected=[]
 for f in (schema.get('__type') or {}).get('fields',[]):
  t=f['type'];t=t.get('ofType') if t['kind']=='NON_NULL' else t
  if t and t.get('kind') in ('SCALAR','ENUM') and any(k in f['name'].lower() for k in ('error','fail','reason','text','title')):selected.append(f['name'])
 fields+=' '+' '.join(selected)
 report={'date':str(day),'read_only':True,'generation_calls':0,'publication_mutations':0,'post_fields':selected,'channels':{},'known_posts':{},'errors':[]}
 cache={}
 def inspect(post):
  if not post:return None
  result={k:v for k,v in post.items() if k!='assets'};result['assets']=[]
  for asset in post.get('assets') or []:
   url=asset.get('source');u=urlparse(url or '');proof={'host':u.hostname,'source_url_sha256':hashlib.sha256((url or '').encode()).hexdigest()}
   if url not in cache:
    record={}
    if u.scheme=='https' and u.hostname and u.hostname not in ('localhost','127.0.0.1','169.254.169.254'):
     try:
      with requests.get(url,stream=True,timeout=60) as response:
       response.raise_for_status();digest=hashlib.sha256();size=0
       with tempfile.NamedTemporaryFile(suffix='.mp4') as movie:
        for chunk in response.iter_content(1024*1024):
         size+=len(chunk)
         if size>150*1024*1024:raise ValueError('Historical media exceeds bounded diagnostic size')
         digest.update(chunk);movie.write(chunk)
        movie.flush();record={'sha256':digest.hexdigest(),'bytes':size}
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',movie.name],capture_output=True,text=True,timeout=45)
        if probe.returncode==0:record['duration']=float(json.loads(probe.stdout)['format']['duration'])
     except Exception as exc:record['unavailable']=type(exc).__name__
    cache[url]=record
   result['assets'].append({**proof,**cache[url]})
  return result
 mapping=destinations(os.environ['REMOTION_PROFILE'])
 for service,d in mapping.items():
  # Omitting the status filter is essential: the regular queue excludes failed posts.
  text='query {posts(first:100,input:{organizationId:'+json.dumps(d['organization'])+',filter:{channelIds:['+json.dumps(d['channel'])+'],dueAt:{start:'+json.dumps((due.replace(second=0)).isoformat())+',end:'+json.dumps((due.replace(second=1)).isoformat())+'}}}){edges{node{'+fields+'}} pageInfo{hasNextPage}}}'
  try:
   rows=query(text)['posts']
   if rows['pageInfo']['hasNextPage']:raise ValueError('Historical diagnostic requires complete bounded pagination')
   report['channels'][service]=[inspect(e['node']) for e in rows.get('edges',[])]
  except Exception as exc:report['errors'].append(service+': '+type(exc).__name__)
 latest=read_json('reviews/daily_health/latest.json',{});ids=set()
 for rows in latest.get('observed_receipts',{}).values():
  for row in rows:ids.add(row['id'])
 for file in ('state/professional_topics.json','state/stickman_publications.json','state/remotion_registry.json'):
  data=read_json(file,{})
  groups=[data] if isinstance(data,list) else [data.get(k,{}) for k in ('episodes','publications','slots')]
  for group in groups:
   for entry in (group.values() if isinstance(group,dict) else group):
    if not isinstance(entry,dict) or not str(entry.get('due_at','')).startswith(str(day)):continue
    for row in (entry.get('receipts') or entry.get('posts') or {}).values():
     if isinstance(row,dict) and row.get('id'):ids.add(row['id'])
 for identifier in sorted(ids):
  try:report['known_posts'][identifier]=inspect(query('query {post(input:{id:'+json.dumps(identifier)+'}){'+fields+'}}')['post'])
  except Exception as exc:report['known_posts'][identifier]={'unavailable':type(exc).__name__}
 path='reviews/daily_health/legacy-reconciliation/'+str(day)+'-'+os.environ['GITHUB_RUN_ID']+'.json'
 write_json(path,report);Path('health-output').mkdir(exist_ok=True);Path('health-output/legacy-diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report':path,'channels':{s:len(rows) for s,rows in report['channels'].items()},'errors':report['errors'],'publication_mutations':0}))

if __name__=='__main__':main()
