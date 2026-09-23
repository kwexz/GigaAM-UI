"""Console client over core (debug/regression; the GUI is the main client)."""
import argparse
import sys

from .core import compat, devices, formats, jobs, models


def main(argv=None) -> int:
    compat.load_dotenv()
    ap = argparse.ArgumentParser(description="Transcribe audio/video with GigaAM-v3")
    ap.add_argument("input", help="audio or video file")
    ap.add_argument("--model", default="e2e_rnnt", choices=sorted(models.CATALOG),
                    help="model revision")
    ap.add_argument("--device", default="cpu",
                    help="cpu | cuda[:N] | mps | auto")
    ap.add_argument("--format", default="srt", choices=sorted(formats.WRITERS),
                    help="output subtitle format")
    ap.add_argument("--output", default=None, help="output file (default: beside input)")
    args = ap.parse_args(argv)

    compat.ensure_ffmpeg()
    device = devices.resolve(args.device)
    output = args.output or jobs.default_output(args.input, args.format)
    job = jobs.Job(input=args.input, output=output, fmt=args.format,
                   model_id=args.model, device=device)

    print(f"Transcribing: {job.input} [{job.model_id}/{job.device} -> {job.fmt}]")

    def on_stage(name):
        print({"loading_model": "Loading model...",
               "transcribing": "Transcribing..."}.get(name, name), flush=True)

    def on_segments(total):
        print(f"Segments: {total}", flush=True)

    def on_chunk(seg, prog):
        print(f"[{prog.done}/{prog.total} {prog.percent:.0f}%] {seg.text[:80]}",
              flush=True)

    result = jobs.run(job, on_stage=on_stage, on_segments=on_segments,
                      on_chunk=on_chunk)
    if result.status == "done":
        print(f"\nFinished in {result.elapsed:.2f} sec, "
              f"{result.segments} segments\nSaved to: {result.output}")
        return 0
    if result.status == "cancelled":
        print(f"\nCancelled after {result.elapsed:.2f} sec, "
              f"partial kept at: {result.output}")
        return 130
    print(f"\nFailed: {result.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
