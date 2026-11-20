# Preserved materials

All listed bytes preserved at their original paths, except the Nafhamha identity receives a new rebuild_tokens member and its exact original is saved beside it as nafhamha-identity.original.json. The full original source remains on the verified backup branch and tag. Additional extracted topic identifiers are in state/legacy-topic-index.json; new reservations never overwrite that index.

| Original path | SHA256 before rebuild |
|---|---|
| `config/channel_identity.json` | `96714503c45a5854b2c095be4261b4e1af1ab150b7a37250e2553d4c7a1aa31a` |
| `config/arabic_pronunciation.json` | `0d86385ab789e20a6189ccc86119aeb2d0303e13d9b97b63703e562a6c1bf8fe` |
| `state/topic_history.json` | `3e5a8816524703e6b459e7301b51134d486e41946236a9df3d53f35b7269c18e` |
| `professional_motion/branding.json` | `6e065a88d78aa8cabfdffbb3510525ce6fc07fc44b0095176a6531aff3359c4a` |
| `history_visual/assets/Noto-Fonts-Copyright.txt` | `075f91382875da1c4b491f1facf2586f55448705133264d98ce15cab6211b125` |
| `history_visual/assets/NotoSansArabic-Bold.ttf` | `ded6fc7359ca36d15d7aab9ef0c066e21ce48b26a069994d6602fa2cb9a1b952` |
| `history_visual/assets/NotoSansArabic-Regular.ttf` | `504d7407d86875acf7d04dfaa0fd7524d0b8797723bc4aa18022f29db25b0b6e` |
| `archive/legacy-islamic/topic_history_legacy.json` | `84bb2cf60838738e89e5e5b7ae9372cace950af3fca9adba0f5bde4120012aa4` |
| `photo_motion/assets/Noto-Fonts-Copyright.txt` | `075f91382875da1c4b491f1facf2586f55448705133264d98ce15cab6211b125` |
| `photo_motion/assets/NotoSansArabic-Bold.ttf` | `ded6fc7359ca36d15d7aab9ef0c066e21ce48b26a069994d6602fa2cb9a1b952` |
| `photo_motion/assets/NotoSansArabic-Regular.ttf` | `504d7407d86875acf7d04dfaa0fd7524d0b8797723bc4aa18022f29db25b0b6e` |
| `professional_motion/fonts/OFL-IBM-Plex.txt` | `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da` |
| `professional_motion/fonts/Noto-Fonts-Copyright.txt` | `075f91382875da1c4b491f1facf2586f55448705133264d98ce15cab6211b125` |
| `professional_motion/fonts/NotoSansArabic-Bold.ttf` | `ded6fc7359ca36d15d7aab9ef0c066e21ce48b26a069994d6602fa2cb9a1b952` |
| `professional_motion/fonts/IBMPlexMono-Medium.ttf` | `a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755` |

Original logo present in checkout: no. The owner subsequently supplied inline logo references. Their original file bytes have not been exposed by the upload tool; no replacement has been drawn. See config/logo-intake.json. Original font files and their available notices remain. Charon and intended 17:00 Africa/Cairo destination names remain in config. No .mp4 files were tracked on the cloned main snapshots; no approved media was deleted from remote media branches. Legacy scheduling files are in the backup, but the new branch has only one active workflow.

## Follow-up original logo installation

Source: Owner supplied logos.zip / documented-history-stories.jpg

Canonical file: `brand/logo/logo.jpg`

SHA-256: `3641e6a62fa3efc6c266d230832c1a5987bdc700522d17c938c03845de4efd5a`

Byte-for-byte copy verified; no redraw, recolor, background removal, raster edit or vectorization. The public/brand/logo directory is a symlink to the canonical directory. Header, intro/outro and thumbnail use the same Logo component and source.
