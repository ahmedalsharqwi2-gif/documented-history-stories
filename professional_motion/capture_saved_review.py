"""Capture source support for one exact saved draft; no paid generation."""
import argparse,copy,hashlib,json,re,subprocess
from . import editorial as e

def git(*args):return subprocess.check_output(['git',*args])

STAGE='initialization'

def capture(run,topic,digest):
    global STAGE
    out=e.ROOT/'delivery';out.mkdir(exist_ok=True)
    STAGE='fetch-saved-draft'
    if not re.fullmatch(r'[0-9]+',run) or not re.fullmatch(r'[0-9a-f]{64}',digest):raise ValueError('Invalid bounded draft reference')
    git('fetch','origin','refs/heads/codex/professional-review-run-'+run)
    raw=git('show','FETCH_HEAD:professional_motion/delivery/last-draft.json')
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Saved draft checksum differs from the reviewed reference')
    draft=json.loads(raw)
    if draft.get('canonical_subject')!=topic:raise ValueError('Saved draft does not match the exact canonical source topic')
    row=next(x for x in json.loads((e.ROOT/'catalog.json').read_text())['history'] if x['key']==topic)
    (out/'last-draft.json').write_bytes(raw)
    STAGE='read-official-source'
    text=e.evidence(row['url'])
    STAGE='validate-saved-draft'
    story=e.validate(copy.deepcopy(draft),'history',row)
    STAGE='attach-source-excerpts'
    e.attach_evidence(story,text)
    quotes=[{'scene':i+1,'excerpt_id':x['evidence_excerpt_id'],'quote':x['evidence_quote'],'authored_claim':x['narration']} for i,x in enumerate(story['scenes'])]
    words=text.split();focus=[]
    for kind,pattern in [('antiquities_law',r'\b117\b'),('whole_property_area',r'\b80(?:\s*%|\s+per\s+cent|\s+percent)')]:
        match=re.search(pattern,text,re.I)
        if not match:continue
        before=len(text[:match.start()].split());start=max(0,before-12)
        focus.append({'kind':kind,'quote':' '.join(words[start:start+30])})
    if sum(len(x['quote'].split()) for x in quotes+focus)>180:raise ValueError('Source quotation budget exceeded')
    out=e.ROOT/'delivery';out.mkdir(exist_ok=True);(out/'last-draft.json').write_bytes(raw)
    report={'source_run':run,'topic_key':topic,'draft_sha256':digest,'source_url':row['url'],'source_body_sha256':hashlib.sha256(text.encode()).hexdigest(),'source_support':quotes,'focus_quotes':focus,'factual_review_pending':True,'no_voice_generated':True}
    (out/'source-support.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--topic',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    try:capture(a.run,a.topic,a.sha256)
    except Exception as error:
        out=e.ROOT/'delivery';out.mkdir(exist_ok=True)
        report={'stage':STAGE,'error_class':type(error).__name__,'http_status':getattr(getattr(error,'response',None),'status_code',None),'validation':str(error)[:220] if isinstance(error,ValueError) else None,'source_generation_calls':0}
        (out/'capture-failure.json').write_text(json.dumps(report,indent=2))
        raise
