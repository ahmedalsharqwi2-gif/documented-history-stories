"""Read-only validation of public historical sources; no credentials required."""
import json,os,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
urls=['https://smarthistory.org/the-pantheon/','https://whc.unesco.org/en/list/86/','https://whc.unesco.org/en/list/311/','https://whc.unesco.org/en/list/164/','https://whc.unesco.org/en/list/xml/','https://www.khanacademy.org/humanities/ancient-art-civilizations/roman/middle-empire/a/the-pantheon']
def one(url):
 try:
  r=requests.get(url,timeout=35,headers={'User-Agent':'ArabicDocumentaryMotion/2.0'});s=BeautifulSoup(r.text,'html.parser');article=s.find('article') or s.find('main') or s
  return {'url':url,'status':r.status_code,'final_url':r.url,'title':s.title.get_text(' ',strip=True) if s.title else '', 'body_characters':len(' '.join(article.stripped_strings)),'xml_rows':r.text.count('<row>') if '/xml/' in url else None}
 except requests.RequestException as e:return {'url':url,'error_class':type(e).__name__}
rows=list(ThreadPoolExecutor(4).map(one,urls));p=Path('history-sources.json');p.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
def git(*args,data=None):return subprocess.check_output(['git',*args],input=data).decode().strip()
b=git('hash-object','-w',str(p));tree=git('mktree',data=('100644 blob '+b+'\thistory-sources.json\n').encode());c=git('-c','user.name=source-check-bot','-c','user.email=bot@users.noreply.github.com','commit-tree',tree,'-m','Public historical source availability [skip ci]');git('push','origin',c+':refs/heads/codex/history-sources-'+os.environ['GITHUB_RUN_ID'])
