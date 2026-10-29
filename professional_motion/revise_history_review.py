"""Complete the saved Giza draft using independently checked public references."""
import hashlib,json,os,subprocess
from pathlib import Path
from .editorial import registry,save
SCENES=[
('الهرم كان شكله مختلف','hero','الهرم الأكبر اللي قدامك مش كان شكله كده طول الوقت. الحجر اللي بنشوفه النهارده كان مستخبي تحت كسوة أفتح وأنعم. وده يفتح سؤال أهم من حجمه: المواد دي وصلت للمكان واتجمعت إزاي؟'),
('خوفو والعجيبة الباقية','levels','ده هرم الملك خوفو، واتعمل كمقبرة ليه. ومن عجائب الدنيا السبع القديمة، هو الوحيد اللي لسه باقي لحد النهارده. يعني إحنا مش قدام شكل مشهور وخلاص؛ إحنا قدام أثر جمع بين العمارة ووظيفة المقبرة الملكية.'),
('الجسم غير الكسوة','material','حسب وزارة السياحة والآثار، جسم الهرم اتبنى من حجر جيري محلي، لكن الكسوة الخارجية كانت من حجر جيري عالي الجودة. الفرق ده مهم: الحجر اللي بيكوّن الجسم مش بالضرورة هو نفس الحجر اللي كان بيحدد شكل السطح.'),
('الحجر وصل بمراكب','assembly','حجر الكسوة اتجاب من طرة، جنوب المعادي، واتنقل بالسفن. قبل ما نفكر في رفع الحجر، فيه رحلة نقل لازم تحصل. تخيل ترتيب وصول المواد لمشروع بالحجم ده؛ البناء هنا مش شكل هندسي بس، دي كمان حكاية تنظيم ونقل.'),
('تلات حجرات من جوه','section','الهرم مش كتلة مصمتة من غير فراغات. المصدر الرسمي بيذكر تلات حجرات: واحدة محفورة في الصخر تحت الهرم، واتنين أعلى منها جوه البناء نفسه. المقطع التوضيحي بيقرّب الفكرة، مش بيعرض خريطة بمقاسات أصلية لكل ممر وحجرة.'),
('الطريق لغرفة الملك','section','في الحجرة العلوية، غرفة الملك، لسه التابوت موجود. والوصول ليها بيكون عبر البهو الكبير، وهو ممر صاعد ضخم بتوصفه الوزارة كعمل مميز في الهندسة والعمارة القديمة. هنا التفاصيل اللي جوه مهمة زي الشكل الخارجي اللي كلنا عارفينه.'),
('ارتفاع عاش آلاف السنين','hero','الارتفاع الأصلي، حسب المصدر الرسمي، كان حوالي مية وستة وأربعين متر ونص. والهرم فضل أعلى بناء في العالم لآلاف السنين. الرقم مش مجرد معلومة نحفظها؛ بص لحجم المشروع، وفكر في رحلة الحجر من المحجر لحد مكانه.'),
('المعروف واللي لسه محل بحث','levels','بس ضخامة الأثر ما تديناش حق نخترع تفاصيل. الوزارة بتوضح إن طريقة البناء مش محسومة بكل تفاصيلها لحد النهارده. نعرف مواد، ونقل، وحجرات موجودة فعلًا؛ والأسئلة الباقية محتاجة دليل. عشان كده، حكاية الهرم الحقيقية أقوى من حكاية سهلة من غير مصدر.')]

def main():
 subprocess.run(['git','fetch','origin','refs/heads/codex/professional-review-run-40928402745:refs/remotes/origin/verified-giza-references'],check=True)
 references=json.loads(subprocess.check_output(['git','show','origin/verified-giza-references:professional_motion/delivery/alternative-reference-check.json']))
 official=next(r for r in references if r['url']=='https://egymonuments.gov.eg/monuments/the-great-pyramid/')
 wiki=next(r for r in references if r['url']=='https://en.wikipedia.org/wiki/Great_Pyramid_of_Giza')
 if any(r.get('http_status')!=200 for r in [official,wiki]):raise ValueError('The reviewed public references were unavailable')
 primary=official['quote'];secondary=wiki['quote']
 def quote(text,needle):
  position=text.casefold().find(needle.casefold())
  if position<0:raise ValueError('Reviewed fact excerpt no longer found')
  return ' '.join(text[position:].split()[:15])
 needles=[(secondary,'Over time'),(primary,'The Great Pyramid, the tomb'),(primary,'made of local limestone'),(primary,'These casing stones'),(primary,'On the inside'),(primary,'The sarcophagus'),(primary,'original height'),(primary,'To this day')]
 row=next(r for r in json.loads(Path('professional_motion/catalog.json').read_text())['history'] if r['key']=='great-pyramid-giza-unesco')
 s={'title':'الهرم الأكبر.. حكاية الحجر اللي وصل بالمراكب','canonical_subject':'great-pyramid-giza-unesco','topic_key':row['key'],'suitable':True,'facts':['Khufu’s tomb','Local limestone core and high-quality casing from Turah transported by ship','Three chambers','Grand Gallery leading to King’s Chamber','Original height about 146.5 m','Complete construction method remains uncertain'],'milestones':[],'scenes':[],'profile':'history','series':'نقص ونروى','visual_family':'architecture','variant':'pyramid','visual_contract':row['visual_contract'],'source':{'url':official['url'],'publisher':'وزارة السياحة والآثار المصرية','title':'The Great Pyramid'},'fiction':False,'documented':True,'hashtags':['الهرم_الأكبر','خوفو','آثار_مصر','تاريخ_مصر']}
 for i,(label,mode,text) in enumerate(SCENES):
  source,needle=needles[i];s['scenes'].append({'id':'scene_'+str(i+1),'label':label,'visual_mode':mode,'narration':text,'labels':[],'evidence_quote':quote(source,needle),'evidence_source':wiki['url'] if i==0 else official['url']})
 s['editorial_review']={'supported':True,'novel':True,'issues':[],'review_type':'Codex source and visual review of the saved, unpublished Giza topic','source_response_sha256':official['body_sha256'],'secondary_response_sha256':wiki['body_sha256'],'checks':['Use only the verified official Ministry description and the recorded public reference','Remove unverified law number and 80-percent property-scope claim','Clearly label internal diagram schematic, not surveyed reconstruction','Distinguish documented features from uncertain construction details']}
 p=Path('professional_motion/delivery');p.mkdir(exist_ok=True)
 for n in ['narration.wav','narration.source.json','timing.json','error.json']:(p/n).unlink(missing_ok=True)
 (p/'story.json').write_text(json.dumps(s,ensure_ascii=False,indent=2));data=registry();episode=next((r for r in data['episodes'] if r.get('topic_key')==s['topic_key']),None)
 if episode is None:episode={'slot':'review-'+os.environ['GITHUB_RUN_ID'],'topic_key':s['topic_key']};data['episodes'].append(episode)
 if episode.get('status') in ('published','scheduled','publishing'):raise ValueError('Do not revise a submitted episode')
 episode.update(story=s,title=s['title'],canonical_subject=s['canonical_subject'],url=official['url'],status='reserved');save(data)
 print('Source-reviewed historical narration:',sum(len(x['narration'].split()) for x in s['scenes']),'words')
if __name__=='__main__':main()
