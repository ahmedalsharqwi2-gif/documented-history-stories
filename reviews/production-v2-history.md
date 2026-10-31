# History production v2 candidate

This branch adds an opt-in renderer and leaves the existing production workflows and all topic histories, video fingerprints and publication receipts intact. It is not activated for daily production.

## Actual visual changes

`--pipeline v2` installs deterministic stone/timber surface detail, one 1024px soft shadow map, a warm key and cool rim light, and a restrained dolly/arc camera move. It does not replace the authored geometry or source contracts. The two-tier Segovia aqueduct remains two tiers, with no dome or invented building added. Text and captions are composited after the 3D frame and remain independent of the camera.

Renderer defaults remain legacy. V2 defaults to `professional_motion/output/v2`. `--delivery-dir` and `--output-dir` support isolated review inputs and outputs. Both inputs and timing hashes still have to match. Renderer metadata records the selected pipeline and cinema status. An interrupted encoder is stopped during cleanup.

Example, from repository root:

```sh
node professional_motion/render.mjs --pipeline v2 --review --style reference \
  --delivery-dir /absolute/path/to/matched-delivery \
  --output-dir /absolute/path/to/review-output
```

The renderer produces silent visual frames; a matched, measured narration and the separate validated finishing step are required for a complete review film. Rendering alone is not a publication or cutover approval.

## Verification and limitations

- `node tests/test_history_cinema_v2.mjs`: 2 passed. Tests verify deterministic shading, no changes to source geometry buffers, two-tier preservation, camera movement and bounded shadow resources.
- Existing selected Python regressions: 43 passed, 3 failed. All failures concern the existing daily scheduling window, which always returns eligible and uses tomorrow's due time. This renderer change does not silently alter that running path.
- Eight 1080x1920 v2 Segovia still frames and a new 32-second/30fps silent MP4 technical preview rendered through real Chromium/WebGL. FFprobe counted all 960 frames and a full FFmpeg video decode passed. Beginning, middle and final frames were inspected: subject remains framed, two tiers are visible, and review text/source attribution remain readable. The preview explicitly states that new narration is unavailable; it has no audio stream and is not a complete narrated acceptance film. See `production-v2-history-technical.json` for exact evidence and checksum.
- The original gold logo is not attached as a readable file; `original_logo_installed` remains false. No substitute logo was generated.
- The archived complete Segovia narration from run 41053670613 matches its own story/audio hashes and lasts 153.24 seconds, but contains factual statements corrected in the current registry. It is unsuitable as an accurate acceptance film and has not been republished or treated as a new topic.
- Later matched Arles and El Jem archives were also inspected. Arles conflates the collective monument dating with the amphitheatre; El Jem narration says restorations did not preserve the structural core. These were rejected as accurate acceptance inputs, rather than reused to claim completion.
- New Gemini narration is unavailable in this environment. No full newly narrated v2 film has passed the channel acceptance gate; the old workflow must remain in place until full validation and an explicit cutover.

No topic registry entry, existing video checksum, receipt, social post or old scheduled workflow was changed by the renderer work.
