# Complete vector-motion history preview

Manual workflow: **Complete Motion Episode**. Production publishing workflows stay paused.

The run prepares a short source-based Egyptian Dunkirk script, generates four new VoiceTut Mohammed narration chunks in parallel, aligns actual generated speech, renders 1080×1920/30fps SVG motion graphics with Remotion, and mixes the narration with a restrained existing music bed and original transition sweeps. No stock photos or external image generation service are needed.

Each expected word has a timed entrance and active-word emphasis. Timing uses Whisper-small exact anchors, number expansion within recognized spans, and close long-word spelling matches in equal-length blocks. Exact and approximate matches are reported separately; remaining tokens use bounded interpolation. Low timing-anchor coverage stops the run. The map uses the existing Natural Earth coastline; ship placements and routes are schematic.

The script provider is reported honestly: an available Gemini key can produce a constrained rewrite; otherwise the prepared source-based script is used. The topic is deliberately Dunkirk for this preview. This is not yet a general topic-to-motion-scenes generator.

Outputs: playable MP4, four scene JPEGs, exact script and sources, alignment metrics, voice provenance and video verification, committed to a unique result branch after successful rendering. No social posting occurs.

Quality must be judged from the produced preview. Frame-perfect word timing and historical visual detail still need human review.

## Iterate without regenerating the voice

**Motion Episode Revision** downloads the prepared script and the four accepted voice artifacts from a source run. It checks out the current main branch, realigns the same audio and renders the revised composition. The result records both the render-source commit and narration-source run. This separates graphic iteration from slow CPU speech generation.

The first history pilot uses source run `39468830702`. A manual revision can specify a different completed source run. Four still frames can also be inspected through **Motion Scene Review**, whose synthetic timestamps are clearly labelled and are not the final audio alignment.
