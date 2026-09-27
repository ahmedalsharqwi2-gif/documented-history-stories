# Reference audio for Coqui XTTS-v2

ضع هنا ملف `voice_reference.wav` لاختبار استنساخ الصوت.

## المواصفات الموصى بها

- متحدث واحد فقط، وبموافقة صريحة من صاحب الصوت.
- مدة 6–15 ثانية؛ جملة أو جملتان باللغة العربية الفصحى.
- صوت واضح بلا موسيقى أو صدى أو ضوضاء أو أصوات خلفية.
- لا تقرأ أرقاماً أو أسماءً صعبة في العينة المرجعية.
- WAV، قناة واحدة، 16 أو 24 kHz، PCM 16-bit.
- لا تضف مؤثرات أو ضغطاً قوياً أو silence طويلاً في البداية والنهاية.

## تحويل ملف موجود

```bash
ffmpeg -i input.mp3 -ac 1 -ar 24000 -sample_fmt s16 assets/voice_reference.wav
```

## اختبار الملف

```bash
ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels \\
  -of default=noprint_wrappers=1 assets/voice_reference.wav
```

لا ترفع الملف إلى GitHub إذا كان يحتوي صوتاً شخصياً أو غير مصرح بنشره.
