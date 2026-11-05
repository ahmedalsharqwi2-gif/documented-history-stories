# Abu Simbel — complete narrated approval review

This work is review-only. It does not change daily workflows, publication destinations, credentials, or schedules. No publisher is invoked. The retained episode is `config/reviews/abu-simbel-nine-beats.json`.

## Editorial source and archival provenance

Primary historical source: UNESCO World Heritage Centre, **Working Together: Abu Simbel**, https://whc.unesco.org/en/activities/1296 . The story concerns the rescue campaign, dismantling, relocation to higher ground and reassembly of the original temples; the historical chronology is 1960–1968. The brand is **نقص ونروي**, Noto Naskh Arabic, dark green/cream with one gold title word.

The original eight-paragraph episode was retained, with the hook `أبو سمبل مش مكانه.` added at the beginning. Paragraph four is split exactly before `مش تكسير` to give nine scene changes. The flattened narration remains identical to the successfully generated Charon receipt. Structural beat identifiers do not introduce invented competing historical theories.

`remotion_motion/assets.json` pins the real archival source URLs, Commons pages, licenses, artists, source and cached image hashes. The three history caches are decoded, their bytes checked against `cache_sha256`, and converted to JPEG with Pillow. No synthetic archival event images are used. The lift image is Per-Olow Anderson/Public domain; the old-site image is Museo Egizio/CC0; the campaign document is UNESCO/Public domain. Derived images retain source records beside them.

The locator map uses the manifest's pinned Natural Earth commit and SHA-256, national polygons, and WGS84 point **31.6258°E, 22.3372°N**. It is a schematic location map; no invented river course is drawn.

## Authored visuals and actual render path

The review uses the local Remotion `LockedFilm` renderer, with actual Three.js WebGL for two Egyptian temple shots. The schematic has four seated colossi, a rock-cut facade and separate facade pieces. It has no Greek columns or pediment. Block seams are explanatory, not a survey of historical cutting boundaries. Split/reassembly motion moves actual component meshes and stays inside the measured focal stage. Archive photographs have source-preserving camera drift; this review does not claim use of an external OpenMontage render or a newly deployed hosted template.

The chronology shot explicitly connects 1960 to 1968. All nine shots were rendered as layout diagnostics and inspected. Those diagnostic props are explicitly unaligned and must never be used as a narrated final video.

## Narration and timing

The recovered voice is real Gemini **Charon**. The original WAV is preserved. Only **0.23225 seconds of initial quiet** was removed, based on this recording's silence detection and PCM inspection. No speed or pitch changes were applied. Trimmed duration: **129.20775 seconds**. This is above the 100–120-second target, and within the review contract's strict >90 and <180-second range.

Independent faster-whisper large-v3-turbo recognition used actual 16 kHz PCM, Arabic word timestamps and no script prompt. Monotonic script-character matching yields **95.4225% word coverage** and **97.6227% character coverage**, retaining the raw recognition and all unmatched words. Seventy-one captions contain at most four words. Captions are anchored phrases, not a claim of exact per-word timing. Two phrases are shorter than 0.9 seconds and remain honestly measured, without padding or retiming. The hook is 1.10 seconds.

The local assets can be recreated with `python professional_motion/prepare_abu_simbel_review_assets.py`; it verifies all pinned caches/map bytes before writing derivatives.

## Gates and reproducibility

- `node --test professional_motion/egypt_temple.test.mjs`: actual Egyptian geometry and dismantle/reassembly invariants.
- `cd remotion_motion && npx tsc --noEmit`: typecheck.
- `remotion_factory.locked_episode`: ordered narrative beats, exact unique title accent, exact opening hook, caption budget, duration and audible first frame.
- `remotion_motion/review.mjs --props <measured-props.json> --output-dir <new-dir>`: full 1080×1920, 30 fps review with audio and review watermark.
- `remotion_motion/safe_audit.mjs`: every two seconds plus every caption onset, same rendered composition and separate shaped-text masks; one reused headless browser avoids repeated launches without reducing coverage.
- `scripts/verify_safe_area.py --video <review.mp4> --manifest <audit/manifest.json> --output <new-dir>`: actual encoded pixels versus source stills, shaped text, focal scale and multi-platform interface overlays.

Encoded video/audio, all scene starts/middles/ends, final tail and transitions must pass before this review is represented as complete. Interface overlays are simulated checks, not real-device or signed-in app screenshots. The publication workflow remains unchanged, and this review is never automatically published.
