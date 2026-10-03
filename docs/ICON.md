# EnglishLinks icon

Original icon generated for EnglishLinks with the built-in image generation
tool on 2026-10-01 (Asia/Yekaterinburg).

- `images/englishlinks-icon.png`: 400×400 PNG for CurseForge and README.
- `../EnglishLinks/Icon.tga`: 256×256 uncompressed 24-bit true-color TGA for WoW,
  top-left origin (descriptor `0x20`) with rows stored top-to-bottom.

On 2026-10-03 the user reported that the addon-list icon appeared upside down
in Forever. The original TGA used bottom-left origin and bottom-to-top rows.
It was repacked with top-to-bottom rows and the matching origin flag; decoding
both files with a format-aware reader produces identical pixels. This addresses
the observed orientation mismatch without changing the artwork. Live-client
confirmation of the repacked texture is still pending.

The generated composition was resized and format-converted for these targets;
its artwork was not retouched. The game screenshot is a separate user-provided
image, not generated artwork.

Prompt:

Use case: logo-brand. Create an original square app icon for EnglishLinks, a World of Warcraft addon that makes clickable chat links display English names. A richly painted fantasy-game inventory icon: two bold interlocking gold chain links inside a compact deep-blue speech bubble, a small elegant parchment tab bearing exactly the uppercase letters EN. Dark navy background, warm antique gold metal, a subtle cyan magical glow. Strong simple centered silhouette, readable at 64 pixels, crisp polished edges, restrained texture, full-bleed square composition. No outer blank margins, no mockup, no extra text, no Warcraft logo, no flags. This is an original addon emblem suitable for a CurseForge project avatar. Opaque background.
