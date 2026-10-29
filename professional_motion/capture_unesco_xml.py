"""Read UNESCO's documented public World Heritage data feed; no generation."""
import hashlib,json,re
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
from bs4 import BeautifulSoup
URL='https://whc.unesco.org/en/list/xml/'

def main():
 p=Path('professional_motion/delivery');p.mkdir(exist_ok=True)
 try:
  response=requests.get(URL,timeout=45,headers={'User-Agent':'ArabicDocumentaryMotion/2.0'});response.raise_for_status();tree=ET.fromstring(response.content)
  for row in tree.iter():
   if row.tag.rsplit('}',1)[-1]!='row':continue
   data={c.tag.rsplit('}',1)[-1]:''.join(c.itertext()).strip() for c in row}
   if data.get('id_number')!='86':continue
   text=BeautifulSoup(data.get('short_description',''),'html.parser').get_text(' ',strip=True);words=text.split()
   report={'source_url':URL,'canonical_property_url':'https://whc.unesco.org/en/list/86/','source_response_sha256':hashlib.sha256(response.content).hexdigest(),'property_id':'86','title':BeautifulSoup(data.get('site',''),'html.parser').get_text(' ',strip=True),'quote':' '.join(words[:170]),'quote_complete':len(words)<=170,'fields':{k:data.get(k) for k in ['date_inscribed','category','region','states']},'source_generation_calls':0}
   (p/'unesco-public-data.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));return
  raise ValueError('Official public feed has no property 86')
 except Exception as error:
  (p/'xml-source-failure.json').write_text(json.dumps({'error_class':type(error).__name__,'http_status':getattr(getattr(error,'response',None),'status_code',None),'raw_body_included':False}));raise
if __name__=='__main__':main()
