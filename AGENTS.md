# AGENTS.md — giga-transcribe

Desktop app (PySide6, Windows + macOS Apple Silicon) for audio/video transcription
with GigaAM-v3 + Silero VAD. Inference runs in a downloaded engine bundle via
QProcess/JSONL, or in-process QThread over core.jobs in dev; UI never imports
torch/transformers directly.

Self-bootstrap distribution: light exe/app shows a setup page on first run
(desktop/setup_page.py over installer/setup.py) listing components, total size
and target dir; download starts only on user button. No separate installer
framework, no silent downloads.

## Permanent

- `ponytail` (full): shortest working diff, stdlib first, no unrequested abstractions.
- `HF_TOKEN` and signing certs never enter the repo; audit with `env-secrets-manager`.
- Pre-publication leak audit (tree + `--git-history` + `--entropy`) → `secrets-scan`.

## Skill routing (load one when its branch fires)

- Qt widgets, layout, states, a11y → `qt-ui-design`.
- PySide6 code review (finished GUI work) → `pyside6-reviewer`.
- torch devices (cpu/cuda/mps), inference memory, serialization → `pytorch`.
- HF download, cache, gated-repo access → `huggingface-local-models`.
- ffprobe/ffmpeg transcode, `-progress` parsing, subprocess media errors → `ffmpeg-audio-processing`.
- GitHub Actions matrix, artifacts, release pipeline → `github-actions`.
- macOS notarization/Gatekeeper failures → `asc-notarization`.
- Signing trust chain checklist → `implementing-code-signing-for-artifacts`
  (Authenticode commands verified against Microsoft Learn).
- Failing inference/packaging bug → `diagnosing-bugs`.
- New behavior (formats, protocol, downloader) → `tdd` first.
- Disputed tool behavior → `research` against primary docs.
- Finished risky diff → `code-review`.

## Out of scope

- `design-taste-frontend`, web UI skills: Qt only until the web client starts.
- `playwright`: desktop has no browser surface.
- No new skills without asking.

## Known gaps (no skill — use official docs + smoke builds)

- PySide6 + PyInstaller + torch/transformers native-lib bundling.
- Authenticode specifics beyond the checklist.
