# OpenMontage automatic history review

GitHub Actions produces a complete, newly written factual history film with the
repository's approved Charon voice. A pinned OpenMontage checkout supplies media
acquisition and `video_compose`; the existing factual source bank, editorial
models, voice client, API budget and measured-speech alignment are reused.

The first run starts automatically on a push to `codex/openmontage-auto-review`.
After installation on the default branch, the scheduled workflow prepares a review
at 09:00 Africa/Cairo, with DST handled by two UTC triggers and a local-time guard.
This workflow has no Buffer credential and does not publish to social platforms.
The old paused daily workflows are not reactivated.

Required existing Actions secrets: `GEMINI_API_KEY`, or the separate
`GEMINI_TEXT_API_KEY` and `GEMINI_TTS_API_KEY`. The configured writer/reviewer and
`config/accepted_voice.json` remain authoritative. There is no voice fallback.

Each date has one retained production state on `codex/openmontage-review-state`.
Acknowledged scripts and original narration are retained before rendering. An
unresolved provider request stops rather than blindly resynthesizing. Re-running
the same date resumes acknowledged work. A completed date never generates again.

Outputs: the Actions artifact contains MP4, source/ASR/compose evidence and credits;
the run summary links a downloadable MP4 on the separate review branch. This is
photo-based production: real licensed stills with authored motion and Arabic phrase
captions, not AI-generated video or newly recorded archival footage. Every scene
requires its own subject-matched high-resolution image. An over-specific shot
query can broaden to the actual named site; this is recorded as site context,
not claimed as evidence of the exact narrated detail. Subject-match count is
ranked before resolution. Original TIFF photographs are decoded and converted
to JPEG, rather than being renamed and left unreadable by the browser.
Missing source support,
failed independent review, missing media, or insufficient measured speech stops
the run. Automated checks do not establish human creative acceptance.

OpenMontage is AGPLv3; this adapter references a pinned checkout and preserves its
license. Remotion and all media retain their respective license terms. Per-photo
authors, source URLs and licenses are saved with each sample.
