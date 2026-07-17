#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["mflux==0.18.0"]
# ///
"""Generate images locally with FLUX.1-schnell for website/app assets.

Single image:
    uv run scripts/generate.py "warm photo of a pottery studio" \
        --out public/hero.webp --size 1440x800

Batch (loads the model once for all jobs):
    uv run scripts/generate.py --batch manifest.json
"""

import argparse
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from imagegen_core import (
    SUPPORTED_EXTENSIONS,
    Job,
    apply_style,
    discover_style_config,
    finalize_image,
    numbered_outputs,
    parse_manifest,
    parse_size,
    plan_generation_size,
    resolve_seeds,
    save_image,
)

DEFAULT_MODEL = "dhairyashil/FLUX.1-schnell-mflux-4bit"
BASE_MODEL = "schnell"


def check_environment() -> None:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        sys.exit(
            "agentimagegen v1 requires an Apple Silicon Mac (macOS arm64).\n"
            "Linux/CUDA support is on the roadmap:\n"
            "https://github.com/ethanrogers/agentimagegen#roadmap"
        )
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
        )
        if int(result.stdout.strip()) < 16 * 1024**3:
            print(
                "warning: under 16 GB RAM; generation may be very slow (swapping).",
                file=sys.stderr,
            )
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass  # RAM check is best-effort only


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images locally with FLUX.1-schnell."
    )
    parser.add_argument("prompt", nargs="?", help="image description")
    parser.add_argument("--out", help="output path (.webp, .png, or .jpg)")
    parser.add_argument("--size", help="exact output size, e.g. 1440x800")
    parser.add_argument("--seed", type=int, help="fixed seed for reproducibility")
    parser.add_argument(
        "--count", type=int, default=1, help="number of candidates (hero-1.webp, ...)"
    )
    parser.add_argument("--steps", type=int, default=4, help="inference steps")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model repo")
    parser.add_argument(
        "--batch", help="JSON manifest: [{prompt, out, size, seed?, count?}, ...]"
    )
    parser.add_argument(
        "--no-style", action="store_true", help="ignore project imagegen.toml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the generation plan without loading the model",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.count < 1:
        sys.exit("error: --count must be at least 1")
    if args.steps < 1:
        sys.exit("error: --steps must be at least 1")

    try:
        if args.batch:
            jobs = parse_manifest(Path(args.batch))
        elif args.prompt:
            if not args.out or not args.size:
                sys.exit("error: --out and --size are required with a prompt")
            width, height = parse_size(args.size)
            jobs = [
                Job(
                    prompt=args.prompt,
                    out=Path(args.out),
                    width=width,
                    height=height,
                    seed=args.seed,
                    count=args.count,
                )
            ]
        else:
            sys.exit("error: provide a prompt or --batch manifest.json")

        for job in jobs:
            if job.out.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError(
                    f"unsupported output format {job.out.suffix!r} for {job.out}: "
                    "use .webp, .png, or .jpg"
                )

        style = None if args.no_style else discover_style_config(Path.cwd())
    except (ValueError, OSError) as exc:
        sys.exit(f"error: {exc}")
    plans = []
    for job in jobs:
        job.prompt = apply_style(job.prompt, style)
        gen_w, gen_h, needs_upscale = plan_generation_size(job.width, job.height)
        outs = numbered_outputs(job.out, job.count)
        seeds = resolve_seeds(job.seed, job.count)
        plans.append((job, gen_w, gen_h, needs_upscale, outs, seeds))

    if args.dry_run:
        for job, gen_w, gen_h, needs_upscale, outs, seeds in plans:
            note = " (will be Lanczos-upscaled)" if needs_upscale else ""
            for out, seed in zip(outs, seeds):
                print(
                    f"[dry-run] {out}  {job.width}x{job.height}  "
                    f"gen@{gen_w}x{gen_h}{note}  seed={seed}"
                )
                print(f"          prompt: {job.prompt}")
        return

    check_environment()
    run_plans(plans, model=args.model, steps=args.steps)


def run_plans(plans, model: str, steps: int) -> None:
    print(f"loading {model} (first run downloads ~7 GB)...", flush=True)
    from mflux.models.flux.variants.txt2img.flux import Flux1, ModelConfig

    flux = Flux1(model_config=ModelConfig.from_name(model, base_model=BASE_MODEL))
    for job, gen_w, gen_h, needs_upscale, outs, seeds in plans:
        for out, seed in zip(outs, seeds):
            generated = flux.generate_image(
                seed=seed,
                prompt=job.prompt,
                num_inference_steps=steps,
                width=gen_w,
                height=gen_h,
            )
            image = finalize_image(generated.image, job.width, job.height)
            if needs_upscale:
                print(
                    f"warning: {out} exceeds the native generation ceiling; "
                    f"upscaled from {gen_w}x{gen_h}.",
                    file=sys.stderr,
                )
            save_image(image, out)
            print(f"wrote {out} ({job.width}x{job.height}, seed={seed})")


if __name__ == "__main__":
    main()
