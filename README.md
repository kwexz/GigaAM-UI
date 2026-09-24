# Giga Transcribe

> 🇷🇺 Читать на русском: [README.ru.md](README.ru.md)

Desktop app for speech-to-text on audio and video.
Local, no cloud: GigaAM-v3 model + Silero VAD, Windows and macOS Apple Silicon.

- 🎙️ Audio and video (wav, mp3, mp4, mkv and more — ffmpeg handles it all)
- 📝 Subtitle output: SRT, VTT, TXT, JSON
- 🖥️ CPU everywhere; NVIDIA CUDA and Apple Metal (MPS) where available
- 📦 Light exe/app: the heavy engine downloads itself on first launch, on button press
- 🔒 Audio never leaves your machine — everything runs locally

## Quick start (users)

1. Download the tiny setup stub from [Releases](https://github.com/kwexz/isMemory/releases):
   `GigaTranscribe-Setup-Windows.zip` or `GigaTranscribe-Setup-macOS.zip` (~12 MB).
2. Unpack, run the stub, press **"Download and install"** —
   it shows contents and total size up front, then offers **"Launch"**.
3. Open or drag & drop a file, press **"Transcribe"**.

Prefer manual setup? `GigaTranscribe-Windows.zip` / `-macOS.zip` holds the full
app (`GigaAM-UI`) with its own setup page for engine + FFmpeg.

> Builds are not code-signed yet: SmartScreen / Gatekeeper will show
> a warning (macOS: right-click → Open).

## How it works

```mermaid
flowchart LR
    subgraph stub["Setup stub (~12 MB)"]
        S[list + total + button]
    end
    subgraph app["GigaAM-UI (full app)"]
        UI[window,\nprogress, text]
    end
    subgraph data["Data folder"]
        ENG[engine-*: GigaAM-Worker\nPyTorch + GigaAM + Silero]
        FF[ffmpeg-*: ffmpeg]
    end
    S -- "download on click" --> UI
    S -- "download on click" --> ENG
    S -- "download on click" --> FF
    S -- "Launch" --> UI
    UI -- "QProcess + JSONL" --> ENG
```

Transcribing one file:

```mermaid
sequenceDiagram
    participant U as UI
    participant W as GigaAM-Worker
    participant V as Silero VAD
    participant G as GigaAM-v3
    U->>W: job.json (file, model, device)
    W->>W: ffmpeg → mono 16 kHz
    W->>V: speech regions
    V-->>W: N segments
    loop each segment
        W->>G: chunk ≤ 22 s
        G-->>W: text + timestamps
        W-->>U: {"type": "segment", ...}
    end
    W-->>U: {"type": "finished", "output": "*.srt"}
```

## Run from source (developers)

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e .          # dependencies from pyproject.toml
pip install pytest PySide6  # tests and GUI

# console
PYTHONPATH=src python -m giga_transcribe "input/call.wav" --format srt

# GUI
PYTHONPATH=src python -m giga_transcribe.desktop.app
```

Requirements: Python 3.12, ffmpeg on PATH. No HF token needed
(VAD is Silero, no gated models in the pipeline).

## Checks

```bash
PYTHONPATH=src pytest tests -q          # all tests (mocks, no model)
QT_QPA_PLATFORM=offscreen pytest tests/test_desktop.py  # headless GUI
```

End-to-end engine check — `input/short.wav` (local file, never committed):
7 segments, SRT byte-stable across CPU/GPU.

## Layout

```mermaid
flowchart TB
    subgraph core["core/ — no Qt, no prints, callbacks only"]
        direction LR
        E[engine] --> V[vad]
        J[jobs] --> E
        F[formats: srt/vtt/txt/json]
        D[devices: cpu/cuda/mps]
    end
    W[worker/: JSONL console\nfor QProcess] --> J
    G[desktop/: PySide6\nwindow + setup] --> J
    I[installer/: manifest,\ndownload, setup] --> G
```

- `core/` — engine: model loading, VAD chunking, inference, cancel between chunks.
- `worker/` — same engine as a separate process (JSONL on stdout).
- `desktop/` — window, first-run setup page, QThread/QProcess workers.
- `installer/` — component manifest, resumable SHA-256 downloads, install marker.
- `packaging/` — PyInstaller specs; `.github/workflows/release.yml` — releases.

## Releases and setup

```mermaid
flowchart LR
    TAG["git tag v*"] --> CI["GitHub Actions:\nwin-x64 + mac-arm64"]
    CI --> S0["Setup stub zips\n~12 MB"]
    CI --> B1["GigaAM-UI zips\nfull app"]
    CI --> B2["engine-*.zip\nPyTorch + models"]
    CI --> B3["ffmpeg URLs\npinned, not mirrored"]
    CI --> M["manifest.json\nURL + SHA + size"]
    S0 & B1 & B2 & M --> REL["GitHub Release"]
    REL -- "user downloads stub" --> ST[stub]
    ST -- "setup on click" --> B1 & B2 & B3
```

## Privacy

- Audio and transcripts are processed locally only.
- Never committed: audio, subtitles, tokens, models (see `.gitignore`).
- `input/` holds local files for manual runs only.
- Component licenses and sources: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Status and plans

Done: core, CLI, GUI, on-click setup, win/mac engine packs, MPS on Apple Silicon,
v0.1.x releases.

Next: file queue, CUDA engine pack (needs hardware to verify),
speaker diarization, auto-updates.
See `AGENTS.md` — skill routing and architecture boundaries.
