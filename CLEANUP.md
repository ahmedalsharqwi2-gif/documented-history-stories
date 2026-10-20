# تنظيف المسار الحالي

حُذفت workflows الاختبارية المكررة بعد اعتماد Charon، وأزيلت أدوات توليد VoiceTut التجريبية غير المستخدمة. تبقى جميع النسخ السابقة محفوظة في تاريخ Git. لم تُحذف فحوص ASR أو العربية أو المزامنة أو إصلاح نهاية الصوت، ولم تتغير شروط إيقاف الإنتاج أو النشر.

الملفات المحذوفة:
- `.github/workflows/accepted-voice-check.yml`
- `.github/workflows/voice-lab.yml`
- `.github/workflows/voicetut-sample.yml`
- `.github/workflows/feature-voice-auditions.yml`
- `.github/workflows/complete-voice-lab.yml`
- `.github/workflows/neural-arabic-clarity.yml`
- `.github/workflows/gemini-voice-pronunciation.yml`
- `.github/workflows/gemini-full-egyptian-narration.yml`
- `.github/workflows/voice-listening-delivery.yml`
- `.github/workflows/abu-simbel-gemini-feature.yml`
- `motion_feature/tts_worker.py`
- `motion_feature/scene_task.py`
- `motion_feature/select_voice.py`
- `audio_repair/samples.py`
- `audio_repair/gemini_voices.py`
- `audio_repair/gemini_long.py`
- `audio_repair/neural_trial.py`
- `audio_repair/listening_pack.py`
- `audio_repair/gemini_client.py`
- `voice_lab/voicetut_sample.py`
- `voice_lab/synthesize_sample.py`
- `voice_lab/egyptian-sample.txt`

حُذفت أيضًا سلاسل إعادة إنتاج نفس الحلقة التجريبية عند workflow_run، لمنع تتابع تشغيلات غير ضرورية. يظل كود الرسوم وإصلاح الصوت متاحًا.
- `.github/workflows/motion-episode-revision.yml`
- `.github/workflows/motion-complete-720.yml`
- `.github/workflows/publish-motion-delivery.yml`
- `.github/workflows/motion-quick-preview.yml`
- `.github/workflows/motion-scene-review.yml`
- `.github/workflows/feature-final-polish.yml`
- `.github/workflows/feature-number-word-review.yml`
- `.github/workflows/feature-visual-review.yml`
- `.github/workflows/gemini-feature-plan.yml`
- `.github/workflows/history-visual.yml`
- `.github/workflows/test-story-audio.yml`
- `.github/workflows/narration_sample.yml`
