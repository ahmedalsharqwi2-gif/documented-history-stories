# تجربة مصنع فيديوهات التاريخ

تجربة مستقلة داخل فرع `codex/history-motion-pilot`، لا تستدعي خطوط النشر القديمة.
أول موضوع: حجر رشيد، بمصادر المتحف البريطاني المرفقة في episodes/rosetta.json.

## التنفيذ

- محرك Motion as Code الأصلي من الحزمة المرفوعة، مع تكييف 1080×1920 وخطوط عربية ودعم Chrome على Linux.
- مشهد Three.js لحجر ثلاثي الأبعاد وإضاءة وغبار وكاميرا متحركة، وخريطة توضيحية وطبقات شرح.
- شكل الحجر والنقوش إعادة بناء توضيحية؛ ليست مسحًا ثلاثي الأبعاد أو تفريغًا للنقوش الأثرية.
- صوت مصري ar-EG-ShakirNeural عبر edge-tts، وليس الصوت الأصلي لفيديو الأخطبوط. نجاح الخدمة المجانية غير مضمون؛ فشلها يوقف التشغيل دون إخراج فيديو صامت.
- كل مشهد يُنطق كاملًا وتُقاس مدته بـWAV؛ لا يوجد تقطيع حسب عدد الحروف أو محاذاة إنجليزية للعربية.
- التخزين المؤقت للصوت مرتبط ببصمة النص والصوت والسرعة لمنع إعادة استخدام صوت قديم.
- GitHub Actions ينتج MP4 ويرفعه كـartifact للمعاينة. لا توجد جدولة أو نشر على Buffer.

## تشغيل

Python 3.12 وBun وFFmpeg وChromium مطلوبة.

```bash
pip install -r requirements.txt
cd app && bun install && bunx playwright-core install --with-deps chromium
cd ..
python scripts/prepare.py
cd app
export CHROME_PATH=$(bun -e "import {chromium} from 'playwright-core'; console.log(chromium.executablePath())")
bun run render
cd .. && python scripts/verify.py
```

المصنع هنا يبدأ من حلقة مُعدة ومراجعة. اختيار موضوع وكتابة نص جديد آليًا ونظام مراجعة ونشر متعدد القنوات مراحل لاحقة بعد اعتماد الإخراج.

ترخيص محرك mexicat/pdoom-video محفوظ في LICENSE.pdoom-engine. الخطوط Noto Sans Arabic مع ترخيصها في app/public/fonts.
