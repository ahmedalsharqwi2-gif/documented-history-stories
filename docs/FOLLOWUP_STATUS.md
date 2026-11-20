# Follow-up execution evidence

Original owner-supplied logo is now installed byte-for-byte at `brand/logo/logo.jpg` with SHA-256 `3641e6a62fa3efc6c266d230832c1a5987bdc700522d17c938c03845de4efd5a`. `public/brand/logo` resolves to the single canonical source. Rendering uses `BrandLogo`; no redrawing, recoloring or background removal.

Local `make test`: PASS, 29 tests and TypeScript. Tests include synthetic 429/503, jitter/backoff, Retry-After across model fallback, quota limiting, voice chunk resume across fresh clients, changed voice settings, original logo hash rejection, exact script evidence, and verification/freshness selection. Gemini API calls are injected mocks in tests; no live provider was called by tests.

This commit starts an actual review-only Actions attempt using existing repository environment bindings. Local silent visual-preview render is running separately under the shared render lock. Neither attempt is yet claimed successful; terminal evidence will be appended.

Publishing remains disabled in config/release.json. Main and verified legacy backup refs are untouched.

Shared hardening applied: discovery Retry-After, RSS User-Agent/cache/delay and strict item dates, layout QA before every partial render, and run-attempt-specific provider cache saves. Local 29 mocked tests and TypeScript pass.
