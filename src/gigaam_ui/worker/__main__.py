"""GigaAM-Worker: `python -m gigaam_ui.worker --job job.json`.

Protocol (v1, one JSON object per stdout line):
  {"type": "stage", "name": "loading_model" | "transcribing"}
  {"type": "segments", "total": N}
  {"type": "segment", "index": i, "start": s, "end": e, "text": t,
   "current": i, "total": N}
  {"type": "finished", "output": path, "elapsed": s, "segments": N}
  {"type": "error", "message": text}            # fatal, then exit 1
  {"type": "cancelled", "partial": path}        # then exit 130
Cancel: create the --cancel-file; the worker checks it between chunks.
"""
import argparse
import json
import os
import sys


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def log(*parts) -> None:
    print(*parts, file=sys.stderr, flush=True)


def main(argv=None) -> int:
    from gigaam_ui.core import compat, devices, formats, jobs, models

    compat.load_dotenv()
    ap = argparse.ArgumentParser(description="gigaam-ui inference worker")
    ap.add_argument("--job", required=True, help="path to job.json")
    ap.add_argument("--cancel-file", default=None,
                    help="worker stops when this file appears")
    args = ap.parse_args(argv)

    try:
        with open(args.job, encoding="utf-8-sig") as f:
            spec = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        emit({"type": "error", "message": f"bad job file: {e}"})
        return 1

    for key in ("input", "output", "format", "model", "device"):
        if key not in spec:
            emit({"type": "error", "message": f"job.json missing key: {key}"})
            return 1

    compat.ensure_ffmpeg()
    try:
        device = devices.resolve(spec["device"])
        models.get(spec["model"])
        formats.WRITERS[spec["format"]]
    except SystemExit as e:
        emit({"type": "error", "message": str(e)})
        return 1

    job = jobs.Job(input=spec["input"], output=spec["output"],
                   fmt=spec["format"], model_id=spec["model"], device=device)

    def cancelled() -> bool:
        return bool(args.cancel_file) and os.path.exists(args.cancel_file)

    total = {"n": 0}
    result = jobs.run(
        job,
        on_stage=lambda name: emit({"type": "stage", "name": name}),
        on_segments=lambda n: (total.__setitem__("n", n),
                               emit({"type": "segments", "total": n})),
        on_chunk=lambda seg, prog: emit({
            "type": "segment", "index": seg.index, "start": seg.start,
            "end": seg.end, "text": seg.text.strip(),
            "current": prog.done, "total": prog.total}),
        should_cancel=cancelled,
    )
    if result.status == "done":
        emit({"type": "finished", "output": result.output,
              "elapsed": round(result.elapsed, 2),
              "segments": result.segments})
        return 0
    if result.status == "cancelled":
        emit({"type": "cancelled", "partial": result.output})
        return 130
    emit({"type": "error", "message": result.error})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
