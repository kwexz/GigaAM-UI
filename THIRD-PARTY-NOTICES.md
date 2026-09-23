# Third-party components

What the app downloads or bundles, where it comes from, under which license.
Our own code is MIT (see LICENSE when added); below are third parties.

## Shipped in our release artifacts (engine packs, UI bundle)

| Component | License | Source |
|---|---|---|
| PyTorch (+ torchaudio) | BSD-style | https://pytorch.org |
| transformers (HF) | Apache-2.0 | https://github.com/huggingface/transformers |
| GigaAM-v3 model + code | MIT | https://huggingface.co/ai-sage/GigaAM-v3 |
| Silero VAD | MIT | https://github.com/snakers4/silero-vad |
| soundfile / libsndfile | BSD / LGPL-2.1 | https://github.com/bastibe/python-soundfile |
| PySide6 (Qt) | LGPL-3.0 | https://www.qt.io |
| hydra-core, omegaconf, sentencepiece | MIT / Apache-2.0 | PyPI |

## Downloaded from upstream, never re-hosted

| Component | License | Source |
|---|---|---|
| FFmpeg builds (Windows: Gyan, macOS: evermeet) | GPL (includes x264/x265) | https://ffmpeg.org/download.html |

FFmpeg archives are fetched from their official builds and hash-pinned in
`manifest.json`. We do not redistribute FFmpeg binaries: GPL obligations
(source availability) stay with the upstream distributors linked above.

## Fetched at runtime from Hugging Face

| Component | License | Source |
|---|---|---|
| GigaAM-v3 weights (`ai-sage/GigaAM-v3`) | MIT | https://huggingface.co/ai-sage/GigaAM-v3 |
| Silero VAD weights | MIT | via `silero-vad` package |

No gated models remain in the pipeline: no accounts, no tokens required.
