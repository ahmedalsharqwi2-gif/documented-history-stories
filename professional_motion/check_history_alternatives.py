"""Check alternate public references without evading a refusing source."""
import hashlib,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
URLS=['https://en.wikipedia.org/wiki/Great_Pyramid_of_Giza','https://egymonuments.gov.eg/monuments/the-great-pyramid/','https://www.smithsonianmag.com/history/the-worlds-oldest-papyrus-and-what-it-can-tell-us-about-the-great-pyramids-180956597/']
def read(url):
 try:
  r=requests.get(url,timeout=40,headers={'User-Agent':'ArabicHistoryDocumentary/2.0 (public reference checking)'});s=BeautifulSoup(r.text,'html.parser');title=s.title.get_text(' ',strip=True) if s.title else ''
  result={'url':url,'http_status':r.status_code,'title':title,'final_url':r.url}
  if r.status_code!=200:return result
  for e in s(['script','style','nav','header','footer','aside']):e.decompose()
  body=s.find(id='mw-content-text') or s.find('article') or s.find('main') or s
  text=' '.join(p.get_text(' ',strip=True) for p in body.find_all('p') if len(p.get_text(' ',strip=True))>80)
  result.update(body_sha256=hashlib.sha256(text.encode()).hexdigest(),body_words=len(text.split()),quote=' '.join(text.split()[:170]))
  return result
 except Exception as error:return {'url':url,'error_class':type(error).__name__}
def main():
 rows=list(ThreadPoolExecutor(3).map(read,URLS));p=Path('professional_motion/delivery');p.mkdir(exist_ok=True);(p/'alternative-reference-check.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()
